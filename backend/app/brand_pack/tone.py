"""Simple, deterministic tone rules: exclamation overuse and all-caps shouting."""
from __future__ import annotations

import re

from .models import Span


def exclamation_excess(text: str, max_allowed: int) -> tuple[Span, int] | None:
    """Return the span of the first excess run of '!' and the total count, or None."""
    positions = [i for i, c in enumerate(text) if c == "!"]
    if len(positions) <= max_allowed:
        return None
    start = positions[max_allowed]
    end = start
    while end < len(text) and text[end] == "!":
        end += 1
    return Span(start=start, end=end), len(positions)


def shouting_words(text: str, min_length: int, allowed: list[str]) -> list[tuple[Span, str]]:
    allowed_set = {a.upper() for a in allowed}
    pattern = re.compile(rf"\b[A-Z]{{{min_length},}}\b")
    out: list[tuple[Span, str]] = []
    for m in pattern.finditer(text):
        if m.group(0) in allowed_set:
            continue
        out.append((Span(start=m.start(), end=m.end()), m.group(0)))
    return out
