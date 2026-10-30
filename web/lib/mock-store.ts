/**
 * In-browser mock of the backend. Lets the whole UI run before Sudiksha's
 * API is ready (NEXT_PUBLIC_USE_MOCKS=true). State is kept in localStorage so
 * a page refresh does not lose the demo.
 *
 * Layer A here is the real TypeScript mirror. Layer B/C are canned imitations
 * of Sudiksha's engine, only good enough to drive the UI. Signatures are
 * placeholders; the real Ed25519 signing happens on the backend.
 */
import { fingerprint } from "./canonical";
import { DEFAULT_RULE_PACK, runLayerALocal } from "./layer-a";
import type {
  ClaimDiff,
  ClaimParts,
  Classification,
  Constitution,
  ConstitutionDoc,
  ContentItem,
  ContentSubmission,
  Decision,
  ExpireFactResult,
  Fact,
  FactPatch,
  FactUpdateResult,
  LintResult,
  Finding,
  Insights,
  LayerACheckRequest,
  LayerACheckResponse,
  LoginResponse,
  Passport,
  Role,
  Rule,
  User,
  VerifyResult,
  WorkflowAction,
} from "./types";

// ---------- Users ----------

export const DEMO_PASSWORD = "demo1234";
export const DEMO_USERS: User[] = [
  { id: "u-creator", name: "Aanya Rao", email: "creator@wordaudit.demo", role: "creator" },
  { id: "u-reviewer", name: "Rohan Iyer", email: "reviewer@wordaudit.demo", role: "reviewer" },
  { id: "u-approver", name: "Meera Shah", email: "approver@wordaudit.demo", role: "approver" },
  { id: "u-manager", name: "Dev Malhotra", email: "manager@wordaudit.demo", role: "brand_manager" },
];

// ---------- Ledger facts (Sudiksha owns the real Claim Ledger) ----------

interface Fact_ {
  id: string;
  text: string;
  evidence_url: string;
  expires_at: string;
  expired: boolean;
  parts: ClaimParts;
}

const daysFromNow = (d: number) => new Date(Date.now() + d * 86_400_000).toISOString();
const now = () => new Date().toISOString();
const wait = (ms = 120) => new Promise((r) => setTimeout(r, ms));

function seedFacts(): Fact_[] {
  return [
    {
      id: "F-003",
      text: "48,000 active merchants use PaisaLeaf Ledger (as of June 2026).",
      evidence_url: "https://example.internal/evidence/merchant-count-jun-2026.xlsx",
      expires_at: daysFromNow(12),
      expired: false,
      parts: { metric: "Active merchants", value: "48,000", population: "All PaisaLeaf Ledger merchants", conditions: "Active in last 30 days", period: "June 2026" },
    },
    {
      id: "F-007",
      text: "Up to 60% faster reconciliation in a three-month pilot with 12 retail customers.",
      evidence_url: "https://example.internal/evidence/pilot-q1-2026.pdf",
      expires_at: daysFromNow(45),
      expired: false,
      parts: { metric: "Reconciliation time reduction", value: "Up to 60%", population: "12 retail pilot customers", conditions: "Pilot setting", period: "Q1 2026 (3 months)" },
    },
    {
      id: "F-011",
      text: "4.6 average app rating on the Play Store (September 2026).",
      evidence_url: "https://example.internal/evidence/app-rating-sep-2026.png",
      expires_at: daysFromNow(5),
      expired: false,
      parts: { metric: "App rating", value: "4.6", population: "Play Store reviewers", conditions: "Average", period: "September 2026" },
    },
  ];
}

// ---------- Canned Layer B / C ----------

const QUALIFIER_STEPS = ["may", "up to", "typically", "proven", "guaranteed"];
const SCOPE_STEPS = ["in a pilot", "selected customers", "most customers", "every customer"];

function qualifierIndex(s: string): number {
  if (/guarantee/i.test(s)) return 4;
  if (/proven|always/i.test(s)) return 3;
  if (/typically|on average/i.test(s)) return 2;
  if (/up to/i.test(s)) return 1;
  if (/\b(may|can)\b/i.test(s)) return 0;
  return 2;
}
function scopeIndex(s: string): number {
  if (/\b(every|all)\b/i.test(s)) return 3;
  if (/\bmost\b/i.test(s)) return 2;
  if (/pilot/i.test(s)) return 0;
  return 1;
}

function sentenceAround(text: string, index: number): { start: number; end: number } {
  let start = index;
  while (start > 0 && !/[.!?\n]/.test(text[start - 1])) start--;
  let end = index;
  while (end < text.length && !/[.!?\n]/.test(text[end])) end++;
  while (start < end && /\s/.test(text[start])) start++;
  return { start, end };
}

function analyseClaims(text: string, facts: Fact_[], version: string): { claims: ClaimDiff[]; findings: Finding[] } {
  const claims: ClaimDiff[] = [];
  const findings: Finding[] = [];
  const fact = (id: string) => facts.find((f) => f.id === id)!;

  // Claim 1: the 60% reconciliation claim (drift example from the proposal)
  const pct = /\b60\s?%/.exec(text);
  if (pct) {
    const sp = sentenceAround(text, pct.index);
    const sentence = text.slice(sp.start, sp.end);
    const f = fact("F-007");
    const q = qualifierIndex(sentence);
    const sc = scopeIndex(sentence);
    const drift = q > 1 || sc > 0;
    const status = f.expired ? "uncertain" : drift ? "contradicted" : "verified";
    claims.push({
      claim_id: "CL-60",
      status,
      draft_text: sentence,
      draft: {
        metric: "Reconciliation time reduction",
        value: /up to/i.test(sentence) ? "Up to 60%" : "60%",
        population: SCOPE_STEPS[sc],
        conditions: QUALIFIER_STEPS[q],
        period: /pilot/i.test(sentence) ? "Pilot" : "Not stated",
      },
      ledger_fact_id: f.id,
      ledger_text: f.text,
      ledger: f.parts,
      ladders: [
        { name: "Qualifier strength", steps: QUALIFIER_STEPS, draft_index: q, ledger_index: 1 },
        { name: "Scope", steps: SCOPE_STEPS, draft_index: sc, ledger_index: 0 },
      ],
      explanation: f.expired
        ? "The supporting fact has expired. A person needs to decide whether the claim can stay."
        : drift
          ? `The value matches ${f.id}, but ${[
              q > 1 ? `it says "${QUALIFIER_STEPS[q]}" where the evidence only supports "up to"` : null,
              sc > 0 ? `it says "${SCOPE_STEPS[sc]}" where the evidence only covers "in a pilot"` : null,
            ]
              .filter(Boolean)
              .join("; ")}.`
          : `Matches ${f.id} on value, qualifier and scope.`,
    });
    if (drift && !f.expired) {
      findings.push({
        id: "C-drift-60",
        layer: "C",
        kind: "claim_drift",
        source: "automated_assessment",
        status: "evidence_conflict",
        fact_id: f.id,
        rule_version: version,
        severity: "high",
        message: "This claim says more than the evidence supports.",
        explanation: claims[claims.length - 1].explanation,
        span: sp,
        matched_text: sentence,
        claim_status: "contradicted",
        fix_type: "replace",
        suggestion: "PaisaLeaf Ledger cut reconciliation time by up to 60% in a three-month pilot with 12 retail customers",
        suggestion_verified: true,
      });
    }
  }

  // Claim 2: merchant / customer counts
  const count = /\b(\d{1,3}(?:,\d{3})+|\d{4,})\s*\+?\s*(merchants|customers|users)\b/i.exec(text);
  if (count) {
    const f = fact("F-003");
    const value = Number(count[1].replace(/,/g, ""));
    const ok = value === 48000;
    const status = f.expired ? "uncertain" : ok ? "verified" : "contradicted";
    claims.push({
      claim_id: "CL-count",
      status,
      draft_text: count[0],
      draft: { metric: "Active merchants", value: count[1], population: count[2], conditions: "Not stated", period: "Not stated" },
      ledger_fact_id: f.id,
      ledger_text: f.text,
      ledger: f.parts,
      ladders: [],
      explanation: ok ? `Value matches ${f.id}.` : `The ledger value is 48,000 (${f.parts.period}); the draft says ${count[1]}.`,
    });
    if (!ok) {
      findings.push({
        id: "B-count",
        layer: "B",
        kind: "claim_value_mismatch",
        source: "automated_assessment",
        status: "evidence_conflict",
        fact_id: f.id,
        rule_version: version,
        severity: "high",
        message: `"${count[0]}" doesn't match the approved figure.`,
        explanation: `The field-by-field check found a different value. ${claims[claims.length - 1].explanation}`,
        span: { start: count.index, end: count.index + count[0].length },
        matched_text: count[0],
        claim_status: "contradicted",
        fix_type: "replace",
        suggestion: "48,000 merchants",
        suggestion_verified: true,
      });
    }
  }

  // Claim 3: big money figures with no ledger entry -> Unsupported
  const money = /\b(?:Rs\.?\s*|₹\s*)?(\d+(?:\.\d+)?)\s*(crore|lakh)\b/i.exec(text);
  if (money) {
    claims.push({
      claim_id: "CL-money",
      status: "unsupported",
      draft_text: money[0],
      draft: { metric: "Money amount", value: money[0], population: "Not stated", conditions: "Not stated", period: "Not stated" },
      ledger_fact_id: null,
      ledger_text: null,
      ledger: null,
      ladders: [],
      explanation: "Nothing approved backs this figure yet. That doesn't make it wrong. Someone just needs to add the evidence.",
    });
    findings.push({
      id: "B-money",
      layer: "B",
      kind: "claim_unsupported",
      source: "automated_assessment",
      status: "needs_verification",
      rule_version: version,
      severity: "medium",
      message: `We couldn't find a source for "${money[0]}".`,
      explanation: claims[claims.length - 1].explanation,
      span: { start: money.index, end: money.index + money[0].length },
      matched_text: money[0],
      claim_status: "unsupported",
      fix_type: "advice",
      suggestion: "Add the source to the Claim Ledger, or take the figure out.",
    });
  }

  return { claims, findings };
}

function analyse(sub: Pick<ContentSubmission, "text" | "html" | "colour_pairs" | "images">, facts: Fact_[]) {
  const a = runLayerALocal({ text: sub.text, html: sub.html, colour_pairs: sub.colour_pairs, images: sub.images });
  const bc = analyseClaims(sub.text, facts, DEFAULT_RULE_PACK.version);
  return { findings: [...a, ...bc.findings], claims: bc.claims };
}

// ---------- Constitution seed ----------

function packToRules(): Rule[] {
  return DEFAULT_RULE_PACK.terms.map((t) => ({
    id: t.id,
    title: t.kind === "banned" ? `Avoid: ${t.terms.join(", ")}` : `Require: "${t.terms[0]}"`,
    kind: t.kind === "banned" ? "banned_term" : "required_term",
    severity: t.severity,
    owner: "Dev Malhotra",
    source_doc: t.source_ref.split(",")[0],
    source_page: null,
    source_passage: t.reason,
    pass_examples: t.replacement ? [`... ${t.replacement} ...`] : [t.terms[0]],
    fail_examples: t.kind === "banned" ? [t.terms[0]] : ["(wording left out)"],
    status: "active",
    version: 1,
    drafted_by: "human",
  }));
}

function draftedRulesFor(filename: string, n: number): Rule[] {
  const base = filename.replace(/\.[^.]+$/, "");
  return [
    {
      id: `DR-${n}-1`,
      title: "Use sentence case in headings",
      kind: "tone",
      severity: "low",
      owner: "Unassigned",
      source_doc: filename,
      source_page: 3,
      source_passage: "Headlines should read like a sentence, not a billboard. Capitalise only the first word and proper nouns.",
      pass_examples: ["Open an account in five minutes"],
      fail_examples: ["Open An Account In Five Minutes"],
      status: "draft",
      version: 1,
      drafted_by: "software",
    },
    {
      id: `DR-${n}-2`,
      title: 'Avoid "best-in-class"',
      kind: "banned_term",
      severity: "medium",
      owner: "Unassigned",
      source_doc: filename,
      source_page: 5,
      source_passage: `${base}: We do not use unproven superlatives such as best-in-class or world-class.`,
      pass_examples: ["Rated 4.6 on the Play Store (Sep 2026)"],
      fail_examples: ["Best-in-class payments app"],
      status: "draft",
      version: 1,
      drafted_by: "software",
    },
    {
      id: `DR-${n}-3`,
      title: "Tone should be professional but friendly",
      kind: "tone",
      severity: "low",
      owner: "Unassigned",
      source_doc: filename,
      source_page: 2,
      source_passage: "Our tone is professional but friendly.",
      pass_examples: ["Thanks for waiting. Your refund is on its way."],
      fail_examples: ["Yo! Refund incoming!!!"],
      status: "draft",
      version: 1,
      drafted_by: "software",
      decision_reason: "Linter note: this phrase is ambiguous; reviewers read it differently.",
    },
  ];
}

// ---------- DB ----------

interface DB {
  seq: number;
  contents: ContentItem[];
  passports: Passport[];
  facts: Fact_[];
  constitution: Constitution;
}

const KEY = "wordaudit.mock.v1";
let db: DB | null = null;

function persist() {
  if (typeof window === "undefined" || !db) return;
  try {
    localStorage.setItem(KEY, JSON.stringify(db));
  } catch {
    /* storage full or blocked: keep in memory */
  }
}

function makeItem(
  id: string,
  title: string,
  author: User,
  state: ContentItem["state"],
  texts: string[],
  facts: Fact_[],
): ContentItem {
  const versions = texts.map((text, i) => ({
    version: i + 1,
    text,
    html: `<p>${text}</p>`,
    author: author.name,
    created_at: daysFromNow(-(texts.length - i)),
    rule_pack_version: DEFAULT_RULE_PACK.version,
  }));
  const latest = texts[texts.length - 1];
  const { findings, claims } = analyse({ text: latest, html: null, colour_pairs: [], images: [] }, facts);
  return {
    id,
    title,
    state,
    author_id: author.id,
    author_name: author.name,
    versions,
    findings,
    claims,
    comments: [],
    audit: [{ at: versions[0].created_at, actor: author.name, action: "created", detail: "Version 1" }],
    passport_id: null,
    updated_at: now(),
  };
}

async function issuePassport(d: DB, item: ContentItem, approver: User): Promise<Passport> {
  const latest = item.versions[item.versions.length - 1];
  const fp = await fingerprint(latest.text);
  const factIds = new Set(item.claims.map((c) => c.ledger_fact_id).filter(Boolean) as string[]);
  const p: Passport = {
    id: `P-${item.id.replace(/^C-/, "")}`,
    content_id: item.id,
    content_title: item.title,
    content_version: latest.version,
    canonical_text: latest.text,
    fingerprint: fp,
    hash_algorithm: "SHA-256",
    signature: `mock-ed25519:${fp.slice(0, 32)}`,
    signature_algorithm: "Ed25519",
    public_key: "mock-public-key (real key comes from the backend)",
    guideline_version: latest.rule_pack_version,
    evidence: d.facts
      .filter((f) => factIds.has(f.id))
      .map((f) => ({ fact_id: f.id, text: f.text, evidence_url: f.evidence_url, expires_at: f.expires_at })),
    creator: item.author_name,
    approved_by: approver.name,
    approved_at: now(),
    mode: "strict",
    automation_disclosure:
      "Wording checked against brand rules; claims checked automatically against approved evidence. Every decision was made by a person.",
    compliant_as_of: now(),
    current_status: "valid",
    current_status_reason: null,
  };
  d.passports = d.passports.filter((x) => x.id !== p.id).concat(p);
  item.passport_id = p.id;
  return p;
}

async function getDb(): Promise<DB> {
  if (db) return db;
  if (typeof window !== "undefined") {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        db = JSON.parse(raw) as DB;
        return db;
      }
    } catch {
      /* ignore and reseed */
    }
  }
  const facts = seedFacts();
  const creator = DEMO_USERS[0];
  const approver = DEMO_USERS[2];
  const fresh: DB = {
    seq: 200,
    facts,
    passports: [],
    contents: [
      makeItem(
        "C-101",
        "Ledger pilot results post",
        creator,
        "in_review",
        [
          "PaisaLeaf Ledger cut reconciliation time by up to 60% in a pilot. Join 48,000 merchants.",
          "PaisaLeaf Ledger guarantees 60% faster reconciliation for every customer. Join 50,000 merchants who switched this year!!",
        ],
        facts,
      ),
      makeItem(
        "C-102",
        "Pilot case study (approved)",
        creator,
        "approved",
        [
          "In a three-month pilot with 12 retail customers, PaisaLeaf Ledger reduced reconciliation time by up to 60%. Results may vary.",
        ],
        facts,
      ),
      makeItem(
        "C-103",
        "SIP launch banner",
        creator,
        "draft",
        ["Start a mutual fund SIP with PaisaLeaf from Rs 500 a month. Our app is the best in India."],
        facts,
      ),
      makeItem(
        "C-104",
        "October merchant newsletter",
        creator,
        "approved",
        ["Thank you to the 48,000 merchants who run their books on PaisaLeaf Ledger. Here is what is new this month."],
        facts,
      ),
    ],
    constitution: {
      version: DEFAULT_RULE_PACK.version,
      documents: [
        {
          id: "D-1",
          filename: "PaisaLeaf_Brand_Guidelines_v3.pdf",
          classification: "internal",
          uploaded_at: daysFromNow(-20),
          uploaded_by: "Dev Malhotra",
          rules: packToRules(),
        },
      ],
    },
  };
  for (const id of ["C-102", "C-104"]) {
    const item = fresh.contents.find((c) => c.id === id)!;
    await issuePassport(fresh, item, approver);
    item.audit.push({ at: now(), actor: approver.name, action: "approved", detail: `Passport ${item.passport_id}` });
  }
  db = fresh;
  persist();
  return db;
}

export function resetMockStore() {
  db = null;
  if (typeof window !== "undefined") localStorage.removeItem(KEY);
}

const userById = (id: string) => DEMO_USERS.find((u) => u.id === id);

function findItem(d: DB, id: string): ContentItem {
  const item = d.contents.find((c) => c.id === id);
  if (!item) throw new Error(`Content ${id} not found`);
  return item;
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;


// ---------- Ledger helpers (improvement 3) ----------

function flagDependents(d: DB, factId: string, reason: string): { content: string[]; passports: string[] } {
  const content: string[] = [];
  const passports: string[] = [];
  for (const item of d.contents) {
    if (!item.claims.some((c) => c.ledger_fact_id === factId)) continue;
    content.push(item.id);
    item.state = "needs_rereview";
    item.audit.push({ at: now(), actor: "System", action: "flagged", detail: reason });
  }
  for (const p of d.passports) {
    if (!p.evidence.some((e) => e.fact_id === factId)) continue;
    p.current_status = "needs_rereview";
    p.current_status_reason = reason;
    passports.push(p.id);
  }
  return { content, passports };
}

function factOut(d: DB, f: Fact_): Fact {
  const daysLeft = Math.round((Date.parse(f.expires_at) - Date.now()) / 86_400_000);
  return {
    id: f.id,
    statement: f.text,
    metric: f.parts.metric,
    value: Number(f.parts.value.replace(/[^\d.]/g, "")) || null,
    unit: f.parts.value.includes("%") ? "%" : null,
    qualifier: /up to/i.test(f.parts.value) ? "up to" : null,
    scope: f.parts.population,
    period: f.parts.period,
    evidence_url: f.evidence_url,
    owner: "Brand team",
    expires_on: f.expires_at.slice(0, 10),
    status: f.expired ? "expired" : "active",
    version: (f as Fact_ & { version?: number }).version ?? 1,
    days_left: daysLeft,
    used_by_content: d.contents.filter((c) => c.claims.some((cl) => cl.ledger_fact_id === f.id)).map((c) => c.id),
    used_by_passports: d.passports.filter((p) => p.evidence.some((e) => e.fact_id === f.id)).map((p) => p.id),
    updated_at: now(),
  };
}

// ---------- Mock API (same signatures as lib/api.ts) ----------

export const mock = {
  async login(email: string, password: string): Promise<LoginResponse> {
    await wait();
    const user = DEMO_USERS.find((u) => u.email === email.trim().toLowerCase());
    if (!user || password !== DEMO_PASSWORD) throw new Error("Wrong email or password");
    return { access_token: `mock-token-${user.id}`, token_type: "bearer", user };
  },

  async layerACheck(req: LayerACheckRequest): Promise<LayerACheckResponse> {
    const findings = runLayerALocal(req);
    const counts: Record<string, number> = { high: 0, medium: 0, low: 0, total: findings.length };
    findings.forEach((f) => (counts[f.severity] += 1));
    return { rule_pack_version: DEFAULT_RULE_PACK.version, checked_at: now(), findings, counts };
  },

  async listContent(): Promise<ContentItem[]> {
    await wait();
    const d = await getDb();
    return clone([...d.contents].sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
  },

  async getContent(id: string): Promise<ContentItem> {
    await wait(80);
    return clone(findItem(await getDb(), id));
  },

  async createContent(sub: ContentSubmission, user: User): Promise<ContentItem> {
    await wait(300);
    const d = await getDb();
    const id = `C-${++d.seq}`;
    const { findings, claims } = analyse(sub, d.facts);
    const item: ContentItem = {
      id,
      title: sub.title || "Untitled draft",
      state: "draft",
      author_id: user.id,
      author_name: user.name,
      versions: [{ version: 1, text: sub.text, html: sub.html, author: user.name, created_at: now(), rule_pack_version: DEFAULT_RULE_PACK.version }],
      findings,
      claims,
      comments: [],
      audit: [{ at: now(), actor: user.name, action: "created", detail: "Version 1" }],
      passport_id: null,
      updated_at: now(),
    };
    d.contents.push(item);
    persist();
    return clone(item);
  },

  async saveVersion(id: string, sub: ContentSubmission, user: User): Promise<ContentItem> {
    await wait(300);
    const d = await getDb();
    const item = findItem(d, id);
    if (item.author_id !== user.id) throw new Error("Only the creator can add a new version.");
    if (!["draft", "changes_requested", "needs_rereview"].includes(item.state))
      throw new Error("A new version can only be added to a draft or after changes are requested.");
    const v = item.versions.length + 1;
    item.versions.push({ version: v, text: sub.text, html: sub.html, author: user.name, created_at: now(), rule_pack_version: DEFAULT_RULE_PACK.version });
    item.title = sub.title || item.title;
    const { findings, claims } = analyse(sub, d.facts);
    item.findings = findings;
    item.claims = claims;
    item.state = "draft";
    item.passport_id = null; // an old approval never covers a new version
    item.audit.push({ at: now(), actor: user.name, action: "new version", detail: `Version ${v}` });
    item.updated_at = now();
    persist();
    return clone(item);
  },

  async respondToFinding(
    contentId: string,
    findingId: string,
    body: { decision: Decision; reason: string; modified_text?: string | null },
    user: User,
  ): Promise<ContentItem> {
    await wait();
    const d = await getDb();
    const item = findItem(d, contentId);
    const f = item.findings.find((x) => x.id === findingId);
    if (!f) throw new Error("Finding not found");
    if (body.reason.trim().length < 5) throw new Error("A reason of at least 5 characters is required.");
    f.response = { ...body, by: user.name, at: now() };
    item.audit.push({ at: now(), actor: user.name, action: `finding ${body.decision}`, detail: `${f.rule_id ?? f.fact_id ?? f.id}: ${body.reason}` });
    item.updated_at = now();
    persist();
    return clone(item);
  },

  async addComment(contentId: string, body: string, user: User): Promise<ContentItem> {
    await wait();
    const d = await getDb();
    const item = findItem(d, contentId);
    item.comments.push({ id: `cm-${Date.now()}`, author: user.name, role: user.role, body, at: now() });
    item.updated_at = now();
    persist();
    return clone(item);
  },

  async transition(contentId: string, action: WorkflowAction, reason: string | undefined, user: User): Promise<ContentItem> {
    await wait(200);
    const d = await getDb();
    const item = findItem(d, contentId);
    const need = (roles: Role[], states: ContentItem["state"][]) => {
      if (!roles.includes(user.role)) throw new Error(`Only ${roles.join(" or ")} can do this.`);
      if (!states.includes(item.state)) throw new Error(`Not allowed while content is "${item.state}".`);
    };
    switch (action) {
      case "submit": {
        need(["creator"], ["draft", "changes_requested"]);
        if (item.author_id !== user.id) throw new Error("Only the author can submit.");
        const open = item.findings.filter((f) => !f.response).length;
        if (open) throw new Error(`You still have ${open} item${open === 1 ? "" : "s"} to respond to.`);
        item.state = "in_review";
        break;
      }
      case "forward":
        need(["reviewer"], ["in_review"]);
        item.state = "awaiting_approval";
        break;
      case "request_changes":
        need(["reviewer", "approver"], ["in_review", "awaiting_approval"]);
        if (!reason || reason.trim().length < 5) throw new Error("Let them know what to change.");
        item.state = "changes_requested";
        break;
      case "approve": {
        need(["approver"], ["awaiting_approval"]);
        if (item.author_id === user.id) throw new Error("You can't approve your own work in Strict mode. Ask another approver.");
        await issuePassport(d, item, user);
        item.state = "approved";
        break;
      }
    }
    item.audit.push({ at: now(), actor: user.name, action, detail: reason ?? null });
    item.updated_at = now();
    persist();
    return clone(item);
  },

  async getPassport(id: string): Promise<Passport> {
    await wait(80);
    const p = (await getDb()).passports.find((x) => x.id === id);
    if (!p) throw new Error(`Passport ${id} not found in this browser's demo data.`);
    return clone(p);
  },

  async verifyPassport(id: string, content?: string): Promise<VerifyResult> {
    await wait(200);
    const p = await mock.getPassport(id);
    const computed = await fingerprint(content ?? p.canonical_text);
    return {
      passport_id: p.id,
      signature_valid: p.signature === `mock-ed25519:${p.fingerprint.slice(0, 32)}`,
      fingerprint_match: computed === p.fingerprint,
      computed_fingerprint: computed,
      expected_fingerprint: p.fingerprint,
      current_status: p.current_status,
      checked_at: now(),
    };
  },

  async listFacts(): Promise<Fact[]> {
    await wait();
    const d = await getDb();
    return d.facts.map((f) => factOut(d, f)).sort((a, b) => Number(a.status === "active") - Number(b.status === "active") || (a.days_left ?? 1e6) - (b.days_left ?? 1e6));
  },

  async updateFact(factId: string, patch: FactPatch, user: User): Promise<FactUpdateResult> {
    await wait(200);
    if (user.role !== "brand_manager") throw new Error("Only the Brand Manager can change facts.");
    const d = await getDb();
    const f = d.facts.find((x) => x.id === factId);
    if (!f) throw new Error("Fact not found");
    const changed: string[] = [];
    if (patch.statement !== undefined && patch.statement !== f.text) (f.text = patch.statement), changed.push("statement");
    if (patch.expires_on && patch.expires_on !== f.expires_at.slice(0, 10)) {
      if (Number.isNaN(Date.parse(patch.expires_on))) throw new Error("Use a date like 2027-03-31 for the expiry.");
      f.expires_at = new Date(patch.expires_on).toISOString();
      changed.push("expires_on");
    }
    if (patch.status && (patch.status !== "active") !== f.expired) (f.expired = patch.status !== "active"), changed.push("status");
    if (patch.value !== undefined && patch.value !== null) (f.parts = { ...f.parts, value: String(patch.value) }), changed.push("value");
    let hit = { content: [] as string[], passports: [] as string[] };
    if (changed.length) {
      (f as Fact_ & { version?: number }).version = ((f as Fact_ & { version?: number }).version ?? 1) + 1;
      hit = flagDependents(d, factId, `Approved fact ${factId} changed (${changed.join(", ")}).`);
    }
    persist();
    return { fact: factOut(d, f), changed, flagged_content: hit.content, flagged_passports: hit.passports };
  },

  async lintRules(user: User): Promise<LintResult> {
    await wait(400);
    if (user.role !== "brand_manager") throw new Error("Only the Brand Manager can run the rule health check.");
    const d = await getDb();
    const rules = d.constitution.documents.flatMap((x) => x.rules).filter((r) => r.status !== "rejected");
    const vague = rules.filter((r) => /professional|friendly|natural|approachable|appropriate|modern/i.test(r.source_passage));
    return {
      findings: vague.map((r) => ({
        kind: "ambiguity" as const,
        method: "lexical",
        score: null,
        explanation: "This rule relies on vague wording, so reviewers will apply it differently.",
        rules: [{ key: r.id, id: r.id, text: r.source_passage }],
        vague_terms: (r.source_passage.match(/professional|friendly|natural|approachable|appropriate|modern/gi) ?? []).map((w) => w.toLowerCase()),
      })),
      rules_checked: rules.length,
      checked_at: now(),
    };
  },

  async expireFact(factId: string): Promise<ExpireFactResult> {
    await wait(200);
    const d = await getDb();
    const f = d.facts.find((x) => x.id === factId);
    if (!f) throw new Error("Fact not found");
    f.expired = true;
    f.expires_at = now();
    const flaggedContent: string[] = [];
    const flaggedPassports: string[] = [];
    for (const item of d.contents) {
      if (!item.claims.some((c) => c.ledger_fact_id === factId)) continue;
      flaggedContent.push(item.id);
      if (item.state === "approved") item.state = "needs_rereview";
      item.claims.forEach((c) => {
        if (c.ledger_fact_id === factId) c.status = "uncertain";
      });
      item.audit.push({ at: now(), actor: "System", action: "flagged", detail: `${factId} expired` });
    }
    for (const p of d.passports) {
      if (!p.evidence.some((e) => e.fact_id === factId)) continue;
      p.current_status = "needs_rereview";
      p.current_status_reason = `Supporting fact ${factId} expired on ${new Date().toLocaleDateString("en-IN")}.`;
      flaggedPassports.push(p.id);
    }
    persist();
    return { fact_id: factId, flagged_content: flaggedContent, flagged_passports: flaggedPassports };
  },

  async getInsights(): Promise<Insights> {
    await wait();
    const d = await getDb();
    const counts = new Map<string, number>();
    const overrides = new Map<string, { total: number; rejected: number }>();
    for (const item of d.contents) {
      for (const f of item.findings) {
        const key = f.rule_id ?? f.kind;
        counts.set(key, (counts.get(key) ?? 0) + 1);
        if (f.response) {
          const o = overrides.get(key) ?? { total: 0, rejected: 0 };
          o.total += 1;
          if (f.response.decision === "rejected") o.rejected += 1;
          overrides.set(key, o);
        }
      }
    }
    // Historical baseline so the charts are not empty on a fresh demo
    const history: Record<string, number> = { "BAN-001": 9, "REQ-001": 7, "TONE-001": 6, "BAN-005": 4, "A11Y-001": 4, "BAN-007": 3 };
    for (const [k, v] of Object.entries(history)) counts.set(k, (counts.get(k) ?? 0) + v);
    const repeated = [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([rule_id, count]) => ({ rule_id, label: rule_id, count }));

    const baseOverride: Record<string, number> = { "TONE-001": 0.42, "BAN-007": 0.35, "REQ-001": 0.18, "BAN-001": 0.06 };
    for (const [k, o] of overrides) baseOverride[k] = Math.max(baseOverride[k] ?? 0, o.rejected / o.total);
    const confusing = Object.entries(baseOverride)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([rule_id, rate]) => ({ rule_id, label: rule_id, override_rate: Math.round(rate * 100) }));

    const nodes: Insights["impact"]["nodes"] = [];
    const edges: Insights["impact"]["edges"] = [];
    for (const f of d.facts) nodes.push({ id: f.id, kind: "fact", label: `${f.id}: ${f.text.slice(0, 38)}…`, status: f.expired ? "expired" : "ok" });
    for (const item of d.contents) {
      const linked = new Set(item.claims.map((c) => c.ledger_fact_id).filter(Boolean) as string[]);
      if (!linked.size) continue;
      nodes.push({ id: item.id, kind: "content", label: `${item.id}: ${item.title}`, status: item.state === "needs_rereview" ? "flagged" : "ok" });
      linked.forEach((fid) => edges.push({ source: fid, target: item.id }));
    }
    for (const p of d.passports) {
      nodes.push({ id: p.id, kind: "passport", label: `Passport ${p.id}`, status: p.current_status === "valid" ? "ok" : "flagged" });
      edges.push({ source: p.content_id, target: p.id });
    }

    return {
      repeated_mistakes: repeated,
      findings_per_week: [
        { week: "W38", layer_a: 14, layer_b: 6, layer_c: 3 },
        { week: "W39", layer_a: 12, layer_b: 5, layer_c: 4 },
        { week: "W40", layer_a: 9, layer_b: 5, layer_c: 2 },
        { week: "W41", layer_a: 8, layer_b: 3, layer_c: 2 },
        { week: "W42", layer_a: 6, layer_b: 3, layer_c: 1 },
        { week: "W43", layer_a: d.contents.reduce((n, c) => n + c.findings.filter((f) => f.layer === "A").length, 0), layer_b: d.contents.reduce((n, c) => n + c.findings.filter((f) => f.layer === "B").length, 0), layer_c: d.contents.reduce((n, c) => n + c.findings.filter((f) => f.layer === "C").length, 0) },
      ],
      confusing_rules: confusing,
      expiring_facts: d.facts
        .filter((f) => !f.expired)
        .map((f) => ({ fact_id: f.id, label: f.id, days_left: Math.max(0, Math.round((Date.parse(f.expires_at) - Date.now()) / 86_400_000)) }))
        .sort((a, b) => a.days_left - b.days_left),
      impact: { nodes, edges },
    };
  },

  async getConstitution(): Promise<Constitution> {
    await wait();
    return clone((await getDb()).constitution);
  },

  async uploadConstitution(file: File, classification: Classification, user: User): Promise<ConstitutionDoc> {
    await wait(700);
    const d = await getDb();
    const n = d.constitution.documents.length + 1;
    const doc: ConstitutionDoc = {
      id: `D-${n}`,
      filename: file.name,
      classification,
      uploaded_at: now(),
      uploaded_by: user.name,
      rules: draftedRulesFor(file.name, n),
    };
    d.constitution.documents.unshift(doc);
    persist();
    return clone(doc);
  },

  async decideRule(ruleId: string, decision: "approve" | "reject", reason: string, user: User): Promise<Constitution> {
    await wait();
    const d = await getDb();
    if (user.role !== "brand_manager") throw new Error("Only the Brand Manager can approve rules.");
    const rule = d.constitution.documents.flatMap((x) => x.rules).find((r) => r.id === ruleId);
    if (!rule) throw new Error("Rule not found");
    rule.status = decision === "approve" ? "active" : "rejected";
    rule.decided_by = user.name;
    rule.decision_reason = reason || null;
    rule.owner = rule.owner === "Unassigned" ? user.name : rule.owner;
    if (decision === "approve") {
      const [y, r] = d.constitution.version.split("-r");
      d.constitution.version = `${y}-r${Number(r ?? 0) + 1}`;
    }
    persist();
    return clone(d.constitution);
  },

  userById,
};
