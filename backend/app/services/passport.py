"""Brand Passport: content fingerprint and Ed25519 signature for tamper-evident approval records."""
import hashlib
import json
import os
import uuid
from functools import lru_cache
from typing import Optional

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey
from sqlmodel import Session, select

from ..config import get_settings
from ..errors import NotFound
from ..models import ClaimRecord, Content, ContentVersion, LedgerClaim, Passport, now_iso
from . import audit


@lru_cache
def _signing_key() -> SigningKey:
    s = get_settings()
    if s.signing_key_hex:
        return SigningKey(bytes.fromhex(s.signing_key_hex))
    if os.path.exists(s.signing_key_path):
        return SigningKey(bytes.fromhex(open(s.signing_key_path).read().strip()))
    key = SigningKey.generate()
    with open(s.signing_key_path, "w") as fh:
        fh.write(key.encode().hex())
    return key


def public_key_hex() -> str:
    return _signing_key().verify_key.encode().hex()


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def issue_passport(session: Session, content: Content, cv: ContentVersion, *, approver: str, mode: str,
                   findings: list) -> Passport:
    keys = sorted({r.ledger_claim_key for r in session.exec(
        select(ClaimRecord).where(ClaimRecord.content_version_id == cv.id)).all() if r.ledger_claim_key})
    snapshot = []
    for k in keys:
        led = session.exec(select(LedgerClaim).where(LedgerClaim.claim_key == k)).first()
        if led:
            snapshot.append({"claim_key": led.claim_key, "version": led.version, "statement": led.statement,
                             "value": led.value, "unit": led.unit, "qualifier": led.qualifier, "scope": led.scope,
                             "period": led.period, "evidence_url": led.evidence_url, "expires_on": led.expires_on,
                             "status": led.status})
    info = cv.llm_info or {}
    payload = {
        "passport_id": uuid.uuid4().hex,
        "content_id": content.id, "content_version": cv.version_no,
        "content_fingerprint": fingerprint(cv.text), "fingerprint_algo": "sha256",
        "guideline_version": cv.constitution_version_number,
        "evidence_snapshot": snapshot,
        "creator": content.creator, "approved_by": approver,
        "approval_mode": mode,
        "automation": {"fixed_checks": "layer_a", "automated_assessment": "layers_b_c",
                       "llm_usage": info.get("usage"), "fixes_proposed": sum(1 for f in findings if f.suggested_fix),
                       "fixes_accepted": sum(1 for f in findings if f.decision == "accepted" and f.suggested_fix)},
        "findings_summary": {"total": len(findings),
                             "accepted": sum(f.decision == "accepted" for f in findings),
                             "modified": sum(f.decision == "modified" for f in findings),
                             "rejected": sum(f.decision == "rejected" for f in findings)},
        "compliant_as_of": now_iso(),
    }
    body = audit.canonical(payload)
    sig = _signing_key().sign(body.encode("utf-8")).signature.hex()
    p = Passport(id=payload["passport_id"], content_version_id=cv.id, payload_json=body, signature=sig,
                 public_key=public_key_hex())
    session.add(p)
    session.flush()
    audit.log(session, approver, "passport.issued", "passport", p.id, {"mode": mode, "content_id": content.id})
    return p


def verify_passport(session: Session, passport_id: str) -> dict:
    p = session.get(Passport, passport_id)
    if not p:
        raise NotFound("Passport not found")
    payload = json.loads(p.payload_json)
    checks = {}
    try:
        VerifyKey(bytes.fromhex(p.public_key)).verify(
            p.payload_json.encode("utf-8"), bytes.fromhex(p.signature)
        )
        checks["signature"] = True
    except (BadSignatureError, ValueError):
        checks["signature"] = False
    cv = session.get(ContentVersion, p.content_version_id)
    content = session.get(Content, cv.content_id) if cv else None
    checks["content_fingerprint"] = bool(cv) and fingerprint(cv.text) == payload["content_fingerprint"]
    checks["guideline_version"] = bool(cv) and cv.constitution_version_number == payload["guideline_version"]
    checks["latest_version"] = bool(content) and content.current_version_no == payload["content_version"]
    valid = all(checks.values())
    failed = [k for k, ok in checks.items() if not ok]
    return {
        "passport_id": p.id,
        "valid": valid,
        "checks": checks,
        "failure_reason": None if valid else "Verification failed: " + ", ".join(failed),
        "compliant_as_of": payload["compliant_as_of"],
        "current_status": p.current_status,
        "status_reason": p.status_reason,
        "approved_by": payload["approved_by"],
        "approval_mode": payload["approval_mode"],
        "guideline_version": payload["guideline_version"],
        "content_version": payload["content_version"],
        "evidence_snapshot": payload["evidence_snapshot"],
        "automation": payload["automation"],
        "public_key": p.public_key,
    }


def tamper_demo(session: Session, content_version_id: int) -> dict:
    """Alter stored content text in place for demonstration of failed verification."""
    cv = session.get(ContentVersion, content_version_id)
    if not cv:
        raise NotFound("Content version not found")
    cv.text = cv.text + " (silently edited after approval)"
    session.add(cv)
    return {"tampered_content_version_id": cv.id}
