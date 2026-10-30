"""Layer A engine: runs every fixed check and returns findings.

No language model is involved anywhere in this module. Given the same input
and rule pack version, the output is always the same.
"""
from __future__ import annotations

import hashlib

from . import alt_text, contrast, tone
from .models import (
    CheckRequest,
    Finding,
    FindingKind,
    ImageRef,
    RulePack,
    Severity,
)
from .terms import contains_any, find_rule

_SEVERITY_RANK = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


def _fid(*parts: object) -> str:
    return "A-" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


def _check_terms(text: str, pack: RulePack) -> list[Finding]:
    out: list[Finding] = []
    for rule in pack.terms:
        if rule.kind == "banned":
            for sp in find_rule(text, rule):
                matched = text[sp.start : sp.end]
                out.append(
                    Finding(
                        id=_fid(rule.id, sp.start, sp.end),
                        kind=FindingKind.BANNED_TERM,
                        rule_id=rule.id,
                        rule_version=pack.version,
                        severity=rule.severity,
                        message=f'Try to avoid "{matched}" here.',
                        explanation=f"{rule.reason} (From: {rule.source_ref}.)",
                        span=sp,
                        matched_text=matched,
                        fix_type="replace" if rule.replacement else "advice",
                        suggestion=rule.replacement,
                    )
                )
        else:  # required
            triggers = contains_any(text, rule.when_any) if rule.when_any else []
            applies = not rule.when_any or bool(triggers)
            if applies and not find_rule(text, rule):
                why = f' You mentioned: {", ".join(triggers)}.' if triggers else ""
                out.append(
                    Finding(
                        id=_fid(rule.id, "missing"),
                        kind=FindingKind.REQUIRED_TERM_MISSING,
                        rule_id=rule.id,
                        rule_version=pack.version,
                        severity=rule.severity,
                        message=f'This needs to include "{rule.terms[0]}".',
                        explanation=f"{rule.reason}{why} (From: {rule.source_ref}.)",
                        fix_type="insert",
                        suggestion=rule.terms[0] + ".",
                    )
                )
    return out


def _check_tone(text: str, pack: RulePack) -> list[Finding]:
    t = pack.tone
    out: list[Finding] = []
    excess = tone.exclamation_excess(text, t.max_exclamations)
    if excess:
        sp, count = excess
        out.append(
            Finding(
                id=_fid(t.exclamation_rule_id, sp.start),
                kind=FindingKind.TONE_EXCLAMATION,
                rule_id=t.exclamation_rule_id,
                rule_version=pack.version,
                severity=t.severity,
                message=f"That's {count} exclamation marks. We keep it to {t.max_exclamations}.",
                explanation="Our voice is calm and confident. A run of exclamation marks can come across as pushy.",
                span=sp,
                matched_text=text[sp.start : sp.end],
                fix_type="replace",
                suggestion="",
            )
        )
    for sp, word in tone.shouting_words(text, t.shouting_min_length, t.allowed_acronyms):
        out.append(
            Finding(
                id=_fid(t.shouting_rule_id, sp.start),
                kind=FindingKind.TONE_SHOUTING,
                rule_id=t.shouting_rule_id,
                rule_version=pack.version,
                severity=t.severity,
                message=f'"{word}" reads like shouting.',
                explanation="Try normal sentence case instead. Approved acronyms like SEBI are fine.",
                span=sp,
                matched_text=word,
                fix_type="replace",
                suggestion=word.capitalize() if sp.start == 0 else word.lower(),
            )
        )
    return out


def _check_contrast(req: CheckRequest, pack: RulePack) -> list[Finding]:
    c = pack.contrast
    out: list[Finding] = []
    for pair in req.colour_pairs:
        try:
            ratio = contrast.contrast_ratio(pair.foreground, pair.background)
        except ValueError as exc:
            out.append(
                Finding(
                    id=_fid(c.rule_id, pair.element, "parse"),
                    kind=FindingKind.LOW_CONTRAST,
                    rule_id=c.rule_id,
                    rule_version=pack.version,
                    severity=Severity.LOW,
                    message=f"We couldn't read the colours for {pair.element}.",
                    explanation=str(exc),
                    target=pair.element,
                )
            )
            continue
        required = c.large_text_min_ratio if pair.large_text else c.min_ratio
        if ratio < required:
            out.append(
                Finding(
                    id=_fid(c.rule_id, pair.element, pair.foreground, pair.background),
                    kind=FindingKind.LOW_CONTRAST,
                    rule_id=c.rule_id,
                    rule_version=pack.version,
                    severity=c.severity,
                    message=(
                        f"{pair.element} may be hard to read: the contrast is {ratio:.2f}:1 "
                        f"and it needs at least {required}:1."
                    ),
                    explanation=(
                        "Low-contrast text is hard for many people to read, especially on a phone outdoors. "
                        "WCAG AA asks for 4.5:1 for normal text and 3:1 for large text."
                    ),
                    target=pair.element,
                    fix_type="advice",
                    suggestion="Try a darker text colour or a lighter background.",
                )
            )
    return out


def _check_alt_text(req: CheckRequest, pack: RulePack) -> list[Finding]:
    a = pack.alt_text
    images: list[ImageRef] = list(req.images)
    if req.html:
        known = {i.src for i in images}
        images += [i for i in alt_text.images_from_html(req.html) if i.src not in known]
    out: list[Finding] = []
    for idx, img in enumerate(images):
        issue = alt_text.check_image(img)
        if issue is None:
            continue
        label = img.src or f"image #{idx + 1}"
        if issue == "missing":
            out.append(
                Finding(
                    id=_fid(a.missing_rule_id, img.src, idx),
                    kind=FindingKind.MISSING_ALT_TEXT,
                    rule_id=a.missing_rule_id,
                    rule_version=pack.version,
                    severity=a.missing_severity,
                    message=f"This image ({label}) has no description.",
                    explanation="People using screen readers won't know what it shows. Add a short description, or mark it as decorative.",
                    target=img.src,
                    fix_type="advice",
                    suggestion="Describe what the image shows in a few words.",
                )
            )
        else:
            detail = (
                "The description is empty, so screen readers will skip this image. That's fine only if it's purely decorative."
                if issue == "empty"
                else f'The description "{img.alt}" looks like a file name or a placeholder.'
            )
            out.append(
                Finding(
                    id=_fid(a.weak_rule_id, img.src, idx),
                    kind=FindingKind.WEAK_ALT_TEXT,
                    rule_id=a.weak_rule_id,
                    rule_version=pack.version,
                    severity=Severity.LOW if issue == "empty" else a.weak_severity,
                    message=f"This image ({label}) needs a better description.",
                    explanation=detail,
                    target=img.src,
                    fix_type="advice",
                    suggestion="Say what the image shows and why it's there, in a short phrase.",
                )
            )
    return out


def run_layer_a(req: CheckRequest, pack: RulePack) -> list[Finding]:
    findings = (
        _check_terms(req.text, pack)
        + _check_tone(req.text, pack)
        + _check_contrast(req, pack)
        + _check_alt_text(req, pack)
    )
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_RANK[f.severity], f.span.start if f.span else 10**9, f.rule_id),
    )


def count_by_severity(findings: list[Finding]) -> dict[str, int]:
    counts = {s.value: 0 for s in Severity}
    for f in findings:
        counts[f.severity.value] += 1
    counts["total"] = len(findings)
    return counts
