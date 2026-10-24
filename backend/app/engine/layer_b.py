"""Layer B: deterministic claim verification against the Claim Ledger."""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..dates import parse_iso_date
from ..models import LedgerClaim
from ..services.embeddings import embed, nearest_ledger, related_threshold
from .claims import ParsedClaim, metrics_match
from .ladders import Strength, assess, comparator_of, comparators_compatible
from .textutil import norm_period, norm_unit

BAD = {"mismatch", "differs", "broader", "stronger", "expired", "unverifiable"}


@dataclass
class ClaimResult:
    claim: ParsedClaim
    status: str
    ledger: Optional[LedgerClaim]
    similarity: float
    fields: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)
    strength: Optional[Strength] = None


def _close(a: float, b: float, rel: float) -> bool:
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-9)


def value_verdict(c_val: float, c_cmp: str, l_val: float) -> str:
    if c_cmp == "exact":
        return "match" if _close(c_val, l_val, 0.01) else "mismatch"
    if c_cmp == "approx":
        return "match" if _close(c_val, l_val, 0.05) else "mismatch"
    return "match" if c_val <= l_val * 1.01 else "mismatch"


def is_expired(led: LedgerClaim, today: date) -> bool:
    if led.status == "expired":
        return True
    exp = parse_iso_date(led.expires_on)
    return bool(exp and exp < today)


def evaluate(claim: ParsedClaim, led: LedgerClaim, today: date):
    cs = assess(claim.text)
    c_cmp = comparator_of(claim.text)
    l_cmp = comparator_of(f"{led.statement} {led.qualifier or ''}")
    f = {"metric": metrics_match(claim.metric, led.metric)}
    cu, lu = norm_unit(claim.unit), norm_unit(led.unit)
    f["unit"] = "unknown" if not (cu and lu) else ("match" if cu == lu else "mismatch")
    if led.value is None:
        f["value"] = "unknown"
    elif claim.value is None:
        f["value"] = "unverifiable"
    elif f["unit"] == "mismatch":
        f["value"] = "unknown"
    else:
        f["value"] = value_verdict(claim.value, c_cmp, led.value)
    if claim.value is not None and led.value is not None and not comparators_compatible(c_cmp, l_cmp):
        f["qualifier"] = "differs"
    elif cs.qualifier_rank > led.qualifier_rank:
        f["qualifier"] = "stronger"
    else:
        f["qualifier"] = "match"
    f["scope"] = "match" if cs.scope_rank <= led.scope_rank else "broader"
    cp, lp = norm_period(claim.period), norm_period(led.period)
    f["period"] = "unspecified" if not (cp and lp) else ("match" if cp == lp else "differs")
    f["expiry"] = "expired" if is_expired(led, today) else "match"

    reasons = []
    if f["expiry"] == "expired":
        status = "Uncertain"
        reasons.append(f"Approved fact {led.claim_key} has expired; a person must confirm it still holds.")
    elif f["metric"] != "match":
        status = "Uncertain"
        reasons.append("Related evidence exists, but it does not clearly measure the same thing.")
    elif f["unit"] == "mismatch":
        status = "Uncertain"
        reasons.append("The approved fact uses a different unit.")
    elif f["value"] == "mismatch" and f["period"] != "differs":
        status = "Contradicted"
        reasons.append(f"The figure in the draft is not supported by approved fact {led.claim_key}.")
    elif any(v in BAD for v in f.values()):
        status = "Uncertain"
        bad = [k for k, v in f.items() if v in BAD]
        reasons.append("Partly supported, but these parts differ from the approved fact: " + ", ".join(bad) + ".")
    else:
        status = "Verified"
    return status, f, reasons


def check_claims(session, claims: list, *, today: Optional[date] = None, k: int = 4) -> list:
    today = today or date.today()
    if not claims:
        return []
    vecs = embed([c.text for c in claims])
    threshold = related_threshold()
    results = []
    for claim, vec in zip(claims, vecs):
        cands = nearest_ledger(session, vec, k)
        top_sim = cands[0][1] if cands else 0.0
        evaluated = []
        for led, sim in cands:
            status, fields, reasons = evaluate(claim, led, today)
            related = (fields["metric"] == "match" and fields["unit"] != "mismatch") or sim >= threshold
            if related:
                evaluated.append((status, fields, reasons, led, sim))
        strength = assess(claim.text)
        if not evaluated:
            results.append(ClaimResult(claim, "Unsupported", None, top_sim, {},
                                       ["No approved fact in the Claim Ledger backs this statement."], strength))
            continue
        evaluated.sort(key=lambda e: (e[0] == "Verified", sum(1 for v in e[1].values() if v == "match"), e[4]),
                       reverse=True)
        status, fields, reasons, led, sim = evaluated[0]
        results.append(ClaimResult(claim, status, led, sim, fields, reasons, strength))
    return results
