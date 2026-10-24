"""Claim Ledger and Brand Constitution management."""
from typing import Optional

from sqlmodel import Session, select

from ..engine.ladders import assess
from ..errors import Conflict, NotFound
from ..models import ConstitutionVersion, LedgerClaim, Rule, now_iso
from . import audit
from .embeddings import embed

LEDGER_FIELDS = {"statement", "metric", "value", "unit", "qualifier", "scope", "period", "evidence_url", "owner",
                 "expires_on", "status"}


def refresh_ledger_derived(led: LedgerClaim) -> None:
    """Recompute strength ranks and embedding for a ledger claim."""
    s = assess(f"{led.statement} {led.qualifier or ''} {led.scope or ''}")
    led.qualifier_rank, led.scope_rank = s.qualifier_rank, s.scope_rank
    led.embedding = embed([f"{led.statement} {led.metric}"])[0]
    led.updated_at = now_iso()


def create_ledger_claim(session: Session, data: dict, actor: str) -> LedgerClaim:
    if session.exec(select(LedgerClaim).where(LedgerClaim.claim_key == data["claim_key"])).first():
        raise Conflict(f"Ledger fact {data['claim_key']} already exists")
    led = LedgerClaim(**{k: v for k, v in data.items() if k in LEDGER_FIELDS | {"claim_key"}})
    refresh_ledger_derived(led)
    session.add(led)
    session.flush()
    audit.log(session, actor, "ledger.created", "ledger_claim", led.claim_key, {"statement": led.statement})
    return led


def get_ledger(session: Session, claim_id: int) -> LedgerClaim:
    led = session.get(LedgerClaim, claim_id)
    if not led:
        raise NotFound("Ledger fact not found")
    return led


def create_rule(session: Session, data: dict, actor: str, *, drafted_by_software: bool = False) -> Rule:
    allowed = {"rule_key", "kind", "text", "severity", "owner", "source_ref", "pattern", "examples_pass",
               "examples_fail"}
    rule = Rule(**{k: v for k, v in data.items() if k in allowed}, drafted_by_software=drafted_by_software,
                status="draft")
    rule.embedding = embed([rule.text])[0]
    session.add(rule)
    session.flush()
    audit.log(session, actor, "rule.drafted", "rule", rule.id, {"rule_key": rule.rule_key})
    return rule


def approve_rule(session: Session, rule_id: int, approver: str) -> Rule:
    rule = session.get(Rule, rule_id)
    if not rule:
        raise NotFound("Rule not found")
    for old in session.exec(select(Rule).where(Rule.rule_key == rule.rule_key, Rule.status == "active")).all():
        if old.id != rule.id:
            old.status = "retired"
            session.add(old)
    rule.status, rule.approved_by = "active", approver
    session.add(rule)
    audit.log(session, approver, "rule.approved", "rule", rule.id, {"rule_key": rule.rule_key})
    return rule


def current_constitution(session: Session) -> Optional[ConstitutionVersion]:
    return session.exec(select(ConstitutionVersion).order_by(ConstitutionVersion.number.desc()).limit(1)).first()


def release_constitution(session: Session, actor: str) -> ConstitutionVersion:
    last = current_constitution(session)
    rules = session.exec(select(Rule).where(Rule.status == "active")).all()
    ver = ConstitutionVersion(
        number=(last.number + 1) if last else 1, released_by=actor,
        rule_snapshot=[{"rule_id": r.id, "rule_key": r.rule_key, "text": r.text} for r in rules])
    session.add(ver)
    session.flush()
    audit.log(session, actor, "constitution.released", "constitution_version", ver.number, {"rules": len(rules)})
    return ver
