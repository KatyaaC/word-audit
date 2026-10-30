"""Website API (/api/*).

Implements the contract the Next.js frontend expects (docs/API_CONTRACT.md and
web/lib/types.ts) on top of the existing services. The original routes in
api.py are unchanged.

What this layer adds:
  * JWT login with four roles (auth.py)
  * the brand rule pack checks the editor runs live (brand_pack/), stored as
    Layer A findings next to the engine's own findings
  * the workflow states between review and approval
  * comments and history (kept in the hash-chained audit log)
  * insights, the impact graph, and a rules overview
"""
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from . import models
from .auth import (DEMO_USERS, UserOut, check_password, create_token, current_user, find_user, require_roles,
                   user_by_name)
from .brand_pack import CheckRequest, count_by_severity, load_rule_pack, run_layer_a as run_brand_pack
from .dates import parse_iso_date
from .db import get_session
from .errors import Conflict, Forbidden, NotFound
from .services import audit, impact, parsing, passport, registry, review
from .services.llm import build_router

router = APIRouter(prefix="/api", tags=["Website"])

EDITABLE = {"draft", "changes_requested", "needs_rereview"}
RESPONDABLE = {"draft", "changes_requested"}

# ---------------------------------------------------------------- helpers


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display(name: str) -> str:
    return name or "Unknown"


def _author_id(name: str) -> str:
    u = user_by_name(name)
    return u.id if u else name


def _ui_state(c: models.Content) -> str:
    if c.status in ("flagged", "needs_review"):
        return "needs_rereview"
    return c.status


def _content(s: Session, content_id: str) -> models.Content:
    try:
        c = s.get(models.Content, int(content_id))
    except ValueError:
        c = None
    if not c:
        raise NotFound("Content not found")
    return c


def _versions(s: Session, c: models.Content) -> list:
    return s.exec(select(models.ContentVersion).where(models.ContentVersion.content_id == c.id)
                  .order_by(models.ContentVersion.version_no)).all()


def _ver_label(n: Optional[int]) -> str:
    return f"v{n or 0}"


def _fmt_value(value, unit) -> str:
    if value is None:
        return "Not stated"
    v = f"{value:,.0f}" if float(value).is_integer() else f"{value:,}"
    if not unit:
        return v
    return f"{v}{unit}" if unit == "%" else f"{v} {unit}"


# ---------------------------------------------------------------- findings

_CLAIM_MSG = {
    "Contradicted": "This figure doesn't match the approved evidence.",
    "Unsupported": "We couldn't find a source for this claim.",
    "Uncertain": "This claim needs a person to check it against the evidence.",
}


def _message(f: models.Finding) -> str:
    d = f.details or {}
    if d.get("message"):
        return d["message"]
    if f.kind == "banned_term":
        return f'Try to avoid "{f.excerpt}" here.'
    if f.kind == "required_term":
        return f'This needs to include "{f.excerpt}".'
    if f.kind == "drift":
        return "This claim says more than the evidence supports."
    return _CLAIM_MSG.get(f.claim_status or "", "Please take a look at this.")


def _plain_drift(f: models.Finding) -> Optional[str]:
    """Everyday wording for a Layer C drift finding, built from the engine's own details."""
    d = f.details or {}
    q, sc, fact = d.get("qualifier") or {}, d.get("scope") or {}, d.get("closest_fact") or {}
    if not fact:
        return None
    parts = []
    if q.get("steps"):
        parts.append(f"it sounds more certain (\"{q.get('draft_phrase') or 'stated as fact'}\" where the evidence "
                     f"only supports \"{QUAL_STEPS[q.get('approved_rank', 3)]}\")")
    if sc.get("steps"):
        parts.append(f"it covers more people (\"{sc.get('draft_phrase') or 'no limit stated'}\" where the evidence "
                     f"only covers \"{SCOPE_STEPS[sc.get('approved_rank', 2)]}\")")
    if not parts:
        return None
    return (f"This claim goes further than approved fact {fact.get('claim_key')}: " + " and ".join(parts)
            + f". The approved wording is: \"{fact.get('statement')}\"")


def finding_out(f: models.Finding, rule_version: str) -> dict:
    d = f.details or {}
    has_span = f.span_start >= 0 and f.span_end > f.span_start
    fix_type = d.get("fix_type") or ("replace" if (f.suggested_fix is not None and has_span) else
                                     "insert" if f.suggested_fix else "advice")
    resp = None
    if f.decision != "pending":
        resp = {"decision": f.decision, "reason": f.decision_reason or "", "modified_text": f.modified_text,
                "by": _display(f.decided_by or ""), "at": f.decided_at or ""}
    return {
        "id": str(f.id), "layer": f.layer, "kind": f.kind or f.layer, "source": f.source_kind, "status": f.status,
        "rule_id": f.rule_key, "rule_version": rule_version, "fact_id": f.ledger_claim_key, "severity": f.severity,
        "message": _message(f),
        "explanation": (_plain_drift(f) if f.kind == "drift" else None) or f.explanation,
        "span": {"start": f.span_start, "end": f.span_end} if has_span else None,
        "matched_text": f.excerpt or None, "fix_type": fix_type,
        "suggestion": d.get("suggestion", f.suggested_fix),
        "suggestion_verified": (f.fix_verified if f.source_kind == "automated_assessment" and f.suggested_fix else None),
        "target": d.get("target"),
        "claim_status": f.claim_status.lower() if f.claim_status else None,
        "response": resp,
    }


def _store_brand_pack(s: Session, cv: models.ContentVersion, text: str, html: Optional[str], pairs: list,
                      images: list) -> None:
    """Run the brand rule pack (same rules as the live editor) and save its findings as Layer A rows."""
    pack = load_rule_pack()
    found = run_brand_pack(CheckRequest(text=text, html=html, colour_pairs=pairs, images=images), pack)
    taken = {(f.span_start, f.span_end) for f in s.exec(select(models.Finding)
                                                        .where(models.Finding.content_version_id == cv.id)).all()
             if f.span_start >= 0}
    for bf in found:
        span = (bf.span.start, bf.span.end) if bf.span else (-1, -1)
        if span[0] >= 0 and span in taken:
            continue  # the engine already flagged exactly this text
        s.add(models.Finding(
            content_version_id=cv.id, layer="A", source_kind="fixed_check", kind=bf.kind.value,
            status="rule_violation", severity=bf.severity.value, rule_key=bf.rule_id, span_start=span[0],
            span_end=span[1], excerpt=bf.matched_text or "", explanation=bf.explanation,
            details={"message": bf.message, "fix_type": bf.fix_type, "suggestion": bf.suggestion,
                     "target": bf.target, "rule_pack": pack.version},
            suggested_fix=bf.suggestion, fix_verified=False))


def _run_review(s: Session, c: models.Content, actor: str, html: Optional[str], pairs: list, images: list) -> None:
    review.review_content(s, c.id, build_router(), actor=actor)
    cv = review.latest_version(s, c)
    _store_brand_pack(s, cv, cv.text, html, pairs, images)
    cv.llm_info = {**(cv.llm_info or {}),
                   "ui": {"html": html, "colour_pairs": pairs, "images": images}}
    s.add(cv)
    c.status, c.flag_reason = "draft", None  # the creator responds before it goes to a reviewer
    s.add(c)


# ---------------------------------------------------------------- claims

QUAL_STEPS = ["may", "up to", "typically", "plain statement", "guaranteed"]
SCOPE_STEPS = ["in a pilot", "some customers", "most customers", "every customer"]


def _claim_out(s: Session, r: models.ClaimRecord) -> dict:
    d = r.details or {}
    parsed, draft, approved = d.get("parsed") or {}, d.get("draft") or {}, d.get("approved")
    led = (s.exec(select(models.LedgerClaim).where(models.LedgerClaim.claim_key == r.ledger_claim_key)).first()
           if r.ledger_claim_key else None)
    draft_parts = {
        "metric": parsed.get("metric") or "Not stated",
        "value": _fmt_value(parsed.get("value"), parsed.get("unit")),
        "population": draft.get("scope_phrase") or parsed.get("scope") or "Not stated",
        "conditions": draft.get("qualifier_phrase") or parsed.get("qualifier") or "Not stated",
        "period": parsed.get("period") or "Not stated",
    }
    ledger_parts, ladders = None, []
    if led and (d.get("fields") or {}).get("metric") == "match":
        draft_parts["metric"] = led.metric or draft_parts["metric"]  # the engine matched it to the same measure
    if led:
        ledger_parts = {"metric": led.metric or "Not stated", "value": _fmt_value(led.value, led.unit),
                        "population": led.scope or "Not stated", "conditions": led.qualifier or "Not stated",
                        "period": led.period or "Not stated"}
    if approved and draft:
        ladders = [
            {"name": "Qualifier strength", "steps": QUAL_STEPS, "draft_index": draft.get("qualifier_rank", 3),
             "ledger_index": approved.get("qualifier_rank", 3)},
            {"name": "Scope", "steps": SCOPE_STEPS, "draft_index": draft.get("scope_rank", 2),
             "ledger_index": approved.get("scope_rank", 2)},
        ]
    reasons = d.get("reasons") or []
    explanation = " ".join(reasons) or ("Matches the approved fact." if r.claim_status == "Verified" else "")
    return {"claim_id": str(r.id), "status": r.claim_status.lower(), "draft_text": r.claim_text,
            "draft": draft_parts, "ledger_fact_id": r.ledger_claim_key,
            "ledger_text": led.statement if led else None, "ledger": ledger_parts, "ladders": ladders,
            "explanation": explanation}


# ---------------------------------------------------------------- content item

_ACTION = {
    "content.created": "created", "content.revised": "added a new version", "content.reviewed": "ran the checks",
    "content.approved": "approved", "workflow.submit": "sent for review", "workflow.forward": "sent to the approver",
    "workflow.request_changes": "asked for changes", "comment.added": "commented",
    "finding.accepted": "accepted a finding", "finding.modified": "edited a finding", "finding.rejected":
        "rejected a finding", "impact.flagged": "flagged for another look",
}


def _content_audit(s: Session, c: models.Content, finding_ids: set) -> list:
    rows = s.exec(select(models.AuditLog).where(models.AuditLog.entity == "content",
                                                models.AuditLog.entity_id == str(c.id))).all()
    if finding_ids:
        rows += s.exec(select(models.AuditLog).where(models.AuditLog.entity == "finding",
                                                     models.AuditLog.entity_id.in_([str(i) for i in finding_ids]))).all()
    return sorted(rows, key=lambda r: r.seq)


def content_item(s: Session, c: models.Content) -> dict:
    versions = _versions(s, c)
    latest = versions[-1]
    rule_version = _ver_label(latest.constitution_version_number)
    findings = s.exec(select(models.Finding).where(models.Finding.content_version_id == latest.id)).all()
    findings.sort(key=lambda f: ({"high": 0, "medium": 1, "low": 2}.get(f.severity, 3),
                                 f.span_start if f.span_start >= 0 else 10**9))
    claims = s.exec(select(models.ClaimRecord).where(models.ClaimRecord.content_version_id == latest.id)).all()
    all_fids = {f.id for v in versions for f in s.exec(select(models.Finding)
                                                      .where(models.Finding.content_version_id == v.id)).all()}
    log = _content_audit(s, c, all_fids)
    comments = [{"id": f"cm-{r.seq}", "author": _display(r.actor), "role": (r.data or {}).get("role", "creator"),
                 "body": (r.data or {}).get("body", ""), "at": r.ts} for r in log if r.action == "comment.added"]
    history = []
    for r in log:
        if r.action == "comment.added":
            continue
        detail = (r.data or {}).get("reason") or ((r.data or {}).get("version") and f"Version {r.data['version']}")
        history.append({"at": r.ts, "actor": _display(r.actor), "action": _ACTION.get(r.action, r.action),
                        "detail": detail or None})
    if c.flag_reason:
        history.append({"at": log[-1].ts if log else _now(), "actor": "System", "action": "flagged",
                        "detail": c.flag_reason})
    p = s.exec(select(models.Passport).where(models.Passport.content_version_id == latest.id)
               .order_by(models.Passport.created_at.desc())).first()
    return {
        "id": str(c.id), "title": c.title, "state": _ui_state(c), "author_id": _author_id(c.creator),
        "author_name": _display(c.creator),
        "versions": [{"version": v.version_no, "text": v.text, "html": ((v.llm_info or {}).get("ui") or {}).get("html"),
                      "author": _display(c.creator), "created_at": v.created_at,
                      "rule_pack_version": _ver_label(v.constitution_version_number)} for v in versions],
        "findings": [finding_out(f, rule_version) for f in findings],
        "claims": [_claim_out(s, r) for r in claims],
        "comments": comments, "audit": history,
        "passport_id": p.id if p else None,
        "updated_at": log[-1].ts if log else c.created_at,
    }


# ---------------------------------------------------------------- schemas


class LoginIn(BaseModel):
    email: str
    password: str


class ColourPairIn(BaseModel):
    element: str
    foreground: str
    background: str
    large_text: bool = False


class ImageIn(BaseModel):
    src: str
    alt: Optional[str] = None
    decorative: bool = False


class SubmissionIn(BaseModel):
    title: str = "Untitled draft"
    text: str = Field(min_length=1)
    html: Optional[str] = None
    colour_pairs: list[ColourPairIn] = []
    images: list[ImageIn] = []


class ResponseIn(BaseModel):
    decision: Literal["accepted", "modified", "rejected"]
    reason: str
    modified_text: Optional[str] = None


class CommentIn(BaseModel):
    body: str = Field(min_length=1)


class TransitionIn(BaseModel):
    action: Literal["submit", "forward", "request_changes", "approve"]
    reason: Optional[str] = None


class VerifyIn(BaseModel):
    content: Optional[str] = None


class RuleDecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = ""


# ---------------------------------------------------------------- auth + layer A


@router.post("/auth/login")
def login(body: LoginIn):
    user = find_user(body.email)
    if not user or not check_password(body.password):
        raise HTTPException(401, "Wrong email or password")
    return {"access_token": create_token(user), "token_type": "bearer", "user": user.model_dump()}


@router.get("/auth/me")
def me(user: UserOut = Depends(current_user)):
    return user.model_dump()


@router.post("/layer-a/check")
def layer_a_check(body: CheckRequest):
    pack = load_rule_pack()
    found = run_brand_pack(body, pack)
    return {"rule_pack_version": pack.version, "checked_at": _now(),
            "findings": [f.model_dump(mode="json") for f in found], "counts": count_by_severity(found)}


# ---------------------------------------------------------------- content


@router.get("/content")
def list_content(s: Session = Depends(get_session), _: UserOut = Depends(current_user)):
    items = [content_item(s, c) for c in s.exec(select(models.Content)).all()]
    return sorted(items, key=lambda i: i["updated_at"], reverse=True)


@router.post("/content")
def create_content(body: SubmissionIn, s: Session = Depends(get_session),
                   user: UserOut = Depends(require_roles("creator"))):
    c = review.create_content(s, title=body.title.strip() or "Untitled draft", text=body.text,
                              classification="Internal", creator=user.name)
    _run_review(s, c, user.name, body.html, [p.model_dump() for p in body.colour_pairs],
                [i.model_dump() for i in body.images])
    s.commit()
    return content_item(s, c)


@router.get("/content/{content_id}")
def get_content(content_id: str, s: Session = Depends(get_session), _: UserOut = Depends(current_user)):
    return content_item(s, _content(s, content_id))


@router.post("/content/{content_id}/versions")
def new_version(content_id: str, body: SubmissionIn, s: Session = Depends(get_session),
                user: UserOut = Depends(require_roles("creator"))):
    c = _content(s, content_id)
    if c.creator != user.name:
        raise Forbidden("Only the creator can add a new version.")
    if _ui_state(c) not in EDITABLE:
        raise Conflict("A new version can only be added to a draft or after changes are requested.")
    if body.title.strip():
        c.title = body.title.strip()
    review.revise_content(s, c.id, body.text, user.name)
    _run_review(s, c, user.name, body.html, [p.model_dump() for p in body.colour_pairs],
                [i.model_dump() for i in body.images])
    s.commit()
    return content_item(s, c)


@router.post("/content/{content_id}/findings/{finding_id}/response")
def respond(content_id: str, finding_id: str, body: ResponseIn, s: Session = Depends(get_session),
            user: UserOut = Depends(require_roles("creator"))):
    c = _content(s, content_id)
    if c.creator != user.name:
        raise Forbidden("Only the creator responds to findings.")
    if _ui_state(c) not in RESPONDABLE:
        raise Conflict("Findings can only be answered while the content is a draft.")
    if len(body.reason.strip()) < 5:
        raise Conflict("A reason of at least 5 characters is required.")
    f = s.get(models.Finding, int(finding_id)) if finding_id.isdigit() else None
    if not f or f.content_version_id != review.latest_version(s, c).id:
        raise NotFound("Finding not found on the latest version")
    review.decide_finding(s, f.id, decision=body.decision, reason=body.reason,
                          modified_text=body.modified_text, actor=user.name)
    s.commit()
    return content_item(s, c)


@router.post("/content/{content_id}/comments")
def add_comment(content_id: str, body: CommentIn, s: Session = Depends(get_session),
                user: UserOut = Depends(current_user)):
    c = _content(s, content_id)
    audit.log(s, user.name, "comment.added", "content", c.id, {"body": body.body.strip(), "role": user.role})
    s.commit()
    return content_item(s, c)


@router.post("/content/{content_id}/transition")
def transition(content_id: str, body: TransitionIn, s: Session = Depends(get_session),
               user: UserOut = Depends(current_user)):
    c = _content(s, content_id)
    state = _ui_state(c)

    def need(roles: tuple, states: tuple):
        if user.role not in roles:
            raise Forbidden(f"Only {' or '.join(roles)} can do this.")
        if state not in states:
            raise Conflict(f'Not allowed while the content is "{state}".')

    if body.action == "submit":
        need(("creator",), ("draft", "changes_requested"))
        if c.creator != user.name:
            raise Forbidden("Only the author can send this for review.")
        cv = review.latest_version(s, c)
        pending = [f for f in s.exec(select(models.Finding).where(models.Finding.content_version_id == cv.id)).all()
                   if f.decision == "pending"]
        if pending:
            raise Conflict(f"You still have {len(pending)} item{'s' if len(pending) != 1 else ''} to respond to.")
        c.status = "in_review"
    elif body.action == "forward":
        need(("reviewer",), ("in_review",))
        c.status = "awaiting_approval"
    elif body.action == "request_changes":
        need(("reviewer", "approver"), ("in_review", "awaiting_approval"))
        if not body.reason or len(body.reason.strip()) < 5:
            raise Conflict("Let them know what to change.")
        c.status = "changes_requested"
    else:  # approve: Sudiksha's approval issues the signed Passport
        need(("approver",), ("awaiting_approval",))
        review.approve_content(s, c.id, approver=user.name, mode="strict")
    s.add(c)
    if body.action != "approve":
        audit.log(s, user.name, f"workflow.{body.action}", "content", c.id,
                  {"reason": body.reason} if body.reason else {})
    s.commit()
    return content_item(s, c)


# ---------------------------------------------------------------- passports

AUTOMATION_NOTE = ("Wording checked against brand rules; claims checked automatically against approved evidence. "
                   "Every decision was made by a person.")


def passport_out(s: Session, pid: str) -> dict:
    v = passport.verify_passport(s, pid)
    p = s.get(models.Passport, pid)
    payload = json.loads(p.payload_json)
    cv = s.get(models.ContentVersion, p.content_version_id)
    c = s.get(models.Content, cv.content_id) if cv else None
    status, reason = ("valid" if p.current_status == "valid" else "needs_rereview"), p.status_reason
    if status == "valid" and not v["checks"].get("latest_version", True):
        status, reason = "needs_rereview", "The content has a newer version than the one approved."
    return {
        "id": p.id, "content_id": str(payload["content_id"]), "content_title": c.title if c else "",
        "content_version": payload["content_version"], "canonical_text": cv.text if cv else "",
        "fingerprint": payload["content_fingerprint"], "hash_algorithm": "SHA-256", "signature": p.signature,
        "signature_algorithm": "Ed25519", "public_key": p.public_key,
        "guideline_version": _ver_label(payload["guideline_version"]),
        "evidence": [{"fact_id": e["claim_key"], "text": e["statement"], "evidence_url": e.get("evidence_url") or "",
                      "expires_at": e.get("expires_on") or ""} for e in payload["evidence_snapshot"]],
        "creator": _display(payload["creator"]), "approved_by": _display(payload["approved_by"]),
        "approved_at": payload["compliant_as_of"], "mode": payload["approval_mode"],
        "automation_disclosure": AUTOMATION_NOTE, "compliant_as_of": payload["compliant_as_of"],
        "current_status": status, "current_status_reason": reason,
        "rules_version_now": _ver_label(cons.number if (cons := registry.current_constitution(s)) else 0),
    }


@router.get("/passports/{pid}")
def get_passport(pid: str, s: Session = Depends(get_session)):
    return passport_out(s, pid)


@router.post("/passports/{pid}/verify")
def verify(pid: str, body: VerifyIn = VerifyIn(), s: Session = Depends(get_session)):
    v = passport.verify_passport(s, pid)
    p = s.get(models.Passport, pid)
    expected = json.loads(p.payload_json)["content_fingerprint"]
    if body.content is None:
        cv = s.get(models.ContentVersion, p.content_version_id)
        computed = passport.fingerprint(cv.text) if cv else ""
    else:
        computed = passport.fingerprint(body.content)
    return {"passport_id": pid, "signature_valid": bool(v["checks"]["signature"]),
            "fingerprint_match": computed == expected, "computed_fingerprint": computed,
            "expected_fingerprint": expected, "current_status": passport_out(s, pid)["current_status"],
            "checked_at": _now()}


# ---------------------------------------------------------------- ledger + insights


@router.post("/ledger/facts/{fact_key}/expire")
def expire_fact(fact_key: str, s: Session = Depends(get_session),
                user: UserOut = Depends(require_roles("reviewer", "approver", "brand_manager"))):
    led = s.exec(select(models.LedgerClaim).where(models.LedgerClaim.claim_key == fact_key)).first()
    if not led:
        raise NotFound("Fact not found")
    out = impact.update_ledger_claim(s, led.id, {"status": "expired", "expires_on": date.today().isoformat()},
                                     user.name)
    s.commit()
    hit = out["impact"] or {"content_ids": [], "passport_ids": []}
    return {"fact_id": fact_key, "flagged_content": [str(i) for i in hit["content_ids"]],
            "flagged_passports": list(hit["passport_ids"])}


def _week(ts: Optional[str]) -> Optional[str]:
    if not ts:
        return None
    try:
        y, w, _ = datetime.fromisoformat(ts).isocalendar()
    except ValueError:
        return None
    return f"{y}-W{w:02d}"


@router.get("/insights")
def insights(s: Session = Depends(get_session), _: UserOut = Depends(current_user)):
    findings = s.exec(select(models.Finding)).all()
    cvs = {cv.id: cv for cv in s.exec(select(models.ContentVersion)).all()}

    key = lambda f: f.rule_key or f.ledger_claim_key or f.kind  # noqa: E731
    counts = Counter(key(f) for f in findings)
    repeated = [{"rule_id": k, "label": k, "count": n} for k, n in counts.most_common(6)]

    weeks: dict = defaultdict(lambda: {"layer_a": 0, "layer_b": 0, "layer_c": 0})
    for f in findings:
        cv = cvs.get(f.content_version_id)
        w = _week(cv.review_run_at if cv else None)
        if w and f.layer in ("A", "B", "C"):
            weeks[w][f"layer_{f.layer.lower()}"] += 1
    per_week = [{"week": w.split("-")[1], **weeks[w]} for w in sorted(weeks)[-8:]]

    decided, rejected = Counter(), Counter()
    for f in findings:
        if f.decision != "pending":
            decided[key(f)] += 1
            rejected[key(f)] += f.decision == "rejected"
    confusing = sorted(({"rule_id": k, "label": k, "override_rate": round(100 * rejected[k] / n)}
                        for k, n in decided.items()), key=lambda r: -r["override_rate"])[:5]

    today = date.today()
    expiring = []
    for led in s.exec(select(models.LedgerClaim).where(models.LedgerClaim.status == "active")).all():
        exp = parse_iso_date(led.expires_on)
        if exp:
            expiring.append({"fact_id": led.claim_key, "label": led.claim_key, "days_left": max(0, (exp - today).days)})
    expiring.sort(key=lambda e: e["days_left"])

    nodes, edges = [], []
    for led in s.exec(select(models.LedgerClaim)).all():
        nodes.append({"id": led.claim_key, "kind": "fact", "label": f"{led.claim_key}: {led.statement[:38]}…",
                      "status": "expired" if led.status == "expired" else "ok"})
    for c in s.exec(select(models.Content)).all():
        cv = review.latest_version(s, c)
        keys = {r.ledger_claim_key for r in s.exec(select(models.ClaimRecord)
                                                   .where(models.ClaimRecord.content_version_id == cv.id)).all()
                if r.ledger_claim_key}
        if not keys:
            continue
        nodes.append({"id": str(c.id), "kind": "content", "label": f"{c.id}: {c.title}",
                      "status": "flagged" if _ui_state(c) == "needs_rereview" else "ok"})
        edges += [{"source": k, "target": str(c.id)} for k in sorted(keys)]
        for p in s.exec(select(models.Passport).where(models.Passport.content_version_id == cv.id)).all():
            nodes.append({"id": p.id, "kind": "passport", "label": f"Passport {p.id[:8]}",
                          "status": "ok" if p.current_status == "valid" else "flagged"})
            edges.append({"source": str(c.id), "target": p.id})

    return {"repeated_mistakes": repeated, "findings_per_week": per_week, "confusing_rules": confusing,
            "expiring_facts": expiring[:8], "impact": {"nodes": nodes, "edges": edges}}


# ---------------------------------------------------------------- brand rules (constitution)

_KIND = {"banned_term": "banned_term", "required_term": "required_term", "tone": "tone", "claim": "claim",
         "accessibility": "accessibility"}


def _page(ref: str) -> Optional[int]:
    if ref and ref.startswith("p.") and ref[2:].split(" ")[0].isdigit():
        return int(ref[2:].split(" ")[0])
    return None


def _rule_out(r: models.Rule, doc: str) -> dict:
    return {"id": str(r.id), "title": f"{r.rule_key}: {r.text[:80]}{'…' if len(r.text) > 80 else ''}",
            "kind": _KIND.get(r.kind, "visual"), "severity": r.severity, "owner": r.owner or "Unassigned",
            "source_doc": doc, "source_page": _page(r.source_ref), "source_passage": r.text,
            "pass_examples": r.examples_pass or [], "fail_examples": r.examples_fail or (r.pattern or {}).get("terms", []),
            "status": r.status if r.status in ("draft", "active", "rejected") else "rejected", "version": 1,
            "drafted_by": "software" if r.drafted_by_software else "human", "decided_by": r.approved_by,
            "decision_reason": None}


def _pack_doc() -> dict:
    pack = load_rule_pack()
    rules = [{"id": f"pack:{t.id}", "title": (f"Avoid: {', '.join(t.terms)}" if t.kind == "banned"
                                              else f'Require: "{t.terms[0]}"'),
              "kind": "banned_term" if t.kind == "banned" else "required_term", "severity": t.severity.value,
              "owner": "Brand team", "source_doc": t.source_ref, "source_page": None, "source_passage": t.reason,
              "pass_examples": [t.replacement] if t.replacement else [t.terms[0]],
              "fail_examples": t.terms if t.kind == "banned" else ["(wording left out)"], "status": "active",
              "version": 1, "drafted_by": "human", "decided_by": None, "decision_reason": None}
             for t in pack.terms]
    return {"id": "pack", "filename": f"Brand rule pack {pack.version} (checked live in the editor)",
            "classification": "internal", "uploaded_at": "", "uploaded_by": "Brand team", "rules": rules}


def constitution_out(s: Session) -> dict:
    cons = registry.current_constitution(s)
    rules = {r.id: r for r in s.exec(select(models.Rule)).all() if r.status != "retired"}
    docs, used = [], set()
    uploads = s.exec(select(models.AuditLog).where(models.AuditLog.action == "constitution.uploaded")
                     .order_by(models.AuditLog.seq.desc())).all()
    for u in uploads:
        d = u.data or {}
        ids = [i for i in d.get("rule_ids", []) if i in rules]
        used.update(ids)
        docs.append({"id": f"D-{u.seq}", "filename": d.get("filename", "Uploaded document"),
                     "classification": d.get("classification", "internal"), "uploaded_at": u.ts,
                     "uploaded_by": _display(u.actor), "rules": [_rule_out(rules[i], d.get("filename", "")) for i in ids]})
    rest = [r for i, r in rules.items() if i not in used]
    if rest:
        docs.append({"id": "D-core", "filename": "Core brand rules", "classification": "internal",
                     "uploaded_at": rest[0].created_at, "uploaded_by": "Brand team",
                     "rules": [_rule_out(r, "Core brand rules") for r in rest]})
    docs.append(_pack_doc())
    return {"version": _ver_label(cons.number if cons else 0), "documents": docs}


@router.get("/constitution")
def get_constitution(s: Session = Depends(get_session), _: UserOut = Depends(current_user)):
    return constitution_out(s)


@router.post("/constitution/upload")
async def upload_guidelines(file: UploadFile = File(...), classification: str = Form("internal"),
                            s: Session = Depends(get_session), user: UserOut = Depends(require_roles("brand_manager"))):
    if classification not in ("public", "internal", "restricted"):
        raise Conflict("Classification must be public, internal or restricted.")
    name = file.filename or "upload"
    doc = parsing.parse_document(name, await file.read())
    n = len(s.exec(select(models.AuditLog).where(models.AuditLog.action == "constitution.uploaded")).all()) + 1
    ids = []
    for d in parsing.draft_rules_from_chunks(doc.chunks):
        d["rule_key"] = f"D{n}-{d['rule_key']}"  # keep keys unique across uploads
        ids.append(registry.create_rule(s, d, user.name, drafted_by_software=True).id)
    entry = audit.log(s, user.name, "constitution.uploaded", "document", name,
                      {"filename": name, "classification": classification, "rule_ids": ids})
    s.commit()
    return next(d for d in constitution_out(s)["documents"] if d["id"] == f"D-{entry.seq}")


@router.post("/constitution/rules/{rule_id}/decision")
def decide_rule(rule_id: str, body: RuleDecisionIn, s: Session = Depends(get_session),
                user: UserOut = Depends(require_roles("brand_manager"))):
    if not rule_id.isdigit():
        raise Conflict("Rules in the built-in rule pack are already live and can't be changed here.")
    r = s.get(models.Rule, int(rule_id))
    if not r:
        raise NotFound("Rule not found")
    if r.status != "draft":
        raise Conflict("This rule has already been decided.")
    if body.decision == "approve":
        registry.approve_rule(s, r.id, user.name)
        registry.release_constitution(s, user.name)  # new content is checked against the new version
    else:
        r.status = "rejected"
        s.add(r)
        audit.log(s, user.name, "rule.rejected", "rule", r.id, {"reason": body.reason})
    s.commit()
    return constitution_out(s)


__all__ = ["router", "DEMO_USERS"]


# ---------------------------------------------------------------- claim ledger (improvement 3)

LEDGER_EDITABLE = {"statement", "metric", "value", "unit", "qualifier", "scope", "period", "evidence_url", "owner",
                   "expires_on", "status"}


def _usage(s: Session, key: str) -> tuple:
    """Current content versions and Passports that rely on a ledger fact."""
    content_ids, passport_ids = set(), set()
    for rec in s.exec(select(models.ClaimRecord).where(models.ClaimRecord.ledger_claim_key == key)).all():
        cv = s.get(models.ContentVersion, rec.content_version_id)
        c = s.get(models.Content, cv.content_id) if cv else None
        if not c or cv.version_no != c.current_version_no:
            continue
        content_ids.add(str(c.id))
        passport_ids.update(p.id for p in s.exec(select(models.Passport)
                                                 .where(models.Passport.content_version_id == cv.id)).all())
    return sorted(content_ids), sorted(passport_ids)


def fact_out(s: Session, led: models.LedgerClaim) -> dict:
    exp = parse_iso_date(led.expires_on)
    used_c, used_p = _usage(s, led.claim_key)
    return {"id": led.claim_key, "statement": led.statement, "metric": led.metric, "value": led.value,
            "unit": led.unit, "qualifier": led.qualifier, "scope": led.scope, "period": led.period,
            "evidence_url": led.evidence_url, "owner": led.owner, "expires_on": led.expires_on,
            "status": led.status, "version": led.version,
            "days_left": (exp - date.today()).days if exp else None,
            "used_by_content": used_c, "used_by_passports": used_p, "updated_at": led.updated_at}


class FactPatchIn(BaseModel):
    statement: Optional[str] = None
    metric: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    qualifier: Optional[str] = None
    scope: Optional[str] = None
    period: Optional[str] = None
    evidence_url: Optional[str] = None
    owner: Optional[str] = None
    expires_on: Optional[str] = None
    status: Optional[Literal["active", "expired", "superseded"]] = None


@router.get("/ledger")
def list_facts(s: Session = Depends(get_session), _: UserOut = Depends(current_user)):
    facts = [fact_out(s, led) for led in s.exec(select(models.LedgerClaim)).all()]
    # most urgent first: expired, then soonest expiry
    return sorted(facts, key=lambda f: (f["status"] == "active", f["days_left"] if f["days_left"] is not None else 10**6))


@router.patch("/ledger/{fact_key}")
def update_fact(fact_key: str, body: FactPatchIn, s: Session = Depends(get_session),
                user: UserOut = Depends(require_roles("brand_manager"))):
    led = s.exec(select(models.LedgerClaim).where(models.LedgerClaim.claim_key == fact_key)).first()
    if not led:
        raise NotFound("Fact not found")
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in LEDGER_EDITABLE}
    if "expires_on" in changes and changes["expires_on"] and not parse_iso_date(changes["expires_on"]):
        raise Conflict("Use a date like 2027-03-31 for the expiry.")
    out = impact.update_ledger_claim(s, led.id, changes, user.name)
    s.commit()
    hit = out["impact"] or {"content_ids": [], "passport_ids": []}
    return {"fact": fact_out(s, led), "changed": out["changed"],
            "flagged_content": [str(i) for i in hit["content_ids"]], "flagged_passports": list(hit["passport_ids"])}


# ---------------------------------------------------------------- rule health (guideline linter)


@router.post("/constitution/lint")
def lint(s: Session = Depends(get_session), user: UserOut = Depends(require_roles("brand_manager"))):
    from .services import linter

    found = linter.lint_rules(s, build_router())
    keys = {r.rule_key: r for r in s.exec(select(models.Rule)).all()}
    out = []
    for f in found:
        out.append({"kind": f["kind"], "method": f["method"], "score": f.get("score"),
                    "explanation": f["explanation"],
                    "rules": [{"key": k, "id": str(keys[k].id) if k in keys else None,
                               "text": keys[k].text if k in keys else ""} for k in f["rules"]],
                    "vague_terms": (f.get("details") or {}).get("vague_terms", [])})
    n = len(s.exec(select(models.Rule).where(models.Rule.status.in_(["draft", "active"]))).all())
    return {"findings": out, "rules_checked": n, "checked_at": _now()}
