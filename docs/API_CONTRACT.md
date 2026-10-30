# WordAudit API contract (frontend ↔ backend)

The frontend calls exactly these endpoints, through `web/lib/api.ts`.
Request and response shapes are the TypeScript interfaces in `web/lib/types.ts`.
While `NEXT_PUBLIC_USE_MOCKS=true`, the same functions run against `web/lib/mock-store.ts`,
so any endpoint can be built and switched on one at a time.

All endpoints except `/auth/login`, `/passports/{id}` and `/passports/{id}/verify`
expect `Authorization: Bearer <JWT>`. Errors return `{"detail": "<message>"}`; the UI shows `detail` as is.

## Where it lives

All of these are implemented in `backend/app/ui_api.py` under the `/api` prefix, so the website uses
`NEXT_PUBLIC_API_URL=<backend>/api`. They call the existing services (review engine, Passport, impact,
registry); the original routes in `backend/app/api.py` are unchanged.

| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | `LoginResponse` | JWT, four demo roles |
| GET | `/auth/me` | | `User` | |
| POST | `/layer-a/check` | `LayerACheckRequest` | `LayerACheckResponse` | Brand rule pack only |
| GET | `/content` | | `ContentItem[]` | Newest first |
| POST | `/content` | `ContentSubmission` | `ContentItem` | Creator. Runs the engine + brand rule pack. State `draft` |
| GET | `/content/{id}` | | `ContentItem` | Findings are for the latest version |
| POST | `/content/{id}/versions` | `ContentSubmission` | `ContentItem` | Author only. New version, re-checked, back to `draft` |
| POST | `/content/{id}/findings/{finding_id}/response` | `{decision, reason, modified_text?}` | `ContentItem` | Author only, reason ≥ 5 chars |
| POST | `/content/{id}/comments` | `{body}` | `ContentItem` | Stored in the audit log |
| POST | `/content/{id}/transition` | `{action, reason?}` | `ContentItem` | See state machine below |
| GET | `/passports/{id}` | | `Passport` | Public |
| POST | `/passports/{id}/verify` | `{content?}` | `VerifyResult` | Public. No `content` = verify stored text |
| POST | `/ledger/facts/{claim_key}/expire` | | `ExpireFactResult` | Reviewer, approver or brand manager |
| GET | `/insights` | | `Insights` | Real counts from the database |
| GET | `/constitution` | | `Constitution` | DB rules + the built-in rule pack |
| POST | `/constitution/upload` | multipart: `file`, `classification` | `ConstitutionDoc` | PDF, DOCX, TXT, MD. Drafts stay inactive |
| POST | `/constitution/rules/{rule_id}/decision` | `{decision, reason}` | `Constitution` | Brand manager. Approval releases a new rules version |

### Workflow state machine

```
draft ──submit (creator, author, all findings answered)──▶ in_review
in_review ──forward (reviewer)──▶ awaiting_approval
in_review | awaiting_approval ──request_changes (reviewer | approver, reason required)──▶ changes_requested
changes_requested ──new version──▶ draft
awaiting_approval ──approve (approver ≠ author in Strict mode)──▶ approved  (+ Passport issued)
approved ──supporting fact expires/changes──▶ needs_rereview  (Passport current_status = needs_rereview)
```

### Finding fields the UI relies on

- `layer` A/B/C, `source` `fixed_check` (A) or `automated_assessment` (B/C), `status`.
- `span` = character offsets into `ContentVersion.text` (the plain text). The editor and the read-only view highlight with it.
- `fix_type`: `replace` (swap `span` for `suggestion`), `insert` (add `suggestion`), `advice` (text only).
- `suggestion_verified: true` shows the "Re-checked by the engine" badge (self-verifying fixes).
- `claim_status` on B/C findings: `verified | contradicted | unsupported | uncertain`.

### Claim Diff (`ContentItem.claims`)

One `ClaimDiff` per extracted claim. `draft` and `ledger` use the same five fields
(metric, value, population, conditions, period); the UI marks fields that differ.
`ladders` drive the claim strength meter: `steps` weakest → strongest, with `draft_index` and `ledger_index`.

### Passport fingerprint

SHA-256 of the content text with Windows line endings normalised, matching `backend/app/services/passport.py`
and `web/lib/canonical.ts`:

```python
fingerprint = hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
```

`verify` recomputes the fingerprint of the submitted (or stored) text, compares it with the signed one,
and checks the Ed25519 signature over the Passport payload.
