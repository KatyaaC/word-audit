# WordAudit API contract (frontend ↔ backend)

The frontend calls exactly these endpoints, through `web/lib/api.ts`.
Request and response shapes are the TypeScript interfaces in `web/lib/types.ts`.
While `NEXT_PUBLIC_USE_MOCKS=true`, the same functions run against `web/lib/mock-store.ts`,
so any endpoint can be built and switched on one at a time.

All endpoints except `/auth/login`, `/passports/{id}` and `/passports/{id}/verify`
expect `Authorization: Bearer <JWT>`. Errors return `{"detail": "<message>"}`; the UI shows `detail` as is.

## Built by Katya (in `services/`)

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | `LoginResponse` |
| GET | `/auth/me` | | `User` |
| GET | `/layer-a/rule-pack` | | `RulePack` |
| POST | `/layer-a/check` | `LayerACheckRequest` | `LayerACheckResponse` |

Mount them in the main app:

```python
from bt_auth import router as auth_router, require_roles, current_user
from layer_a.router import router as layer_a_router
from layer_a import CheckRequest, run_layer_a, load_rule_pack

app.include_router(auth_router)
app.include_router(layer_a_router)

# inside the review endpoint, before Layer B/C:
layer_a_findings = run_layer_a(CheckRequest(text=text, html=html, colour_pairs=pairs, images=images), load_rule_pack())
```

Protect routes with `Depends(require_roles("approver"))` and similar.

## Built by Sudiksha (expected by the UI)

| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| GET | `/content` | | `ContentItem[]` | Newest first |
| POST | `/content` | `ContentSubmission` | `ContentItem` | Runs Layers A, B, C. State `draft` |
| GET | `/content/{id}` | | `ContentItem` | `findings` are for the latest version |
| POST | `/content/{id}/versions` | `ContentSubmission` | `ContentItem` | Author only. Re-runs all layers, clears responses and `passport_id`, state back to `draft` |
| POST | `/content/{id}/findings/{finding_id}/response` | `{decision, reason, modified_text?}` | `ContentItem` | `reason` required (min 5 chars). Write an audit event |
| POST | `/content/{id}/comments` | `{body}` | `ContentItem` | |
| POST | `/content/{id}/transition` | `{action, reason?}` | `ContentItem` | See state machine below |
| GET | `/passports/{id}` | | `Passport` | Public |
| POST | `/passports/{id}/verify` | `{content?}` | `VerifyResult` | Public. No `content` = verify stored text |
| POST | `/ledger/facts/{id}/expire` | | `ExpireFactResult` | Impact propagation |
| GET | `/insights` | | `Insights` | Three charts + expiring facts + impact graph |
| GET | `/constitution` | | `Constitution` | |
| POST | `/constitution/upload` | multipart: `file`, `classification` | `ConstitutionDoc` | Drafted rules come back with `status: "draft"` |
| POST | `/constitution/rules/{rule_id}/decision` | `{decision: "approve" \| "reject", reason}` | `Constitution` | Brand Manager only. Approval bumps the version |

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

Canonicalise, then SHA-256 (hex). Must match `web/lib/canonical.ts` exactly:

```python
import hashlib, re, unicodedata

def canonicalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in t.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

fingerprint = hashlib.sha256(canonicalize(text).encode("utf-8")).hexdigest()
```

`Passport.canonical_text` is the text that was signed. `verify` recomputes the fingerprint of the
submitted (or stored) text, compares it with the signed one, and checks the Ed25519 signature
over the Passport payload.
