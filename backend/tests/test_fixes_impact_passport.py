import pytest
from sqlmodel import select

from app.engine.fixes import suggest_fix
from app.engine.pipeline import run_engine
from app.errors import Conflict, Forbidden
from app.models import ClaimRecord, Content, ContentVersion, Finding, LedgerClaim, Passport, Rule
from app.services import audit, impact, passport, review
from app.services.llm import LLMError, LLMRouter, MockClient

DRAFT = ("Our platform guarantees 60% faster support resolution time for every customer. "
         "Results may vary.")


def rules(session):
    return session.exec(select(Rule).where(Rule.status == "active")).all()


def test_fix_is_reverified(session, llm):
    base = run_engine(session, DRAFT, rules(session), llm)
    drift = next(f for f in base.findings if f.kind == "drift")
    fix, ok = suggest_fix(session, DRAFT, drift, base.findings, rules(session), llm,
                          {l.claim_key: l for l in session.exec(select(LedgerClaim)).all()})
    assert ok and "up to 60%" in fix
    new_text = DRAFT[:drift.start] + fix + DRAFT[drift.end:]
    again = run_engine(session, new_text, rules(session), llm, explain=False)
    assert not [f for f in again.findings if f.kind in ("claim", "drift")]


def test_bad_llm_fix_is_rejected_then_falls_back(session):
    class BadFix(MockClient):
        def generate(self, task, payload, temperature=0.0):
            if task == "propose_fix":
                return {"sentence": "Our platform guarantees 90% faster support resolution time for everyone."}
            return super().generate(task, payload, temperature)

    llm = LLMRouter(BadFix())
    base = run_engine(session, DRAFT, rules(session), llm)
    drift = next(f for f in base.findings if f.kind == "drift")
    fix, ok = suggest_fix(session, DRAFT, drift, base.findings, rules(session), llm,
                          {l.claim_key: l for l in session.exec(select(LedgerClaim)).all()})
    assert ok and "guarantees 90%" not in fix  # unverified LLM rewrite never shown; approved wording used


def test_unsupported_claim_gets_no_fix(session, llm):
    text = "Our app is rated 4.9 stars by editors."
    base = run_engine(session, text, rules(session), llm)
    f = next(f for f in base.findings if f.claim_status == "Unsupported")
    assert suggest_fix(session, text, f, base.findings, rules(session), llm, {}) == (None, False)


def full_flow(session, llm, text=DRAFT, creator="katya"):
    c = review.create_content(session, title="T", text=text, classification="Internal", creator=creator)
    out = review.review_content(session, c.id, llm)
    for f in out["findings"]:
        review.decide_finding(session, f.id, decision="accepted", reason="ok", modified_text=None, actor=creator)
    return c


def test_approval_rules_and_passport_verify(session, llm):
    c = full_flow(session, llm)
    with pytest.raises(Forbidden):
        review.approve_content(session, c.id, approver="katya", mode="strict")
    p = review.approve_content(session, c.id, approver="dr-pandey", mode="strict")
    v = passport.verify_passport(session, p.id)
    assert v["valid"] and v["current_status"] == "valid"
    solo = review.approve_content(session, full_flow(session, llm, creator="solo").id, approver="solo", mode="solo")
    assert passport.verify_passport(session, solo.id)["approval_mode"] == "solo"


def test_pending_findings_block_approval(session, llm):
    c = review.create_content(session, title="T", text=DRAFT, classification="Internal", creator="a")
    review.review_content(session, c.id, llm)
    with pytest.raises(Conflict):
        review.approve_content(session, c.id, approver="b", mode="strict")


def test_tamper_and_new_version_fail_verification(session, llm):
    c = full_flow(session, llm)
    p = review.approve_content(session, c.id, approver="b", mode="strict")
    cv = review.latest_version(session, c)
    passport.tamper_demo(session, cv.id)
    v = passport.verify_passport(session, p.id)
    assert not v["valid"] and v["checks"]["content_fingerprint"] is False

    c2 = full_flow(session, llm)
    p2 = review.approve_content(session, c2.id, approver="b", mode="strict")
    review.revise_content(session, c2.id, "A brand new draft.", "katya")
    v2 = passport.verify_passport(session, p2.id)
    assert not v2["valid"] and v2["checks"]["latest_version"] is False


def test_impact_propagation_on_change_and_expiry(session, llm):
    c = full_flow(session, llm)
    p = review.approve_content(session, c.id, approver="b", mode="strict")
    led = session.exec(select(LedgerClaim).where(LedgerClaim.claim_key == "CL-0001")).first()
    out = impact.update_ledger_claim(session, led.id, {"value": 45.0}, "manager")
    assert c.id in out["impact"]["content_ids"] and p.id in out["impact"]["passport_ids"]
    session.refresh(c)
    assert c.status == "flagged"
    v = passport.verify_passport(session, p.id)
    assert v["valid"] and v["current_status"] == "flagged"  # signature intact; status shows the fact changed


def test_sweep_expired_flags_linked_content(session, llm):
    from datetime import date
    c = full_flow(session, llm)
    review.approve_content(session, c.id, approver="b", mode="strict")
    flagged = impact.sweep_expired(session, today=date(2030, 1, 1))
    keys = {f["claim_key"] for f in flagged}
    assert "CL-0001" in keys and any(c.id in f["content_ids"] for f in flagged)


def test_audit_chain_detects_tampering(session, llm):
    full_flow(session, llm)
    assert audit.verify_chain(session)["ok"]
    from app.models import AuditLog
    row = session.exec(select(AuditLog).where(AuditLog.seq == 3)).first()
    row.data = {"forged": True}
    session.add(row)
    session.flush()
    res = audit.verify_chain(session)
    assert not res["ok"] and res["first_bad_seq"] == 3
