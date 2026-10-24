"""Claim extraction from text, with LLM primary path and deterministic heuristic fallback."""
import re
from typing import Optional

from pydantic import BaseModel, ValidationError

from .ladders import STRONG_DEF, assess
from .textutil import STOP, content_tokens, direction, norm_unit


class ParsedClaim(BaseModel):
    text: str
    metric: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    qualifier: Optional[str] = None
    scope: Optional[str] = None
    conditions: Optional[str] = None
    period: Optional[str] = None
    start: int = -1
    end: int = -1


_MULT = {"k": 1e3, "thousand": 1e3, "lakh": 1e5, "lakhs": 1e5, "m": 1e6, "million": 1e6, "crore": 1e7,
         "crores": 1e7, "billion": 1e9}
_NUM = re.compile(
    r"(?<![A-Za-z\d.,])(\d[\d,]*(?:\.\d+)?)\+?(?:\s*(k|m|thousand|lakhs?|million|crores?|billion)\b)?"
    r"\s*(%|percent\b|per cent\b|×|x\b|[A-Za-z][A-Za-z\-]*)?",
    re.I,
)
_UNIT_STOP = {"in", "of", "for", "by", "and", "to", "on", "at", "with", "from", "as", "is", "are", "the", "a", "an",
              "per", "or", "than", "that", "which", "across", "among", "after", "before", "over", "under",
              "within", "during", "when", "while", "if", "it", "its", "our", "we"}
_PERIOD = re.compile(
    r"\b(?:Q[1-4]\s*(?:FY)?\s*\d{2,4}|FY\s?\d{2,4}|H[12]\s*\d{4}|(?:19|20)\d{2}|last (?:year|quarter|month)|this year)\b",
    re.I,
)
_SUPERLATIVE = re.compile(r"\b(best|#1|number one|leading|fastest|safest|cheapest|world'?s|only|first|cure[sd]?|"
                          r"prevent[s]?|clinically|risk[- ]free)\b", re.I)
_YEAR = re.compile(r"^(19|20)\d{2}$")


def split_sentences(text: str):
    """Yield sentences with character offsets."""
    pos = 0
    for line in text.split("\n"):
        for m in re.finditer(r"\S.*?(?:(?<=[.!?])(?=\s|$)|$)", line):
            s = m.group(0).rstrip()
            if s:
                yield s, pos + m.start(), pos + m.start() + len(s)
        pos += len(line) + 1


def _first_value(sentence: str):
    for m in _NUM.finditer(sentence):
        raw, mult, unit = m.group(1), m.group(2), m.group(3)
        if _YEAR.match(raw) and not mult and unit != "%":
            continue
        value = float(raw.replace(",", ""))
        if mult:
            value *= _MULT[mult.lower()]
        if unit and unit.lower() in _UNIT_STOP:
            unit = None
        return value, norm_unit(unit)
    return None, None


def heuristic_extract(text: str) -> list:
    claims = []
    for sent, start, end in split_sentences(text):
        value, unit = _first_value(sent)
        is_claim = value is not None or any(p.search(sent) for p in STRONG_DEF) or _SUPERLATIVE.search(sent)
        if not is_claim:
            continue
        st = assess(sent)
        period = _PERIOD.search(sent)
        claims.append(ParsedClaim(
            text=sent, metric=" ".join(content_tokens(sent)) or None, value=value, unit=unit,
            qualifier=st.qualifier_phrase, scope=st.scope_phrase,
            period=period.group(0) if period else None, start=start, end=end,
        ))
    return claims


def metrics_match(a: Optional[str], b: Optional[str]) -> str:
    if not a or not b:
        return "unknown"
    ta, tb = set(content_tokens(a)), set(content_tokens(b))
    if not ta or not tb:
        return "unknown"
    da, db = direction(ta), direction(tb)
    if da and db and da != db:
        return "mismatch"
    inter = ta & tb
    if not (inter - {"reduce", "increase"}):
        return "mismatch"
    smaller = min(len(ta), len(tb))
    if len(inter) / smaller >= 0.5 and (len(inter) >= 2 or smaller == 1):
        return "match"
    return "mismatch"


def _locate(text: str, pc: ParsedClaim):
    """Locate an extracted claim within the source text."""
    idx = text.find(pc.text)
    if idx >= 0:
        return idx, idx + len(pc.text), pc.text
    want = set(content_tokens(pc.text))
    best, best_score = None, 0.0
    for sent, s, e in split_sentences(text):
        have = set(content_tokens(sent))
        if not want or not have:
            continue
        score = len(want & have) / len(want | have)
        if score > best_score:
            best, best_score = (s, e, sent), score
    return best if best and best_score >= 0.4 else None


def extract_claims(text: str, llm, classification: str = "Internal", external_confirmed: bool = False) -> list:
    from ..services.llm import LLMError

    try:
        out = llm.run("extract_claims", {"text": text}, classification=classification,
                      external_confirmed=external_confirmed)
    except LLMError:
        return heuristic_extract(text)
    raw = out.get("claims") if isinstance(out, dict) else None
    if not isinstance(raw, list):
        return heuristic_extract(text)
    claims = []
    for c in raw:
        try:
            pc = ParsedClaim(**{k: v for k, v in c.items() if k in ParsedClaim.model_fields})
        except (ValidationError, AttributeError, TypeError):
            continue
        loc = _locate(text, pc)
        if loc:
            pc.start, pc.end, pc.text = loc
            claims.append(pc)
    if raw and not claims:
        return heuristic_extract(text)
    return claims
