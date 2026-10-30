"""Banned and required term matching.

Matching is deterministic. Two paths:

* Regex (always available, and the only path the TypeScript mirror uses).
  Words are matched on hyphen-aware boundaries, and when a rule asks for
  "lemma" matching the last word may carry a simple inflection
  ("guarantee" -> "guarantees", "guaranteed", "guaranteeing").
* spaCy lemmas (used in addition when spaCy and en_core_web_sm are installed).
  Only for single-word, case-insensitive "lemma" rules. A prefix guard stops
  lemma jumps such as "best" -> "good" or "cheapest" -> "cheap".

The spaCy path is a union with the regex path, so the Python service never
reports fewer matches than the in-editor TypeScript checks.
"""
from __future__ import annotations

import re
from functools import lru_cache

from .models import Span, TermRule

BOUND_L = r"(?<![\w-])"
BOUND_R = r"(?![\w-])"


def _load_nlp():
    try:
        import spacy  # type: ignore

        return spacy.load("en_core_web_sm", disable=["parser", "ner"])
    except Exception:  # spaCy or the model is not installed
        return None


_NLP = _load_nlp()


def spacy_available() -> bool:
    return _NLP is not None


def phrase_pattern(term: str, inflect: bool) -> str:
    words = term.strip().split()
    parts = [re.escape(w) for w in words]
    last = words[-1]
    if inflect and last[-1:].isalpha():
        if last.lower().endswith("e"):
            parts[-1] = re.escape(last[:-1]) + "(?:e|es|ed|ing|eing)"
        else:
            parts[-1] = re.escape(last) + "(?:s|es|ed|ing)?"
    return BOUND_L + r"\s+".join(parts) + BOUND_R


@lru_cache(maxsize=1024)
def _compiled(term: str, inflect: bool, case_sensitive: bool) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(phrase_pattern(term, inflect), flags)


def _regex_spans(text: str, term: str, inflect: bool, case_sensitive: bool) -> list[Span]:
    return [
        Span(start=m.start(), end=m.end())
        for m in _compiled(term, inflect, case_sensitive).finditer(text)
    ]


def _is_boundary(text: str, i: int) -> bool:
    return i < 0 or i >= len(text) or not (text[i].isalnum() or text[i] in "-_")


def _lemma_spans(text: str, term: str) -> list[Span]:
    assert _NLP is not None
    doc = _NLP(text)
    t_lower = term.lower()
    t_lemma = _NLP(term)[0].lemma_.lower()
    prefix = t_lower[: max(3, len(t_lower) - 1)]
    out: list[Span] = []
    for tok in doc:
        low = tok.lower_
        if low == t_lower or (tok.lemma_.lower() == t_lemma and low.startswith(prefix)):
            s, e = tok.idx, tok.idx + len(tok.text)
            if _is_boundary(text, s - 1) and _is_boundary(text, e):
                out.append(Span(start=s, end=e))
    return out


def dedupe(spans: list[Span]) -> list[Span]:
    """Sort by start and drop spans that overlap an earlier, longer-or-equal span."""
    out: list[Span] = []
    for sp in sorted(spans, key=lambda s: (s.start, -(s.end - s.start))):
        if out and sp.start < out[-1].end:
            continue
        out.append(sp)
    return out


def find_term(text: str, term: str, rule: TermRule) -> list[Span]:
    inflect = rule.match == "lemma"
    spans = _regex_spans(text, term, inflect, rule.case_sensitive)
    if inflect and _NLP is not None and term.isalpha() and not rule.case_sensitive:
        spans += _lemma_spans(text, term)
    return dedupe(spans)


def find_rule(text: str, rule: TermRule) -> list[Span]:
    """All matches for any of the rule's terms, without overlaps."""
    spans: list[Span] = []
    for term in rule.terms:
        spans += find_term(text, term, rule)
    return dedupe(spans)


def contains_any(text: str, terms: list[str]) -> list[str]:
    """Return the trigger words that appear in the text (exact, case-insensitive)."""
    return [t for t in terms if _regex_spans(text, t, False, False)]
