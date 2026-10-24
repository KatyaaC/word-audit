"""Propagate ledger changes to linked content and passports."""
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from ..dates import parse_iso_date
from ..errors import NotFound
from ..models import ClaimRecord, Content, ContentVersion, LedgerClaim, Passport
from . import audit
from .registry import LEDGER_FIELDS, refresh_ledger_derived

MATERIAL = {"statement", "metric", "value", "unit", "qualifier", "scope", "period", "expires_on", "status"}


def propagate(session: Session, led: LedgerClaim, reason: str, actor: str = "system") -> dict:
    links = session.exec(select(ClaimRecord).where(ClaimRecord.ledger_claim_key == led.claim_key)).all()
    content_ids, passport_ids = set(), set()
    for cv_id in {l.content_version_id for l in links}:
        cv = session.get(ContentVersion, cv_id)
        content = session.get(Content, cv.content_id) if cv else None
        if not content or cv.version_no != content.current_version_no:
            continue
        content.status = "flagged" if content.status == "approved" else "needs_review"
        content.flag_reason = reason
        session.add(content)
        content_ids.add(content.id)
        for p in session.exec(select(Passport).where(Passport.content_version_id == cv.id)).all():
            p.current_status, p.status_reason = "flagged", reason
            session.add(p)
            passport_ids.add(p.id)
    result = {"claim_key": led.claim_key, "content_ids": sorted(content_ids), "passport_ids": sorted(passport_ids)}
    audit.log(session, actor, "impact.propagated", "ledger_claim", led.claim_key, {**result, "reason": reason})
    return result


def update_ledger_claim(session: Session, claim_id: int, changes: dict, actor: str) -> dict:
    led = session.get(LedgerClaim, claim_id)
    if not led:
        raise NotFound("Ledger fact not found")
    changed = {k: v for k, v in changes.items() if k in LEDGER_FIELDS and getattr(led, k) != v}
    impact = None
    if changed:
        for k, v in changed.items():
            setattr(led, k, v)
        led.version += 1
        refresh_ledger_derived(led)
        session.add(led)
        audit.log(session, actor, "ledger.updated", "ledger_claim", led.claim_key, {"changed": sorted(changed)})
        if MATERIAL & set(changed):
            impact = propagate(session, led, f"Ledger fact {led.claim_key} changed ({', '.join(sorted(changed))})",
                               actor)
    return {"claim": led, "changed": sorted(changed), "impact": impact}


def sweep_expired(session: Session, today: Optional[date] = None, actor: str = "system") -> list:
    today = today or date.today()
    out = []
    for led in session.exec(select(LedgerClaim).where(LedgerClaim.status == "active")).all():
        exp = parse_iso_date(led.expires_on)
        if exp and exp < today:
            led.status = "expired"
            led.version += 1
            session.add(led)
            audit.log(session, actor, "ledger.expired", "ledger_claim", led.claim_key, {"expires_on": led.expires_on})
            out.append(propagate(session, led, f"Ledger fact {led.claim_key} expired on {led.expires_on}", actor))
    return out
