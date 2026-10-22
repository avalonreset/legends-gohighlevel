# Authentication and user scopes

## 1. Sub-account API authentication (`GHL_PIT` vs. OAuth 2.0)

Official HighLevel API v2 (`https://services.leadconnectorhq.com`, `Version: 2021-07-28`) supports two authentication models:

| Model | Best for | Lifecycle | Environment variables |
|---|---|---|---|
| **Private Integration Token (PIT)** | Internal agent and CLI automation targeting a single sub-account (`locationId`). Created inside the sub-account under **Settings > Private Integrations**. | Static bearer token (`pit-...`). Does not auto-refresh; rotate approximately every 90 days. Strictly isolated to the issuing sub-account (returns `HTTP 403` on any other location). | `GHL_PIT`, `GHL_LOCATION_ID` |
| **OAuth 2.0 Bearer Token** | Multi-location Marketplace apps, webhooks, and delegated installs. | Access token expires after roughly 24 hours; refresh token lasts up to 1 year and rotates on each refresh. | `GHL_ACCESS_TOKEN`, `GHL_LOCATION_ID` |

Never pass tokens on the command line (`argv`), commit them to `.env` files, or paste them into Markdown notes. Load `GHL_PIT` and `GHL_LOCATION_ID` from your secret manager into the process environment, then run:

```sh
legends-gohighlevel doctor --live
```

`doctor --live` probes 8 sub-account API v2 lanes (`location`, `contacts`, `pipelines`, `calendars`, `conversations`, `custom_values`, `workflows`, `forms`) and reports exact burst (`100 requests / 10 seconds`) and daily (`200,000 requests / day`) rate-limit headroom from `X-RateLimit-*` headers.

## 2. Recommended Private Integration scopes

When creating a sub-account Private Integration token for `legends-gohighlevel`, grant only the scopes needed for your workflow:

- **Read-only inspection (`doctor --live`, inventories, triage):**
  - `locations.readonly`
  - `locations/customValues.readonly`
  - `locations/customFields.readonly`
  - `contacts.readonly`
  - `opportunities.readonly`
  - `calendars.readonly`
  - `conversations.readonly`
  - `workflows.readonly`
  - `forms.readonly`
  - `surveys.readonly`
- **Confirmed custom-value writes (`custom-value-upsert`, `custom-value-delete`):**
  - Add `locations/customValues.write`

## 3. Dual user permission architecture (V1 `permissions` vs. V2 `scopes`)

Inside HighLevel's user management system, every user record carries **two** parallel permission structures:

1. **Legacy V1 (`permissions` object):** 50 boolean flags (such as `workflowsEnabled`, `funnelsEnabled`, `botService`, `PrivateIntegrationLocationEnabled`, `adPublishingReadOnly`, `assignedDataOnly`).
2. **Granular V2 (`scopes` array / `GET /users/permissions`):** Over 130 sub-account capabilities (`forms.write`, `surveys.write`, `pipelines.create`, `private-integration-location.readonly`, `locations.billing.manage`, `locations.details.manage`, `reputation/gbp.write`, `voice-ai-agents.write`, `text-ai-agents.write`, `askai.write`, `lc.whatsapp.*`).

If a V1 flag is `true` (for example `PrivateIntegrationLocationEnabled: true` or `funnelsEnabled: true`) but the corresponding V2 scope (`private-integration-location.readonly` or `forms.write`) is missing from the user's `scopes` array, the HighLevel UI hides the menu or blocks the user when opening that micro-app.

## 4. The Agency Admin worker scope-inheritance trap

When an **Agency Admin** (as opposed to the single **Agency Owner**) creates a new sub-account user in the HighLevel web UI, HighLevel's `usersApp` frontend runs a client-side filter against the logged-in creator's own `scopes` array:

- Any V2 scope that is not present in the logged-in Agency Admin's `scopes` array (after expanding `.write` to `.readonly`) is marked `disabledForChange = true` and **silently set to `enabled = false`** on the newly created user.
- To prevent an automation or provisioning worker from silently nerfing newly created sub-account admins, ensure the Agency Admin worker account itself holds all 243 V2 scopes, and audit user payloads with:

```sh
legends-gohighlevel scope-audit --role admin --account-type account
```

## 5. Mutually exclusive V2 scopes and `PUT /users/:id` validation

When updating a user's `scopes` array via `PUT /users/{userId}`:

- `source` must be set to `"agency_team"` (or `"location_team"` when called inside location context); passing an arbitrary string such as `"agency"` returns `HTTP 422 ("source must be a valid enum value")`.
- Only top-level keys returned by `GET /users/permissions` may be sent in `scopes` (do not send expanded `scopesMap` children such as `quizzes.write` that appear on raw `GET /users/{id}` responses).
- Two V2 scope pairs are mutually exclusive in the HighLevel UI (`workflows.readonly` vs. `workflows.write`, and `campaigns.readonly` vs. `campaigns.write`). When `.write` is enabled, omit the corresponding `.readonly` key.
