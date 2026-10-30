---
title: WordAudit
emoji: 🛡️
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# WordAudit

**Catch risky wording and unsupported claims before they go live.**

WordAudit is an internal brand governance tool. A brand manager uploads the brand guidelines and a list of approved facts. Creators write or submit content. WordAudit checks it in three layers and shows each issue with the exact rule or fact it relates to, a plain explanation and a suggested fix. Nothing is changed automatically: people make every decision. When content is approved, WordAudit issues a signed **Brand Passport** that proves exactly what was approved, when and by whom.


**Team Yakult** · Faculty mentor: Dr. Deeksha Pandey · Members: Sudiksha Srivastav, Katya Chadha

---

## The problem

Content comes from in-house marketers, agencies, freelancers and writing tools, all publishing under one brand name. The guidelines are usually a PDF nobody reads fully, and the facts a brand can safely state are spread across decks and spreadsheets. So:

- claims say more than the evidence allows ("up to 60% in a pilot" becomes "guaranteed 60% for every customer")
- facts that were true last year stay in use
- tone and terms drift between teams
- accessibility issues go unchecked
- mistakes are usually noticed only after the content is live

## How it works

```
Brand Manager uploads guidelines + approved facts
        │
        ▼
Rules and ledger entries are drafted → Brand Manager approves them
        │
        ▼
Creator writes or uploads content (text, PDF, DOCX, image)
        │
        ▼
┌───────────────── Review engine ─────────────────┐
│ Layer A  Brand rules: terms, tone, contrast,    │
│          alt text (fixed checks, no AI)         │
│ Layer B  Claims vs evidence: extract claims,    │
│          match the Claim Ledger, check values   │
│ Layer C  Drift: has the claim become stronger   │
│          than its evidence?                     │
└─────────────────────────────────────────────────┘
        │
        ▼
Creator accepts / edits / rejects each finding, with a reason
        │
        ▼
Reviewer  →  Approver  →  Brand Passport (SHA-256 + Ed25519)
        │
        ▼
A fact expires later → linked content and Passports are flagged for another look
```

### The rule we follow: no source, no factual verdict

Every claim ends up as one of:

| Status | Meaning |
|---|---|
| **Verified** | Matches an approved fact |
| **Contradicted** | Conflicts with an approved fact |
| **Unsupported** | No approved evidence found. This does not mean false; it needs a source |
| **Uncertain** | Related evidence exists and a person needs to decide |

---

## Features

**Writing and review**
- Rich-text editor with live highlights for brand-rule issues as you type
- One-click suggested fixes, always applied by the creator, never automatically
- Findings panel: accept, edit or reject each finding, with a required reason
- Claim view: the draft claim side by side with the closest approved fact, field by field
- Claim strength meter showing how far wording has drifted beyond the evidence
- Version comparison, comments and full history

**Workflow and trust**
- Creator → Reviewer → Approver roles
- Strict mode (the approver must be a different person) and Solo mode for very small teams
- Brand Passport: content fingerprint, guideline version, evidence snapshot, approver, timestamp and digital signature
- QR code linking to a public verification page
- Tamper demo: change one character and verification fails

**Brand rules and insights**
- Upload guidelines (PDF or DOCX); suggested rules stay inactive until the Brand Manager approves them
- Versioned rules, each linked to its source passage, with pass and fail examples
- Dashboard: repeated mistakes, the weekly trend, and rules people push back on
- Impact graph: facts → content → Passports, with an expiry simulation
- Guideline Linter for ambiguous or conflicting rules
- Public, Internal and Restricted documents; Restricted ones are processed only by a local model

---

## Team and responsibilities

### Katya Chadha: frontend, Layer A and content

| # | Responsibility | Technology |
|---|---|---|
| 1 | App setup, login and role-based interface | Next.js, TypeScript, Tailwind CSS, shadcn/ui, JWT (PyJWT, passlib) |
| 2 | Layer A: banned and required terms, tone, colour contrast, alt text | Python, regex, spaCy (optional), WCAG contrast formula |
| 3 | Editor with real-time Layer A feedback | Tiptap |
| 4 | Findings interface: accept / edit / reject with reason, comments, version comparison | React, diff-match-patch |
| 5 | Claim view and claim strength meter | React, Tailwind CSS |
| 6 | Passport page, QR verification link, tamper demo | Next.js, qrcode.react |
| 7 | Insights dashboard (3 charts) and impact graph | Recharts, React Flow |
| 8 | Brand rules upload and approval screens | Next.js |

### Sudiksha Srivastav: backend and AI core

| # | Responsibility | Technology |
|---|---|---|
| 1 | Database schema and vector search | PostgreSQL, pgvector, SQLModel, Alembic |
| 2 | Layer B: claim extraction, ledger matching, field-by-field verdicts, four claim statuses | FastAPI, Pydantic, LLM API (structured JSON), bge-small-en embeddings |
| 3 | Layer C: qualifier and scope strength ladders for drift detection | Python (rule-based); LLM for explanation text only |
| 4 | Self-verifying suggested fixes (each fix is re-run through the engine) | Python, Layer A/B/C engine |
| 5 | Impact propagation when a fact changes or expires | PostgreSQL relations, FastAPI |
| 6 | Brand Passport: fingerprint, signature, verification endpoint, hash-chained audit log | hashlib (SHA-256), PyNaCl (Ed25519) |
| 7 | Local model for Restricted content, and redaction preview | Ollama (Llama 3.1 8B / Qwen2.5 7B), Microsoft Presidio |
| 8 | Guideline Linter: ambiguity and rule-conflict detection | Python, LLM, pgvector |
| 9 | Document parsing for guidelines and content | PyMuPDF, python-docx |

### Joint

| Task | Sudiksha | Katya |
|---|---|---|
| Interviews and survey | 3 interviews, survey design | 3 interviews, survey distribution |
| Synthetic test set | 25 claim and drift items | 25 rule, tone and accessibility items |
| Indian rule pack (ASCI-inspired) | Loading rules into the schema | Researching and drafting the rules |
| Presentation | Architecture slide, evaluation scoreboard | Slide deck, demo script |

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS 4, shadcn/ui-style components |
| Editor | Tiptap 3 (inline decorations for live feedback) |
| Charts and graph | Recharts, React Flow |
| Diff | diff-match-patch |
| Backend | Python, FastAPI, Pydantic |
| Database | PostgreSQL + pgvector, SQLModel, Alembic |
| Embeddings | bge-small-en (sentence-transformers, local) |
| Language models | Commercial API (standard content); Ollama (Restricted content) |
| Fixed checks | Regex, spaCy, WCAG contrast |
| Redaction | Microsoft Presidio + custom regex |
| Parsing | PyMuPDF, python-docx |
| Auth | JWT (PyJWT, passlib) |
| Signing | SHA-256, Ed25519 (PyNaCl) |
| Evaluation | pytest, pandas, scikit-learn |
| Deployment | Docker, Hugging Face Spaces; Neon for Postgres |

---

## Repository structure

```
word-audit/
├── web/                         Next.js frontend (Katya)
│   ├── app/
│   │   ├── login/               sign-in, one-click demo accounts
│   │   ├── (app)/editor/        live-checking editor
│   │   ├── (app)/content/       content list + detail (findings, claims, versions, comments)
│   │   ├── (app)/passport/      Passport + tamper demo
│   │   ├── (app)/insights/      charts + impact graph
│   │   ├── (app)/constitution/  brand rules upload + approval
│   │   └── verify/              public verification page (QR target)
│   ├── components/              UI building blocks
│   ├── lib/
│   │   ├── types.ts             shared data contract with the backend
│   │   ├── api.ts               one function per endpoint (demo data or real API)
│   │   ├── mock-store.ts        in-browser demo backend
│   │   ├── layer-a.ts           TypeScript copy of Layer A for instant feedback
│   │   └── canonical.ts         text normalisation + SHA-256 fingerprint
│   └── scripts/parity.mts       checks the TS and Python Layer A agree
├── services/                    Python: auth + Layer A (Katya)
│   ├── bt_auth/                 JWT login, require_roles()
│   ├── layer_a/                 terms, tone, contrast, alt text
│   │   └── data/                rule pack + synthetic test items
│   ├── eval_layer_a.py          precision / recall on the test set
│   └── tests/                   pytest
├── backend/                     Sudiksha's API: schema, Layers A/B/C, Passport, linter, parsing
│   └── app/ui_api.py            /api routes the website uses (login, workflow, insights, rules)
├── docs/API_CONTRACT.md         every endpoint, the workflow state machine, the fingerprint rule
├── Dockerfile                   Hugging Face Space build
└── README.md
```

---

## Run locally

**Requirements:** Node.js 18+ and Python 3.10+.

### Frontend (works on its own with demo data)

```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.

### Auth + Layer A service

```bash
cd services
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs are at http://localhost:8000/docs.

### Backend (Layers B/C, database, Passport)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # optional settings (LLM key, Postgres, signing key)
uvicorn app.main:app --reload --port 8000
```

### Connect the frontend to the real backend

In `web/.env.local`:

```
NEXT_PUBLIC_USE_MOCKS=false
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### Demo accounts

Password for all: `demo1234`

| Role | Email |
|---|---|
| Creator | creator@wordaudit.demo |
| Reviewer | reviewer@wordaudit.demo |
| Approver | approver@wordaudit.demo |
| Brand Manager | manager@wordaudit.demo |

The login page has one-click buttons for each.

---

## Demo script (about 3 minutes)

1. **Creator → New draft.** The starter text lights up: "guarantees" (banned), "!!" (tone), missing "T&C apply" (required), and the green button fails contrast at 3.30:1. Click a suggestion to apply it.
2. **Check.** On the content page, open the **Claims** tab: the strength meter shows "every customer" says three steps more than the evidence ("in a pilot").
3. **Respond and submit.** Accept, edit or reject each item with a short note, then **Send for review**.
4. **Reviewer → Send to approver. Approver → Approve.** A Brand Passport is issued.
5. **Passport.** Show the QR code, change one word in "Has it been changed?", press **Check**. It doesn't match.
6. **Insights.** Click fact F-007, then "What if this fact expires?". The linked content and Passports turn orange.
7. **Brand Manager → Brand rules.** Upload a PDF, approve a suggested rule, and the version number goes up.

---

## Testing and evaluation

```bash
cd services && pytest && python eval_layer_a.py
cd web && npm run parity && npm run build
```

| Check | Result |
|---|---|
| Python tests (auth + Layer A) | 20 passed |
| Layer A on 25 synthetic rule, tone and accessibility items | precision 1.00, recall 1.00 (0 false alarms on 7 clean items) |
| TypeScript vs Python Layer A parity | 25 / 25 items agree |
| Layers B/C on 25 synthetic claim and drift items | TODO (Sudiksha) |
| Passport tamper detection | modified content fails verification |

These results are on synthetic items written by the team. They show the checks work as designed; they do not prove real-world performance.

---

## Deploy (Hugging Face Spaces)

1. Create a Space with the **Docker** SDK.
2. Push the repo:
   ```bash
   git remote add hf https://huggingface.co/spaces/<hf-username>/word-audit
   git push hf main
   ```
3. Add secrets in **Settings → Variables and secrets**: `JWT_SECRET`, `DATABASE_URL`, the LLM API key, and `NEXT_PUBLIC_API_URL` if the backend runs in a separate Space.

Hugging Face Spaces run one container on port 7860, as a non-root user. Docker Compose is not used there. Postgres is hosted separately (Neon). Restricted mode needs Ollama and GPU hardware, so it is shown in a local demo.

---

## Responsible design

- **People stay in control.** Nothing is published or fixed automatically. Suggested rules need Brand Manager approval. Overrides become proposed changes, never silent policy.
- **Transparency.** Every finding names its rule or fact and says whether it came from a fixed check or an automated assessment.
- **Privacy.** Documents are marked Public, Internal or Restricted. Restricted text is processed only by the local model. Anything sent outside goes through redaction first, with a preview.
- **Tamper-evident, not tamper-proof.** A Passport records "approved as of" (never changes) and "current status" (can change if a fact expires). An old approval never covers a new version.

## Known limitations

- Claim matching can be wrong; it is an assisted assessment, not proof.
- Accessibility checks cover contrast and alt text only.
- Redaction is best-effort and can miss things like unreleased product names.
- Turning qualitative guidelines into rules loses nuance, so each rule links to its source text and needs approval.
- The rule pack is ASCI-inspired wording for a fictional brand ("PaisaLeaf"), not a legal reading of the ASCI Code.
- Results on synthetic data do not prove real-world performance.

---

*Built by Team Yakult for TechCircuit / WCC Forge.*
