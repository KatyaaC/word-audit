/**
 * Shared contract between the frontend and the FastAPI backend.
 * Python mirrors: services/layer_a/models.py (Layer A) and Sudiksha's schemas (Layer B/C, Passport).
 * See docs/API_CONTRACT.md. Change both sides together.
 */

export type Role = "creator" | "reviewer" | "approver" | "brand_manager";

export const ROLE_LABEL: Record<Role, string> = {
  creator: "Creator",
  reviewer: "Reviewer",
  approver: "Approver",
  brand_manager: "Brand Manager",
};

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

// ---------- Findings ----------

export type Severity = "low" | "medium" | "high";
export type FindingLayer = "A" | "B" | "C";
export type FindingSource = "fixed_check" | "automated_assessment";
export type FindingStatus = "rule_violation" | "evidence_conflict" | "needs_verification";
export type ClaimStatus = "verified" | "contradicted" | "unsupported" | "uncertain";
export type Decision = "accepted" | "modified" | "rejected";
export type FixType = "replace" | "insert" | "advice";

export interface Span {
  start: number;
  end: number;
}

export interface FindingResponse {
  decision: Decision;
  reason: string;
  modified_text?: string | null;
  by: string;
  at: string;
}

export interface Finding {
  id: string;
  layer: FindingLayer;
  kind: string;
  source: FindingSource;
  status: FindingStatus;
  rule_id?: string | null;
  rule_version?: string | null;
  fact_id?: string | null;
  severity: Severity;
  message: string;
  explanation: string;
  span?: Span | null;
  matched_text?: string | null;
  fix_type?: FixType | null;
  suggestion?: string | null;
  /** Layer B/C: the suggested fix was re-run through the engine and passed. */
  suggestion_verified?: boolean | null;
  target?: string | null;
  claim_status?: ClaimStatus | null;
  response?: FindingResponse | null;
}

// ---------- Layer A ----------

export interface ColourPair {
  element: string;
  foreground: string;
  background: string;
  large_text: boolean;
}

export interface ImageRef {
  src: string;
  alt: string | null;
  decorative?: boolean;
}

export interface LayerACheckRequest {
  text: string;
  html?: string | null;
  colour_pairs: ColourPair[];
  images: ImageRef[];
}

export interface LayerACheckResponse {
  rule_pack_version: string;
  checked_at: string;
  findings: Finding[];
  counts: Record<string, number>;
}

export interface TermRule {
  id: string;
  kind: "banned" | "required";
  terms: string[];
  severity: Severity;
  match: "exact" | "lemma";
  case_sensitive?: boolean;
  when_any?: string[];
  replacement: string | null;
  reason: string;
  source_ref: string;
}

export interface RulePack {
  brand: string;
  version: string;
  terms: TermRule[];
  tone: {
    max_exclamations: number;
    exclamation_rule_id: string;
    shouting_rule_id: string;
    shouting_min_length: number;
    allowed_acronyms: string[];
    severity: Severity;
  };
  contrast: { rule_id: string; min_ratio: number; large_text_min_ratio: number; severity: Severity };
  alt_text: { missing_rule_id: string; weak_rule_id: string; missing_severity: Severity; weak_severity: Severity };
}

// ---------- Claims (Layer B / C) ----------

export interface ClaimParts {
  metric: string;
  value: string;
  population: string;
  conditions: string;
  period: string;
}

/** A strength ladder from Layer C: steps go from weakest to strongest wording. */
export interface StrengthLadder {
  name: string;
  steps: string[];
  draft_index: number;
  ledger_index: number;
}

export interface ClaimDiff {
  claim_id: string;
  status: ClaimStatus;
  draft_text: string;
  draft: ClaimParts;
  ledger_fact_id: string | null;
  ledger_text: string | null;
  ledger: ClaimParts | null;
  ladders: StrengthLadder[];
  explanation: string;
}

// ---------- Content and workflow ----------

export type ContentState =
  | "draft"
  | "in_review"
  | "changes_requested"
  | "awaiting_approval"
  | "approved"
  | "needs_rereview";

export type WorkflowAction = "submit" | "forward" | "request_changes" | "approve";

export interface ContentVersion {
  version: number;
  text: string;
  html?: string | null;
  author: string;
  created_at: string;
  rule_pack_version: string;
}

export interface Comment {
  id: string;
  author: string;
  role: Role;
  body: string;
  at: string;
}

export interface AuditEvent {
  at: string;
  actor: string;
  action: string;
  detail?: string | null;
}

export interface ContentItem {
  id: string;
  title: string;
  state: ContentState;
  author_id: string;
  author_name: string;
  versions: ContentVersion[];
  /** Findings for the latest version only. */
  findings: Finding[];
  claims: ClaimDiff[];
  comments: Comment[];
  audit: AuditEvent[];
  passport_id?: string | null;
  updated_at: string;
}

export interface ContentSubmission {
  title: string;
  text: string;
  html?: string | null;
  colour_pairs: ColourPair[];
  images: ImageRef[];
}

// ---------- Passport ----------

export type PassportStatus = "valid" | "needs_rereview" | "revoked";

export interface EvidenceSnapshot {
  fact_id: string;
  text: string;
  evidence_url: string;
  expires_at: string;
}

export interface Passport {
  id: string;
  content_id: string;
  content_title: string;
  content_version: number;
  canonical_text: string;
  fingerprint: string;
  hash_algorithm: "SHA-256";
  signature: string;
  signature_algorithm: "Ed25519";
  public_key: string;
  guideline_version: string;
  evidence: EvidenceSnapshot[];
  creator: string;
  approved_by: string;
  approved_at: string;
  mode: "strict" | "solo";
  automation_disclosure: string;
  /** Never changes after approval. */
  compliant_as_of: string;
  /** Can change later, e.g. when a supporting fact expires. */
  current_status: PassportStatus;
  current_status_reason?: string | null;
  /** Brand rules version in force today; differs from guideline_version when rules changed since approval. */
  rules_version_now?: string | null;
}

export interface VerifyResult {
  passport_id: string;
  signature_valid: boolean;
  fingerprint_match: boolean;
  computed_fingerprint: string;
  expected_fingerprint: string;
  current_status: PassportStatus;
  checked_at: string;
}

// ---------- Brand Constitution ----------

export type Classification = "public" | "internal" | "restricted";

export interface Rule {
  id: string;
  title: string;
  kind: "banned_term" | "required_term" | "tone" | "visual" | "claim" | "accessibility";
  severity: Severity;
  owner: string;
  source_doc: string;
  source_page: number | null;
  source_passage: string;
  pass_examples: string[];
  fail_examples: string[];
  status: "draft" | "active" | "rejected";
  version: number;
  drafted_by: "software" | "human";
  decided_by?: string | null;
  decision_reason?: string | null;
}

export interface ConstitutionDoc {
  id: string;
  filename: string;
  classification: Classification;
  uploaded_at: string;
  uploaded_by: string;
  rules: Rule[];
}

export interface Constitution {
  version: string;
  documents: ConstitutionDoc[];
}

// ---------- Insights ----------

export type ImpactNodeKind = "fact" | "content" | "passport";

export interface ImpactNode {
  id: string;
  kind: ImpactNodeKind;
  label: string;
  status: "ok" | "expired" | "flagged";
}

export interface ImpactEdge {
  source: string;
  target: string;
}

export interface Insights {
  repeated_mistakes: { rule_id: string; label: string; count: number }[];
  findings_per_week: { week: string; layer_a: number; layer_b: number; layer_c: number }[];
  confusing_rules: { rule_id: string; label: string; override_rate: number }[];
  expiring_facts: { fact_id: string; label: string; days_left: number }[];
  impact: { nodes: ImpactNode[]; edges: ImpactEdge[] };
}

export interface ExpireFactResult {
  fact_id: string;
  flagged_content: string[];
  flagged_passports: string[];
}

// ---------- Claim Ledger (improvement 3) ----------

export type FactStatus = "active" | "expired" | "superseded";

export interface Fact {
  id: string;
  statement: string;
  metric: string;
  value: number | null;
  unit: string | null;
  qualifier: string | null;
  scope: string | null;
  period: string | null;
  evidence_url: string;
  owner: string;
  expires_on: string | null;
  status: FactStatus;
  version: number;
  /** Negative once the expiry date has passed; null when there is no expiry date. */
  days_left: number | null;
  used_by_content: string[];
  used_by_passports: string[];
  updated_at: string;
}

export type FactPatch = Partial<
  Pick<Fact, "statement" | "metric" | "value" | "unit" | "qualifier" | "scope" | "period" | "evidence_url" | "owner" | "expires_on" | "status">
>;

export interface FactUpdateResult {
  fact: Fact;
  changed: string[];
  flagged_content: string[];
  flagged_passports: string[];
}

// ---------- Rule health (Guideline Linter) ----------

export interface LintFinding {
  kind: "ambiguity" | "conflict";
  method: string;
  score: number | null;
  explanation: string;
  rules: { key: string; id: string | null; text: string }[];
  vague_terms: string[];
}

export interface LintResult {
  findings: LintFinding[];
  rules_checked: number;
  checked_at: string;
}
