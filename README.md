# WordAudit: Katya's work package

Frontend, Layer A and content for Team Yakult's WordAudit. Everything here runs on its own
(mock mode) so it never waits on the backend, and switches to Sudiksha's API with one env var.

```
services/            Python: auth (JWT) + Layer A, mountable in the main FastAPI app
  bt_auth/           login, /auth/me, require_roles() dependency
  layer_a/           banned/required terms, tone, WCAG contrast, alt text
    data/rule_pack_india.json          ASCI-inspired Indian rule pack (drafted, verify before demo)
    data/synthetic_rule_tone_a11y.json Katya's 25 synthetic test items
  eval_layer_a.py    precision / recall on the synthetic items
  tests/             pytest
web/                 Next.js 15 + TypeScript + Tailwind + shadcn-style UI
  app/login                     sign-in, demo accounts per role
  app/(app)/editor              Tiptap editor with real-time Layer A highlights
  app/(app)/content/[id]        findings (accept/modify/reject + reason), Claim Diff, versions, comments, audit log, workflow
  app/(app)/passport/[id]       Passport, QR code, tamper-detection demo
  app/verify/[id]               public verification page (QR target)
  app/(app)/insights            three charts + React Flow impact propagation graph
  app/(app)/constitution        guideline upload + rule approval (Brand Manager)
  lib/types.ts                  shared contract with the backend
  lib/api.ts                    one function per endpoint, mock or real
  lib/layer-a.ts                TypeScript mirror of Layer A for instant feedback
docs/API_CONTRACT.md            endpoints Sudiksha implements, state machine, fingerprint rule
```

## Run

```bash
# Backend pieces (port 8000)
cd services
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                      # 20 tests
python eval_layer_a.py      # Layer A precision/recall on the synthetic set
uvicorn main:app --reload --port 8000

# Frontend (port 3000)
cd web
npm install
cp .env.example .env.local  # NEXT_PUBLIC_USE_MOCKS=true by default
npm run dev
npm run parity              # TS Layer A gives the same rule IDs as Python on all 25 items
```

Demo accounts (password `demo1234`): `creator@`, `reviewer@`, `approver@`, `manager@wordaudit.demo`.
The login page has one-click buttons for each.

To use the real backend set `NEXT_PUBLIC_USE_MOCKS=false` and `NEXT_PUBLIC_API_URL`. Endpoints not built yet
will show their HTTP error in the UI. In mock mode, data lives in the browser's localStorage; clear it to reset.

## How the pieces fit

- **Layer A runs twice, on purpose.** The editor runs `lib/layer-a.ts` on every keystroke (no network, instant
  highlights). "Run full review" sends the text to the backend, where the Python Layer A is the source of truth.
  Both read the same rule pack JSON; `npm run parity` proves they agree. If you edit the rule pack, copy
  `services/layer_a/data/rule_pack_india.json` to `web/lib/default-rule-pack.json`.
- **Offsets.** Findings point at character offsets in the plain text (blocks joined by `\n`). The editor maps those
  back to document positions (`components/editor/layer-a-extension.ts`), so backend findings highlight correctly too.
- **People decide.** Suggestions apply only on a click; every response needs a reason; submit is blocked until every
  finding is answered; Strict mode blocks self-approval.

## Demo script (about 3 minutes)

1. Creator → New draft. The starter text lights up: "guarantees" (BAN-001), "!!" (TONE-001), missing "T&C apply"
   (REQ-001), and the green button fails contrast at 3.30:1. Click a suggestion to apply it.
2. Check everything → content page. Open the Claims tab: the strength meter shows "every customer" says three steps
   more than the evidence ("in a pilot").
3. Accept, edit or reject each item with a short note, then Send for review. Switch to Reviewer → Send to approver. Approver → Approve.
4. Passport: show the QR code, then change one word in "Has it been changed?" and press Check. It doesn't match.
5. Insights: click fact F-007, then "What if this fact expires?". The linked content and Passports turn orange.
6. Brand Manager → Brand rules: upload any PDF, approve a suggested rule, and the version number goes up.

## Checked

- `pytest`: 20 passed. `eval_layer_a.py`: precision 1.00, recall 1.00 on 25 synthetic items (7 clean items, 0 false alarms).
  These are our own synthetic items, so they show the checks work as designed, not real-world accuracy.
- `npm run parity`: all 25 items agree. `next build`: passes with strict TypeScript.
- Browser run-through of steps 1 to 6 above with no console errors.

## Known limits

- Layer B/C in mock mode are canned imitations to drive the UI; the real engine is Sudiksha's.
- Mock signatures are placeholders. Real Ed25519 signing happens on the backend.
- spaCy is optional. Without it, inflections come from a small regex ("guarantee" → guarantees, guaranteed, guaranteeing).
- Accessibility checks cover contrast and alt text only.
- The rule pack is ASCI-inspired wording for a fictional brand, not a legal reading of the ASCI Code.
