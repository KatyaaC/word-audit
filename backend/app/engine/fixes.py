"""Suggested fixes that are re-validated against Layers A, B, and C before presentation."""
from collections import Counter
from typing import Optional

from ..services.llm import LLMError
from .pipeline import run_engine
from .types import RawFinding


def _verified(baseline: list, new_findings: list, old_span, new_span) -> bool:
    """Return True when the replacement introduces no new findings."""
    if any(f.overlaps(new_span) for f in new_findings):
        return False
    before = Counter(f.signature() for f in baseline if not f.overlaps(old_span))
    after = Counter(f.signature() for f in new_findings if not f.overlaps(new_span))
    return all(after[s] <= before[s] for s in after)


def _try(session, text, finding, replacement, baseline, rules, llm, **kw) -> bool:
    old_span = (finding.start, finding.end)
    new_text = text[:finding.start] + replacement + text[finding.end:]
    new_span = (finding.start, finding.start + len(replacement))
    res = run_engine(session, new_text, rules, llm, explain=False, **kw)
    return _verified(baseline, res.findings, old_span, new_span)


def suggest_fix(session, text: str, finding: RawFinding, baseline: list, rules: list, llm, ledger_by_key: dict, *,
                classification: str = "Internal", external_confirmed: bool = False, today=None,
                max_llm_attempts: int = 2) -> tuple:
    """Return a verified replacement, or (None, False) when no safe fix exists."""
    if finding.start < 0:
        return None, False  # e.g. a missing required term: no safe place to insert text automatically
    kw = dict(classification=classification, external_confirmed=external_confirmed, today=today)
    candidates = []

    if finding.kind == "banned_term":
        rule = next((r for r in rules if r.rule_key == finding.rule_key), None)
        repl = ((rule.pattern or {}).get("replacements") or {}).get(finding.excerpt.lower()) if rule else None
        if repl:
            candidates.append(repl)
    elif finding.kind in ("claim", "drift") and finding.ledger_claim_key in ledger_by_key:
        led = ledger_by_key[finding.ledger_claim_key]
        canonical = led.statement
        problems = [finding.explanation]
        for _ in range(max_llm_attempts):
            try:
                out = llm.run("propose_fix", {
                    "original": finding.excerpt, "canonical": canonical, "problems": problems,
                    "approved_fact": {"statement": led.statement, "value": led.value, "unit": led.unit,
                                      "qualifier": led.qualifier, "scope": led.scope, "period": led.period}},
                    classification=classification, external_confirmed=external_confirmed, temperature=0.2)
            except LLMError:
                break
            sentence = (out.get("sentence") or "").strip() if isinstance(out, dict) else ""
            if not sentence or sentence in candidates:
                break
            if _try(session, text, finding, sentence, baseline, rules, llm, **kw):
                return sentence, True
            problems = problems + [f'Previous rewrite "{sentence}" still failed the checks.']
            candidates.append(sentence)
        candidates = [canonical] if canonical not in candidates else [canonical]
        if _try(session, text, finding, canonical, baseline, rules, llm, **kw):
            return canonical, True
        return None, False

    for cand in candidates:
        if _try(session, text, finding, cand, baseline, rules, llm, **kw):
            return cand, True
    return None, False
