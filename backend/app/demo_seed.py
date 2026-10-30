"""Extra ledger facts for the website demo brand ("PaisaLeaf", fictional).

Kept separate from seed_data.py so the engine tests keep their own fixed ledger.
The editor's starter text claims "60% faster reconciliation for every customer",
which these facts let Layers B and C check.
"""
from datetime import date, timedelta

from sqlmodel import Session, select

from .models import LedgerClaim
from .services.registry import create_ledger_claim


def demo_facts() -> list:
    soon = (date.today() + timedelta(days=12)).isoformat()
    return [
        dict(claim_key="CL-PL-001",
             statement="PaisaLeaf Ledger cut reconciliation time by up to 60% in a three-month pilot with 12 retail "
                       "customers in 2026.",
             metric="faster reconciliation", value=60, unit="%", qualifier="up to",
             scope="pilot participants", period="2026", evidence_url="https://example.com/evidence/ledger-pilot-2026",
             owner="Product Analytics", expires_on="2027-06-30"),
        dict(claim_key="CL-PL-002", statement="48,000 active merchants use PaisaLeaf Ledger as of June 2026.",
             metric="active merchants", value=48000, unit="merchant", period="2026",
             evidence_url="https://example.com/evidence/merchants-jun-2026", owner="Sales Ops", expires_on=soon),
    ]


def seed_demo(session: Session) -> None:
    for d in demo_facts():
        if not session.exec(select(LedgerClaim).where(LedgerClaim.claim_key == d["claim_key"])).first():
            create_ledger_claim(session, d, "seed")
    session.commit()
