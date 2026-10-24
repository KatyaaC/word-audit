"""Layer C: rule-based drift detection using qualifier and scope strength ladders."""
from dataclasses import dataclass
from typing import Optional

from .ladders import QUALIFIER_LABELS, SCOPE_LABELS, assess
from .layer_b import ClaimResult


@dataclass
class Drift:
    result: ClaimResult
    q_steps: int
    s_steps: int
    severity: str
    template: str
    details: dict


def detect_drift(res: ClaimResult) -> Optional[Drift]:
    led = res.ledger
    if led is None or res.fields.get("metric") != "match" or res.strength is None:
        return None
    cs = res.strength
    q_steps = cs.qualifier_rank - led.qualifier_rank
    s_steps = cs.scope_rank - led.scope_rank
    if q_steps <= 0 and s_steps <= 0:
        return None
    q_steps, s_steps = max(q_steps, 0), max(s_steps, 0)
    total = q_steps + s_steps
    severity = "high" if (max(q_steps, s_steps) >= 3 or total >= 4) else ("medium" if total >= 2 else "low")
    approved = assess(f"{led.statement} {led.qualifier or ''} {led.scope or ''}")
    parts = []
    if q_steps:
        parts.append(
            f"certainty rises from '{approved.qualifier_phrase or 'plain statement'}' "
            f"({QUALIFIER_LABELS[led.qualifier_rank]}) to '{cs.qualifier_phrase or 'plain statement'}' "
            f"({QUALIFIER_LABELS[cs.qualifier_rank]})"
        )
    if s_steps:
        parts.append(
            f"reach widens from '{approved.scope_phrase or led.scope or 'as approved'}' "
            f"({SCOPE_LABELS[led.scope_rank]}) to '{cs.scope_phrase or 'no stated limit'}' "
            f"({SCOPE_LABELS[cs.scope_rank]})"
        )
    template = (
        f"This draft has drifted from approved fact {led.claim_key}: " + " and ".join(parts)
        + f". Approved wording: '{led.statement}'"
    )
    details = {
        "qualifier": {"draft_rank": cs.qualifier_rank, "draft_phrase": cs.qualifier_phrase,
                      "approved_rank": led.qualifier_rank, "steps": q_steps},
        "scope": {"draft_rank": cs.scope_rank, "draft_phrase": cs.scope_phrase,
                  "approved_rank": led.scope_rank, "steps": s_steps},
        "closest_fact": {"claim_key": led.claim_key, "statement": led.statement, "evidence_url": led.evidence_url},
    }
    return Drift(res, q_steps, s_steps, severity, template, details)
