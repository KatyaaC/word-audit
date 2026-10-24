from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from . import models
from .config import get_settings
from .dates import parse_iso_date
from .db import get_session
from .security import Actor, get_actor, require
from .services import audit, impact, linter, parsing, passport, registry, review
from .services.llm import LLMRouter, build_router
from .services.redaction import redact

router = APIRouter()


def get_llm() -> LLMRouter:
    return build_router()


def pub(obj, drop=("embedding",)):
    d = obj.model_dump()
    for k in drop:
        d.pop(k, None)
    return d


# Schemas
class LedgerIn(BaseModel):
    claim_key: str
    statement: str
    metric: str = ""
    value: Optional[float] = None
    unit: Optional[str] = None
    qualifier: Optional[str] = None
    scope: Optional[str] = None
    period: Optional[str] = None
    evidence_url: str = ""
    owner: str = ""
    expires_on: Optional[str] = None


class LedgerPatch(BaseModel):
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


class RuleIn(BaseModel):
    rule_key: str
    kind: Literal["banned_term", "required_term", "tone", "claim", "accessibility"]
    text: str
    severity: Literal["low", "medium", "high"] = "medium"
    owner: str = ""
    source_ref: str = ""
    pattern: dict = {}
    examples_pass: list = []
    examples_fail: list = []


class ContentIn(BaseModel):
    title: str
    text: str
    classification: Literal["Public", "Internal", "Restricted"] = "Internal"


class ReviseIn(BaseModel):
    text: str


class ReviewIn(BaseModel):
    external_confirmed: bool = False


class DecisionIn(BaseModel):
    decision: Literal["accepted", "modified", "rejected"]
    reason: str = Field(min_length=3)
    modified_text: Optional[str] = None


class ApproveIn(BaseModel):
    mode: Literal["strict", "solo"] = "strict"


class RedactIn(BaseModel):
    text: str
    protected_terms: list = []


class LintIn(BaseModel):
    external_confirmed: bool = False


# Health and transparency
@router.get("/health")
def health():
    return {"ok": True}


@router.get("/transparency")
def transparency():
    from .services.embeddings import active_backend

    s = get_settings()
    return {"commercial_model": s.commercial_model if s.llm_provider == "anthropic" else None,
            "local_model": s.ollama_model if s.local_llm_provider == "ollama" else "mock-local",
            "embeddings": active_backend(), "restricted_content": "processed only by the local model",
            "outbound_text": "redacted locally, previewed and confirmed before transmission",
            "passport_public_key": passport.public_key_hex()}


# Ledger
@router.post("/ledger")
def ledger_create(body: LedgerIn, s: Session = Depends(get_session), a: Actor = Depends(require("brand_manager"))):
    led = registry.create_ledger_claim(s, body.model_dump(), a.user)
    s.commit()
    return pub(led)


@router.get("/ledger")
def ledger_list(expiring_within_days: Optional[int] = None, s: Session = Depends(get_session)):
    items = s.exec(select(models.LedgerClaim)).all()
    if expiring_within_days is not None:
        from datetime import date, timedelta

        horizon = date.today() + timedelta(days=expiring_within_days)
        filtered = []
        for i in items:
            exp = parse_iso_date(i.expires_on)
            if exp is not None and exp <= horizon:
                filtered.append(i)
        items = filtered
    return [pub(i) for i in items]


@router.get("/ledger/{claim_id}")
def ledger_get(claim_id: int, s: Session = Depends(get_session)):
    return pub(registry.get_ledger(s, claim_id))


@router.patch("/ledger/{claim_id}")
def ledger_patch(claim_id: int, body: LedgerPatch, s: Session = Depends(get_session),
                 a: Actor = Depends(require("brand_manager"))):
    out = impact.update_ledger_claim(s, claim_id, body.model_dump(exclude_unset=True), a.user)
    s.commit()
    return {"claim": pub(out["claim"]), "changed": out["changed"], "impact": out["impact"]}


@router.post("/admin/sweep-expired")
def sweep(s: Session = Depends(get_session), a: Actor = Depends(require("brand_manager"))):
    out = impact.sweep_expired(s, actor=a.user)
    s.commit()
    return {"expired": out}


# Constitution
@router.post("/rules")
def rule_create(body: RuleIn, s: Session = Depends(get_session), a: Actor = Depends(require("brand_manager"))):
    r = registry.create_rule(s, body.model_dump(), a.user)
    s.commit()
    return pub(r)


@router.get("/rules")
def rule_list(status: Optional[str] = None, s: Session = Depends(get_session)):
    q = select(models.Rule)
    if status:
        q = q.where(models.Rule.status == status)
    return [pub(r) for r in s.exec(q).all()]


@router.post("/rules/{rule_id}/approve")
def rule_approve(rule_id: int, s: Session = Depends(get_session), a: Actor = Depends(require("brand_manager"))):
    r = registry.approve_rule(s, rule_id, a.user)
    s.commit()
    return pub(r)


@router.post("/constitution/release")
def constitution_release(s: Session = Depends(get_session), a: Actor = Depends(require("brand_manager"))):
    v = registry.release_constitution(s, a.user)
    s.commit()
    return v.model_dump()


@router.post("/documents/parse")
async def documents_parse(file: UploadFile = File(...)):
    doc = parsing.parse_document(file.filename or "upload", await file.read())
    return {"filename": doc.filename, "chars": len(doc.text),
            "chunks": [{"ref": c.ref, "page": c.page, "text": c.text} for c in doc.chunks]}


@router.post("/rules/draft-from-document")
async def rules_draft(file: UploadFile = File(...), s: Session = Depends(get_session),
                      a: Actor = Depends(require("brand_manager"))):
    doc = parsing.parse_document(file.filename or "upload", await file.read())
    out = [pub(registry.create_rule(s, d, a.user, drafted_by_software=True))
           for d in parsing.draft_rules_from_chunks(doc.chunks)]
    s.commit()
    return {"drafted": out, "note": "Drafts are inactive until a Brand Manager approves each one."}


# Content and review
@router.post("/content")
def content_create(body: ContentIn, s: Session = Depends(get_session), a: Actor = Depends(get_actor)):
    c = review.create_content(s, title=body.title, text=body.text, classification=body.classification,
                              creator=a.user)
    s.commit()
    return pub(c)


@router.get("/content/{content_id}")
def content_get(content_id: int, s: Session = Depends(get_session)):
    c = s.get(models.Content, content_id)
    if not c:
        raise HTTPException(404, "Content not found")
    cv = review.latest_version(s, c)
    return {**pub(c), "text": cv.text, "content_version_id": cv.id, "constitution_version": cv.constitution_version_number}


@router.post("/content/{content_id}/revise")
def content_revise(content_id: int, body: ReviseIn, s: Session = Depends(get_session), a: Actor = Depends(get_actor)):
    c = review.revise_content(s, content_id, body.text, a.user)
    s.commit()
    return pub(c)


@router.post("/content/{content_id}/review")
def content_review(content_id: int, body: ReviewIn, s: Session = Depends(get_session), a: Actor = Depends(get_actor),
                   llm: LLMRouter = Depends(get_llm)):
    out = review.review_content(s, content_id, llm, external_confirmed=body.external_confirmed, actor=a.user)
    s.commit()
    return {**out, "findings": [pub(f) for f in out["findings"]]}


@router.get("/content/{content_id}/findings")
def content_findings(content_id: int, s: Session = Depends(get_session)):
    c = s.get(models.Content, content_id)
    if not c:
        raise HTTPException(404, "Content not found")
    cv = review.latest_version(s, c)
    return [pub(f) for f in s.exec(select(models.Finding).where(models.Finding.content_version_id == cv.id)).all()]


@router.get("/content/{content_id}/claims")
def content_claims(content_id: int, s: Session = Depends(get_session)):
    c = s.get(models.Content, content_id)
    if not c:
        raise HTTPException(404, "Content not found")
    cv = review.latest_version(s, c)
    return [pub(r) for r in s.exec(select(models.ClaimRecord).where(models.ClaimRecord.content_version_id == cv.id)).all()]


@router.post("/findings/{finding_id}/decision")
def finding_decision(finding_id: int, body: DecisionIn, s: Session = Depends(get_session),
                     a: Actor = Depends(require("creator", "reviewer"))):
    f = review.decide_finding(s, finding_id, decision=body.decision, reason=body.reason,
                              modified_text=body.modified_text, actor=a.user)
    s.commit()
    return pub(f)


@router.post("/content/{content_id}/approve")
def content_approve(content_id: int, body: ApproveIn, s: Session = Depends(get_session),
                    a: Actor = Depends(require("approver"))):
    p = review.approve_content(s, content_id, approver=a.user, mode=body.mode)
    s.commit()
    return {"passport_id": p.id}


# Passport
@router.get("/passport/{passport_id}")
def passport_get(passport_id: str, s: Session = Depends(get_session)):
    return passport.verify_passport(s, passport_id)


@router.get("/passport/{passport_id}/verify")
def passport_verify(passport_id: str, s: Session = Depends(get_session)):
    return passport.verify_passport(s, passport_id)


@router.post("/demo/tamper/{content_version_id}")
def demo_tamper(content_version_id: int, s: Session = Depends(get_session)):
    if not get_settings().enable_demo_endpoints:
        raise HTTPException(404, "Not found")
    out = passport.tamper_demo(s, content_version_id)
    s.commit()
    return out


# Privacy, linter, and audit
@router.post("/redaction/preview")
def redaction_preview(body: RedactIn, classification: str = "Internal", llm: LLMRouter = Depends(get_llm)):
    r = redact(body.text, body.protected_terms)
    external = llm.commercial is not None and classification != "Restricted"
    return {"redacted_text": r.redacted, "spans": r.spans, "engine": r.engine,
            "will_leave_system": external,
            "destination": "commercial API (after confirmation)" if external else "local model only",
            "warning": "Redaction may miss some identifiers, including unpublished product names."}


@router.post("/linter/run")
def linter_run(body: LintIn, s: Session = Depends(get_session), llm: LLMRouter = Depends(get_llm),
               a: Actor = Depends(require("brand_manager"))):
    return {"findings": linter.lint_rules(s, llm, external_confirmed=body.external_confirmed)}


@router.get("/audit")
def audit_list(limit: int = 100, s: Session = Depends(get_session)):
    rows = s.exec(select(models.AuditLog).order_by(models.AuditLog.seq.desc()).limit(limit)).all()
    return [r.model_dump() for r in rows]


@router.get("/audit/verify")
def audit_verify(s: Session = Depends(get_session)):
    return audit.verify_chain(s)
