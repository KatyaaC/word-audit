"""WCAG 2.x colour contrast.

Contrast ratio = (L1 + 0.05) / (L2 + 0.05), where L1 is the lighter relative
luminance. AA requires 4.5:1 for normal text and 3:1 for large text
(18pt+, or 14pt+ bold).
"""
from __future__ import annotations

import re

_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB = re.compile(r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")


def parse_colour(value: str) -> tuple[int, int, int]:
    v = value.strip()
    m = _HEX.match(v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    m = _RGB.match(v)
    if m:
        r, g, b = (min(255, int(x)) for x in m.groups())
        return r, g, b
    raise ValueError(f"Unsupported colour: {value!r}. Use #rgb, #rrggbb or rgb(r, g, b).")


def _channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    l1 = relative_luminance(parse_colour(foreground))
    l2 = relative_luminance(parse_colour(background))
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)
