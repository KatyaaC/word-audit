"""Seed data for the Claim Ledger, rules, and constitution."""
from sqlmodel import Session, select

from .models import LedgerClaim
from .services.registry import approve_rule, create_ledger_claim, create_rule, release_constitution

LEDGER = [
    dict(claim_key="CL-0001", statement="Support resolution time fell by up to 60% among pilot participants in 2025.",
         metric="support resolution time reduction", value=60, unit="%", qualifier="up to",
         scope="pilot participants", period="2025", evidence_url="https://example.com/evidence/pilot-2025",
         owner="Head of CX", expires_on="2027-03-31"),
    dict(claim_key="CL-0002", statement="More than 2,500 customers use the platform as of 2026.",
         metric="customer count", value=2500, unit="customer", qualifier="more than", period="2026",
         evidence_url="https://example.com/evidence/customers-2026", owner="Sales Ops", expires_on="2099-12-31"),
    dict(claim_key="CL-0003", statement="92% of surveyed customers reported satisfaction in 2024.",
         metric="customer satisfaction rate", value=92, unit="%", scope="surveyed customers", period="2024",
         evidence_url="https://example.com/evidence/csat-2024", owner="CX Research", expires_on="2025-06-30"),
]

RULES = [
    dict(rule_key="R-TERM-001", kind="banned_term", severity="high", owner="Legal", source_ref="p.2 ¶1",
         text="Never use absolute or unsubstantiated health terms such as miracle or cure.",
         pattern={"terms": ["miracle", "cure"], "replacements": {"miracle": "effective"}}),
    dict(rule_key="R-TERM-002", kind="required_term", severity="medium", owner="Legal", source_ref="p.3 ¶4",
         text="Any percentage claim must carry the wording 'Results may vary'.",
         pattern={"terms": ["Results may vary"], "when": r"\d\s*%"}),
    dict(rule_key="R-TONE-001", kind="tone", severity="low", owner="Brand", source_ref="p.5 ¶1",
         text="Keep a professional but friendly tone that feels natural and approachable.",
         examples_pass=["Happy to help you get set up today."], examples_fail=["Yo, whatever, figure it out lol"]),
]


def seed(session: Session) -> None:
    if session.exec(select(LedgerClaim).where(LedgerClaim.claim_key == "CL-0001")).first():
        return
    for d in LEDGER:
        create_ledger_claim(session, d, "seed")
    for d in RULES:
        approve_rule(session, create_rule(session, d, "seed").id, "seed")
    release_constitution(session, "seed")
    session.commit()
