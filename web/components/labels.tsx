import { Badge } from "@/components/ui/primitives";
import type { ClaimStatus, ContentState, Finding, PassportStatus, Severity } from "@/lib/types";

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge variant={severity}>{severity}</Badge>;
}

const STATE: Record<ContentState, { label: string; v: "muted" | "low" | "warning" | "violet" | "success" | "high" }> = {
  draft: { label: "Draft", v: "muted" },
  in_review: { label: "In review", v: "low" },
  changes_requested: { label: "Changes requested", v: "warning" },
  awaiting_approval: { label: "Awaiting approval", v: "violet" },
  approved: { label: "Approved", v: "success" },
  needs_rereview: { label: "Needs another look", v: "high" },
};

export function StateBadge({ state }: { state: ContentState }) {
  const s = STATE[state];
  return <Badge variant={s.v}>{s.label}</Badge>;
}

const CLAIM: Record<ClaimStatus, { label: string; v: "success" | "high" | "warning" | "violet" }> = {
  verified: { label: "Verified", v: "success" },
  contradicted: { label: "Contradicted", v: "high" },
  unsupported: { label: "Unsupported", v: "warning" },
  uncertain: { label: "Uncertain", v: "violet" },
};

export function ClaimStatusBadge({ status }: { status: ClaimStatus }) {
  const s = CLAIM[status];
  return <Badge variant={s.v}>{s.label}</Badge>;
}

export function SourceBadge({ finding }: { finding: Finding }) {
  return finding.source === "fixed_check" ? (
    <Badge variant="outline">Brand rule</Badge>
  ) : (
    <Badge variant="violet">Automated claim check</Badge>
  );
}

const FSTATUS: Record<Finding["status"], string> = {
  rule_violation: "Breaks a rule",
  evidence_conflict: "Doesn't match the evidence",
  needs_verification: "Needs a source",
};

export function FindingStatusBadge({ finding }: { finding: Finding }) {
  return <Badge variant="muted">{FSTATUS[finding.status]}</Badge>;
}

export function PassportStatusBadge({ status }: { status: PassportStatus }) {
  if (status === "valid") return <Badge variant="success">Still valid</Badge>;
  if (status === "needs_rereview") return <Badge variant="high">Needs another look</Badge>;
  return <Badge variant="high">Revoked</Badge>;
}
