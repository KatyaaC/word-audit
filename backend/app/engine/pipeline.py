"""Review engine coordinating Layers A, B, and C."""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .claims import extract_claims
from .layer_a import run_layer_a
from .layer_b import BAD, ClaimResult, check_claims
from .layer_c import detect_drift
from .types import RawFinding


@dataclass
class EngineResult:
    findings: list = field(default_factory=list)
    claim_results: list = field(default_factory=list)


def _claim_finding(res: ClaimResult) -> Optional[RawFinding]:
    c, led = res.claim, res.ledger
    if res.status == "Verified":
        return None
    base = dict(layer="B", source_kind="automated_assessment", kind="claim", claim_status=res.status,
                claim_text=c.text, start=c.start, end=c.end, excerpt=c.text,
                ledger_claim_key=led.claim_key if led else None,
                details={"fields": res.fields, "reasons": res.reasons, "similarity": round(res.similarity, 3),
                         "ledger_statement": led.statement if led else None,
                         "evidence_url": led.evidence_url if led else None})
    if res.status == "Unsupported":
        return RawFinding(status="needs_verification", severity="medium", explanation=(
            "No approved fact in the Claim Ledger supports this statement. Add evidence or revise the wording."), **base)
    if res.status == "Contradicted":
        return RawFinding(status="evidence_conflict", severity="high", explanation=(
            f'The draft conflicts with approved fact {led.claim_key} ("{led.statement}"). ' + " ".join(res.reasons)),
            **base)
    bad = [k for k, v in res.fields.items() if v in BAD]
    return RawFinding(status="needs_verification", severity="medium", explanation=(
        f'Related approved fact {led.claim_key} exists ("{led.statement}"); manual review is required. '
        + " ".join(res.reasons) + (f" Fields to check: {', '.join(bad)}." if bad else "")), **base)


def _suppress_b(res: ClaimResult) -> bool:
    """Suppress Layer B findings that Layer C will already explain."""
    bad = {k for k, v in res.fields.items() if v in BAD}
    return res.status == "Uncertain" and bool(bad) and bad <= {"qualifier", "scope"}


def run_engine(session, text: str, rules: list, llm, *, classification: str = "Internal",
               external_confirmed: bool = False, today: Optional[date] = None, explain: bool = True) -> EngineResult:
    findings = run_layer_a(text, rules)
    claims = extract_claims(text, llm, classification, external_confirmed)
    results = check_claims(session, claims, today=today)
    for res in results:
        drift = detect_drift(res)
        bf = _claim_finding(res)
        if bf and drift and _suppress_b(res):
            bf = None
        if bf:
            findings.append(bf)
        if drift:
            c = res.claim
            findings.append(RawFinding(
                layer="C", source_kind="automated_assessment", kind="drift", status="evidence_conflict",
                severity=drift.severity, explanation=drift.template, ledger_claim_key=res.ledger.claim_key,
                claim_status=res.status, claim_text=c.text, start=c.start, end=c.end, excerpt=c.text,
                details=drift.details))
    if explain:
        _explain(findings, llm, classification, external_confirmed)
    findings.sort(key=lambda f: (f.start if f.start >= 0 else 10**9, f.layer))
    return EngineResult(findings, results)


def _explain(findings, llm, classification, external_confirmed):
    """Optionally rephrase deterministic explanations; retain the template on failure."""
    from ..services.llm import LLMError

    for f in findings:
        if f.source_kind != "automated_assessment":
            continue
        try:
            out = llm.run("explain", {"template": f.explanation, "claim": f.claim_text, "status": f.claim_status},
                          classification=classification, external_confirmed=external_confirmed)
            text = out.get("explanation") if isinstance(out, dict) else None
            if isinstance(text, str) and text.strip():
                f.explanation = text.strip()
        except LLMError:
            pass
