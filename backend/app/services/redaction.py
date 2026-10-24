"""Redaction of outbound payloads. Callers must preview and confirm before external transmission."""
import re
from dataclasses import dataclass, field

PATTERNS = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("URL", re.compile(r"https?://[^\s)>\]]+")),
    ("AADHAAR", re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("CARD", re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
]
_PRESIDIO_ENTITIES = ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", "IP_ADDRESS", "IBAN_CODE"]


@dataclass
class RedactionResult:
    redacted: str
    spans: list = field(default_factory=list)
    engine: str = "regex"


def _presidio_spans(text: str):
    try:
        from presidio_analyzer import AnalyzerEngine

        results = AnalyzerEngine().analyze(text=text, entities=_PRESIDIO_ENTITIES, language="en")
        return [(r.entity_type, r.start, r.end) for r in results if r.score >= 0.5], True
    except Exception:
        return [], False


def redact(text: str, protected_terms=None) -> RedactionResult:
    found = []
    for name, rx in PATTERNS:
        found += [(name, m.start(), m.end()) for m in rx.finditer(text)]
    for term in protected_terms or []:
        if term.strip():
            found += [("PROTECTED", m.start(), m.end())
                      for m in re.finditer(re.escape(term), text, re.I)]
    extra, used_presidio = _presidio_spans(text)
    found += extra
    found.sort(key=lambda s: (s[1], -(s[2] - s[1])))
    merged = []
    for typ, s, e in found:
        if merged and s < merged[-1][2]:
            continue
        merged.append((typ, s, e))
    out, spans, last, counts = [], [], 0, {}
    for typ, s, e in merged:
        counts[typ] = counts.get(typ, 0) + 1
        ph = f"[{typ}_{counts[typ]}]"
        out.append(text[last:s])
        out.append(ph)
        spans.append({"type": typ, "start": s, "end": e, "placeholder": ph})
        last = e
    out.append(text[last:])
    return RedactionResult("".join(out), spans, "presidio+regex" if used_presidio else "regex")


def redact_payload(obj, protected_terms=None):
    """Recursively redact string values in a payload."""
    if isinstance(obj, str):
        return redact(obj, protected_terms).redacted
    if isinstance(obj, list):
        return [redact_payload(x, protected_terms) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_payload(v, protected_terms) for k, v in obj.items()}
    return obj
