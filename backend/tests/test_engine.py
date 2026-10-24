from datetime import date

from sqlmodel import select

from app.engine.claims import heuristic_extract
from app.engine.layer_b import check_claims
from app.engine.layer_c import detect_drift
from app.engine.ladders import assess
from app.engine.pipeline import run_engine
from app.models import Rule


def status_of(session, text, today=None):
    res = check_claims(session, heuristic_extract(text), today=today)
    assert len(res) == 1, [r.claim.text for r in res]
    return res[0]


def test_ladders():
    a = assess("Support time fell by up to 60% among pilot participants.")
    assert (a.qualifier_rank, a.scope_rank) == (1, 0)
    b = assess("Our platform guarantees 60% faster resolution for every customer.")
    assert (b.qualifier_rank, b.scope_rank) == (4, 3)
    assert assess("We reduce cost.").scope_rank == 2


def test_verified(session):
    r = status_of(session, "Support resolution time fell by up to 60% among pilot participants in 2025.")
    assert r.status == "Verified", (r.fields, r.reasons)


def test_contradicted_value(session):
    r = status_of(session, "Support resolution time fell by up to 80% among pilot participants in 2025.")
    assert r.status == "Contradicted", r.fields


def test_contradicted_customer_count(session):
    r = status_of(session, "Over 3,000 customers use the platform in 2026.")
    assert r.status == "Contradicted", (r.fields, r.reasons)


def test_unsupported_when_no_evidence(session):
    r = status_of(session, "Our app is rated 4.9 stars by editors.")
    assert r.status == "Unsupported" and r.ledger is None


def test_uncertain_when_fact_expired(session):
    r = status_of(session, "92% of surveyed customers reported satisfaction in 2024.", today=date(2026, 10, 24))
    assert r.status == "Uncertain" and r.fields["expiry"] == "expired"


def test_drift_detected_and_explained(session):
    r = status_of(session, "Support resolution time fell by 60% for every customer in 2025.")
    d = detect_drift(r)
    assert r.status == "Uncertain" and d and d.q_steps >= 1 and d.s_steps == 3 and d.severity in ("medium", "high")


def test_drift_finding_replaces_duplicate_b_finding(session, llm):
    rules = session.exec(select(Rule).where(Rule.status == "active")).all()
    out = run_engine(session, "Our platform guarantees 60% faster support resolution time for every customer. "
                              "Results may vary.", rules, llm)
    layers = [f.layer for f in out.findings if f.kind in ("claim", "drift")]
    assert "C" in layers
    assert layers.count("B") == 0
