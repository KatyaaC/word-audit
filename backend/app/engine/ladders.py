"""Deterministic strength scales for claim qualifiers and scope."""
import re
from dataclasses import dataclass
from typing import Optional

QUALIFIER_LABELS = [
    "hedged (may / could)",
    "bounded (up to / at most)",
    "typical (on average / typically)",
    "plain statement",
    "definitive (guaranteed / always / proven)",
]
SCOPE_LABELS = [
    "study-bound (pilot / trial)",
    "specific segment (some customers)",
    "general (most customers / unspecified)",
    "universal (every customer / all users)",
]
DEFAULT_QUALIFIER_RANK = 3
DEFAULT_SCOPE_RANK = 2


def _c(patterns):
    return [re.compile(p, re.I) for p in patterns]


HEDGED = _c([r"\bmay\b", r"\bmight\b", r"\bcould\b", r"\bcan help\b", r"\bpotentially\b", r"\bin some cases\b",
             r"\bhas the potential\b"])
BOUNDED = _c([r"\bup to\b", r"\bas much as\b", r"\bas high as\b", r"\bat most\b", r"\bno more than\b",
              r"\bmaximum of\b"])
TYPICAL = _c([r"\btypically\b", r"\bon average\b", r"\baverage of\b", r"\busually\b", r"\bapproximately\b",
              r"\broughly\b", r"\baround\s+\d", r"\babout\s+\d"])
PLAIN_MARK = _c([r"\bat least\b", r"\bmore than\b", r"\bover\s+\d", r"\d\s*\+"])
STRONG_DEF = _c([r"\bguarantee[sd]?\b", r"\balways\b", r"\bproven\b", r"\bensures?\b", r"\bnever fails?\b",
                 r"\bevery time\b", r"\bwithout fail\b", r"\bdefinitely\b", r"\b100\s*%"])
WEAK_DEF = _c([r"\bwill\s+(?:reduce|cut|increase|improve|save|deliver|boost|double|triple|grow|lower|raise|"
               r"eliminate|transform|make)\b"])
MIN_CMP = _c([r"\bat least\b", r"\bmore than\b", r"\bover\s+\d", r"\d\s*\+", r"\bexceed(?:s|ing)?\b",
              r"\babove\s+\d"])

STUDY = _c([r"\bpilot\b", r"\bin (?:our|the|a) (?:study|trial|test|beta|experiment)\b", r"\bstudy participants\b",
            r"\btrial participants\b", r"\bin testing\b", r"\bin (?:lab|clinical) (?:tests?|trials?|conditions)\b",
            r"\bparticipants\b"])
SEGMENT = _c([r"\b(?:some|select(?:ed)?|certain|specific|several) (?:customers?|users?|clients?|teams?|cases|sites|"
              r"stores|patients)\b", r"\bin some\b", r"\bfor teams like\b"])
GENERAL = _c([r"\bmost (?:customers?|users?|clients?|teams?)\b", r"\bmany (?:customers?|users?|clients?|teams?)\b",
              r"\bthe typical (?:customer|user)\b"])
UNIVERSAL = _c([r"\bevery(?:one|body)?\b", r"\ball (?:of our )?(?:customers?|users?|clients?|teams?|patients|people|"
                r"organi[sz]ations|businesses)\b", r"\bany (?:customer|user|client|team|business)\b",
                r"\beach (?:customer|user|client)\b", r"\banyone\b", r"\bacross the board\b", r"\bfor all\b"])


def _hit(patterns, text):
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(0)
    return None


@dataclass(frozen=True)
class Strength:
    qualifier_rank: int
    qualifier_phrase: Optional[str]
    scope_rank: int
    scope_phrase: Optional[str]

    @property
    def qualifier_label(self) -> str:
        return QUALIFIER_LABELS[self.qualifier_rank]

    @property
    def scope_label(self) -> str:
        return SCOPE_LABELS[self.scope_rank]


def assess(text: str) -> Strength:
    text = text or ""
    strong, weak = _hit(STRONG_DEF, text), _hit(WEAK_DEF, text)
    hedged, bounded, typical = _hit(HEDGED, text), _hit(BOUNDED, text), _hit(TYPICAL, text)
    plain = _hit(PLAIN_MARK, text)
    if strong:
        q = (4, strong)
    elif hedged:
        q = (0, hedged)
    elif bounded:
        q = (1, bounded)
    elif typical:
        q = (2, typical)
    elif weak:
        q = (4, weak)
    else:
        q = (DEFAULT_QUALIFIER_RANK, plain)

    study, universal = _hit(STUDY, text), _hit(UNIVERSAL, text)
    general, segment = _hit(GENERAL, text), _hit(SEGMENT, text)
    if study:
        s = (0, study)
    elif universal:
        s = (3, universal)
    elif general:
        s = (2, general)
    elif segment:
        s = (1, segment)
    else:
        s = (DEFAULT_SCOPE_RANK, None)
    return Strength(q[0], q[1], s[0], s[1])


def comparator_of(text: str) -> str:
    """How a number in this text is bounded: max (up to), min (at least), approx, or exact."""
    if _hit(BOUNDED, text):
        return "max"
    if _hit(MIN_CMP, text):
        return "min"
    if _hit(TYPICAL, text):
        return "approx"
    return "exact"


def comparators_compatible(claim_cmp: str, ledger_cmp: str) -> bool:
    if claim_cmp == ledger_cmp:
        return True
    if ledger_cmp == "exact":
        return claim_cmp in ("max", "min", "approx")
    if ledger_cmp == "approx":
        return claim_cmp == "exact"
    return False  # ledger says "up to"/"at least"; a different kind of claim is not covered
