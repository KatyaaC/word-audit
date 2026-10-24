from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawFinding:
    layer: str
    source_kind: str
    kind: str
    status: str
    severity: str
    explanation: str
    rule_key: Optional[str] = None
    ledger_claim_key: Optional[str] = None
    claim_status: Optional[str] = None
    claim_text: Optional[str] = None
    start: int = -1
    end: int = -1
    excerpt: str = ""
    details: dict = field(default_factory=dict)

    def signature(self) -> tuple:
        ref = (self.claim_text or self.excerpt or "").strip().lower()
        return (self.layer, self.kind, self.rule_key, self.ledger_claim_key, ref)

    def overlaps(self, span) -> bool:
        if self.start < 0 or span is None:
            return False
        return self.start < span[1] and span[0] < self.end
