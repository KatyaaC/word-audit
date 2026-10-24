"""Deterministic text helpers for the review engine and embedding fallback."""
import re

STOP = set(
    """a an the and or of for to in on at by with from as is are was were be been it its this that these those our
    we you your their they he she his her not no yes can will would should could may might do does did have has had
    than then so such into over under about up down out more most less least very also just only each per via using
    use used new number count total every all some any many much""".split()
)

DOWN = set(
    """cut cuts cutting reduce reduces reduced reducing reduction reductions decrease decreases decreased lower lowers
    lowered drop drops dropped fell fall falls fallen shrink shrinks decline declined declines slash slashed slashes
    minimize minimise""".split()
)
UP = set(
    """increase increases increased boost boosts boosted raise raises raised grow grows grew growth rise rises rose
    gain gains gained double doubles doubled triple triples tripled""".split()
)


def stem(w: str) -> str:
    w = w.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    return w


def canon(w: str) -> str:
    lw = w.lower()
    if lw in DOWN:
        return "reduce"
    if lw in UP:
        return "increase"
    return stem(lw)


def content_tokens(text: str) -> list:
    return [canon(w) for w in re.findall(r"[A-Za-z]+", text or "") if len(w) > 2 and w.lower() not in STOP]


def direction(tokens) -> int:
    d = 0
    if "reduce" in tokens:
        d -= 1
    if "increase" in tokens:
        d += 1
    return d


def norm_unit(u):
    if not u:
        return None
    u = u.strip().lower()
    if u in ("%", "percent", "percentage", "per cent"):
        return "%"
    if u in ("x", "×", "times"):
        return "x"
    if len(u) > 3 and u.endswith("s") and not u.endswith("ss"):
        u = u[:-1]
    return u


def norm_period(p):
    return re.sub(r"\s+", "", p.lower()) if p else None
