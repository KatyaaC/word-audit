"""Layer A: fixed rule checks (banned terms, required terms). Extension point for additional accessibility checks."""
import re

from .types import RawFinding


def run_layer_a(text: str, rules: list) -> list:
    out = []
    for r in rules:
        if r.status != "active":
            continue
        terms = (r.pattern or {}).get("terms", [])
        if r.kind == "banned_term":
            for t in terms:
                for m in re.finditer(rf"(?<!\w){re.escape(t)}(?!\w)", text, re.I):
                    out.append(RawFinding(
                        layer="A", source_kind="fixed_check", kind="banned_term", status="rule_violation",
                        severity=r.severity, rule_key=r.rule_key, start=m.start(), end=m.end(),
                        excerpt=m.group(0), explanation=f'Banned term "{t}" (rule {r.rule_key}): {r.text}',
                        details={"term": t, "rule_text": r.text, "source_ref": r.source_ref}))
        elif r.kind == "required_term":
            when = (r.pattern or {}).get("when")
            if when and not re.search(when, text, re.I):
                continue
            for t in terms:
                if not re.search(rf"(?<!\w){re.escape(t)}(?!\w)", text, re.I):
                    out.append(RawFinding(
                        layer="A", source_kind="fixed_check", kind="required_term", status="rule_violation",
                        severity=r.severity, rule_key=r.rule_key, excerpt=t,
                        explanation=f'Required wording "{t}" is missing (rule {r.rule_key}): {r.text}',
                        details={"term": t, "rule_text": r.text, "source_ref": r.source_ref}))
    return out
