"""Content review orchestration: engine execution, findings, approval, and passport issuance."""
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from ..engine.fixes import suggest_fix
from ..engine.pipeline import run_engine
from ..errors import Conflict, Forbidden, NotFound
from ..models import (ClaimRecord, Content, ContentVersion, Finding, LedgerClaim, Passport, Rule, now_iso)
from . import audit
from .passport import issue_passport
from .registry import current_constitution


def latest_version(session: Session, content: Content) -> ContentVersion:
    cv = session.exec(select(ContentVersion).where(ContentVersion.content_id == content.id,
                                                   ContentVersion.version_no == content.current_version_no)).first()
    if not cv:
        raise NotFound("Content version missing")
    return cv


def create_content(session: Session, *, title: str, text: str, classification: str, creator: str) -> Content:
    if classification not in ("Public", "Internal", "Restricted"):
        raise Conflict("classification must be Public, Internal or Restricted")
    c = Content(title=title, classification=classification, creator=creator)
    session.add(c)
    session.flush()
    session.add(ContentVersion(content_id=c.id, version_no=1, text=text))
    audit.log(session, creator, "content.created", "content", c.id, {"title": title, "classification": classification})
    return c


def revise_content(session: Session, content_id: int, text: str, actor: str) -> Content:
    c = session.get(Content, content_id)
    if not c:
        raise NotFound("Content not found")
    c.current_version_no += 1
    c.status, c.flag_reason = "draft", None
    session.add(c)
    session.add(ContentVersion(content_id=c.id, version_no=c.current_version_no, text=text))
    audit.log(session, actor, "content.revised", "content", c.id, {"version": c.current_version_no})
    return c


def review_content(session: Session, content_id: int, llm, *, external_confirmed: bool = False, actor: str = "system",
                   today: Optional[date] = None) -> dict:
    content = session.get(Content, content_id)
    if not content:
        raise NotFound("Content not found")
    cv = latest_version(session, content)
    rules = session.exec(select(Rule).where(Rule.status == "active")).all()
    cons = current_constitution(session)
    cv.constitution_version_number = cons.number if cons else 0
    for old in session.exec(select(Finding).where(Finding.content_version_id == cv.id)).all():
        session.delete(old)
    for old in session.exec(select(ClaimRecord).where(ClaimRecord.content_version_id == cv.id)).all():
        session.delete(old)
    llm.reset_calls()
    kw = dict(classification=content.classification, external_confirmed=external_confirmed, today=today)
    result = run_engine(session, cv.text, rules, llm, **kw)
    ledger_by_key = {l.claim_key: l for l in session.exec(select(LedgerClaim)).all()}

    rows = []
    for rf in result.findings:
        fix, verified = suggest_fix(session, cv.text, rf, result.findings, rules, llm, ledger_by_key, **kw)
        row = Finding(
            content_version_id=cv.id, layer=rf.layer, source_kind=rf.source_kind, kind=rf.kind, status=rf.status,
            claim_status=rf.claim_status, severity=rf.severity, rule_key=rf.rule_key,
            ledger_claim_key=rf.ledger_claim_key, claim_text=rf.claim_text, span_start=rf.start, span_end=rf.end,
            excerpt=rf.excerpt, explanation=rf.explanation, details=rf.details, suggested_fix=fix,
            fix_verified=verified)
        session.add(row)
        rows.append(row)

    claims_out = []
    for res in result.claim_results:
        st, led = res.strength, res.ledger
        details = {
            "fields": res.fields, "reasons": res.reasons,
            "draft": {"qualifier_rank": st.qualifier_rank, "qualifier_label": st.qualifier_label,
                      "qualifier_phrase": st.qualifier_phrase, "scope_rank": st.scope_rank,
                      "scope_label": st.scope_label, "scope_phrase": st.scope_phrase},
            "approved": ({"claim_key": led.claim_key, "statement": led.statement,
                          "qualifier_rank": led.qualifier_rank, "scope_rank": led.scope_rank,
                          "evidence_url": led.evidence_url} if led else None),
            "parsed": res.claim.model_dump(exclude={"start", "end"}),
        }
        rec = ClaimRecord(content_version_id=cv.id, ledger_claim_key=led.claim_key if led else None,
                          claim_text=res.claim.text, claim_status=res.status, similarity=round(res.similarity, 3),
                          span_start=res.claim.start, span_end=res.claim.end, details=details)
        session.add(rec)
        claims_out.append({"claim_text": rec.claim_text, "status": rec.claim_status,
                           "ledger_claim_key": rec.ledger_claim_key, "similarity": rec.similarity, **details})

    cv.review_run_at = now_iso()
    cv.llm_info = {"usage": llm.usage_summary()}
    content.status, content.flag_reason = "in_review", None
    session.add(cv)
    session.add(content)
    session.flush()
    audit.log(session, actor, "content.reviewed", "content", content.id,
              {"version": cv.version_no, "findings": len(rows), "usage": cv.llm_info["usage"]})
    return {"content_id": content.id, "version_no": cv.version_no, "findings": rows, "claims": claims_out,
            "llm_usage": cv.llm_info["usage"]}


def decide_finding(session: Session, finding_id: int, *, decision: str, reason: str, modified_text: Optional[str],
                   actor: str) -> Finding:
    f = session.get(Finding, finding_id)
    if not f:
        raise NotFound("Finding not found")
    cv = session.get(ContentVersion, f.content_version_id)
    content = session.get(Content, cv.content_id)
    if cv.version_no != content.current_version_no:
        raise Conflict("This finding belongs to an older version of the content")
    if decision == "modified" and not modified_text:
        raise Conflict("Provide modified_text when decision is 'modified'")
    f.decision, f.decision_reason, f.modified_text = decision, reason.strip(), modified_text
    f.decided_by, f.decided_at = actor, now_iso()
    session.add(f)
    audit.log(session, actor, f"finding.{decision}", "finding", f.id, {"reason": f.decision_reason})
    return f


def approve_content(session: Session, content_id: int, *, approver: str, mode: str) -> Passport:
    content = session.get(Content, content_id)
    if not content:
        raise NotFound("Content not found")
    cv = latest_version(session, content)
    if not cv.review_run_at:
        raise Conflict("Run the automated review before approval")
    findings = session.exec(select(Finding).where(Finding.content_version_id == cv.id)).all()
    pending = [f.id for f in findings if f.decision == "pending"]
    if pending:
        raise Conflict(f"Every finding needs a decision first; pending finding ids: {pending}")
    if mode == "strict" and approver == content.creator:
        raise Forbidden("Strict mode: the creator cannot approve their own content")
    p = issue_passport(session, content, cv, approver=approver, mode=mode, findings=findings)
    content.status, content.flag_reason = "approved", None
    session.add(content)
    audit.log(session, approver, "content.approved", "content", content.id, {"passport_id": p.id, "mode": mode})
    return p
