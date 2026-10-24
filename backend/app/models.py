from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from .db import EmbeddingType


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(factory):
    return Field(default_factory=factory, sa_column=Column(JSON))


def _vec():
    return Field(default=None, sa_column=Column(EmbeddingType))


class ConstitutionVersion(SQLModel, table=True):
    __tablename__ = "constitution_version"
    id: Optional[int] = Field(default=None, primary_key=True)
    number: int = Field(index=True, unique=True)
    released_by: str = ""
    rule_snapshot: list = _json(list)
    created_at: str = Field(default_factory=now_iso)


class Rule(SQLModel, table=True):
    __tablename__ = "rule"
    id: Optional[int] = Field(default=None, primary_key=True)
    rule_key: str = Field(index=True)
    kind: str
    text: str
    severity: str = "medium"
    owner: str = ""
    source_ref: str = ""
    pattern: dict = _json(dict)
    examples_pass: list = _json(list)
    examples_fail: list = _json(list)
    status: str = Field(default="draft", index=True)
    drafted_by_software: bool = False
    approved_by: Optional[str] = None
    embedding: Optional[list] = _vec()
    created_at: str = Field(default_factory=now_iso)


class LedgerClaim(SQLModel, table=True):
    __tablename__ = "ledger_claim"
    id: Optional[int] = Field(default=None, primary_key=True)
    claim_key: str = Field(index=True, unique=True)
    statement: str
    metric: str = ""
    value: Optional[float] = None
    unit: Optional[str] = None
    qualifier: Optional[str] = None
    scope: Optional[str] = None
    period: Optional[str] = None
    evidence_url: str = ""
    owner: str = ""
    expires_on: Optional[str] = None
    status: str = Field(default="active", index=True)
    version: int = 1
    qualifier_rank: int = 3
    scope_rank: int = 2
    embedding: Optional[list] = _vec()
    updated_at: str = Field(default_factory=now_iso)


class Content(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    classification: str = "Internal"
    creator: str = ""
    status: str = Field(default="draft", index=True)
    current_version_no: int = 1
    flag_reason: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class ContentVersion(SQLModel, table=True):
    __tablename__ = "content_version"
    id: Optional[int] = Field(default=None, primary_key=True)
    content_id: int = Field(index=True)
    version_no: int
    text: str
    constitution_version_number: Optional[int] = None
    review_run_at: Optional[str] = None
    llm_info: dict = _json(dict)
    created_at: str = Field(default_factory=now_iso)


class Finding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content_version_id: int = Field(index=True)
    layer: str
    source_kind: str
    kind: str = ""
    status: str
    claim_status: Optional[str] = None
    severity: str = "medium"
    rule_key: Optional[str] = None
    ledger_claim_key: Optional[str] = None
    claim_text: Optional[str] = None
    span_start: int = -1
    span_end: int = -1
    excerpt: str = ""
    explanation: str = ""
    details: dict = _json(dict)
    suggested_fix: Optional[str] = None
    fix_verified: bool = False
    decision: str = "pending"
    decision_reason: Optional[str] = None
    modified_text: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None


class ClaimRecord(SQLModel, table=True):
    """Claim extracted from a content version, linked to the ledger when matched."""

    __tablename__ = "claim_record"
    id: Optional[int] = Field(default=None, primary_key=True)
    content_version_id: int = Field(index=True)
    ledger_claim_key: Optional[str] = Field(default=None, index=True)
    claim_text: str
    claim_status: str
    similarity: float = 0.0
    span_start: int = -1
    span_end: int = -1
    details: dict = _json(dict)


class Passport(SQLModel, table=True):
    id: str = Field(primary_key=True)
    content_version_id: int = Field(index=True)
    payload_json: str
    signature: str
    public_key: str
    current_status: str = "valid"
    status_reason: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    seq: int = Field(index=True, unique=True)
    ts: str
    actor: str
    action: str
    entity: str
    entity_id: str
    data: dict = _json(dict)
    prev_hash: str
    entry_hash: str
