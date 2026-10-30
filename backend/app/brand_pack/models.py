"""Pydantic models for Layer A (fixed, deterministic checks).

These shapes are mirrored in web/lib/types.ts. Change both together.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingKind(str, Enum):
    BANNED_TERM = "banned_term"
    REQUIRED_TERM_MISSING = "required_term_missing"
    TONE_EXCLAMATION = "tone_exclamation"
    TONE_SHOUTING = "tone_shouting"
    LOW_CONTRAST = "low_contrast"
    MISSING_ALT_TEXT = "missing_alt_text"
    WEAK_ALT_TEXT = "weak_alt_text"


class Span(BaseModel):
    """Character offsets into the plain text that was checked (end is exclusive)."""

    start: int
    end: int


class Finding(BaseModel):
    id: str
    layer: Literal["A"] = "A"
    kind: FindingKind
    source: Literal["fixed_check"] = "fixed_check"
    status: Literal["rule_violation"] = "rule_violation"
    rule_id: str
    rule_version: str
    severity: Severity
    message: str
    explanation: str
    span: Span | None = None
    matched_text: str | None = None
    # replace: swap span for `suggestion`; insert: add `suggestion`; advice: guidance only
    fix_type: Literal["replace", "insert", "advice"] = "advice"
    suggestion: str | None = None
    # For findings that are not tied to text (an image src, a UI element name)
    target: str | None = None


# ---------- Rule pack ----------


class TermRule(BaseModel):
    id: str
    kind: Literal["banned", "required"]
    terms: list[str] = Field(min_length=1)
    severity: Severity = Severity.MEDIUM
    match: Literal["exact", "lemma"] = "exact"
    case_sensitive: bool = False
    # Required rules only apply when one of these trigger words appears
    when_any: list[str] = Field(default_factory=list)
    replacement: str | None = None
    reason: str
    source_ref: str


class ToneRules(BaseModel):
    max_exclamations: int = 1
    exclamation_rule_id: str = "TONE-001"
    shouting_rule_id: str = "TONE-002"
    shouting_min_length: int = 4
    allowed_acronyms: list[str] = Field(default_factory=list)
    severity: Severity = Severity.LOW


class ContrastRules(BaseModel):
    rule_id: str = "A11Y-001"
    min_ratio: float = 4.5  # WCAG 2.x AA, normal text
    large_text_min_ratio: float = 3.0  # WCAG 2.x AA, large text
    severity: Severity = Severity.HIGH


class AltTextRules(BaseModel):
    missing_rule_id: str = "A11Y-002"
    weak_rule_id: str = "A11Y-003"
    missing_severity: Severity = Severity.HIGH
    weak_severity: Severity = Severity.MEDIUM


class RulePack(BaseModel):
    brand: str
    version: str
    terms: list[TermRule]
    tone: ToneRules = Field(default_factory=ToneRules)
    contrast: ContrastRules = Field(default_factory=ContrastRules)
    alt_text: AltTextRules = Field(default_factory=AltTextRules)


# ---------- Request / response ----------


class ColourPair(BaseModel):
    element: str
    foreground: str
    background: str
    large_text: bool = False


class ImageRef(BaseModel):
    src: str
    alt: str | None = None  # None means the alt attribute is missing
    decorative: bool = False


class CheckRequest(BaseModel):
    text: str = ""
    html: str | None = None
    colour_pairs: list[ColourPair] = Field(default_factory=list)
    images: list[ImageRef] = Field(default_factory=list)


class CheckResponse(BaseModel):
    rule_pack_version: str
    checked_at: datetime
    findings: list[Finding]
    counts: dict[str, int]
