# Internal backend API, 5-layer governance, and dashboard RBAC

GoHighLevel splits its operational surface across two distinct HTTP planes. Understanding which plane governs a capability prevents hours of trial-and-error debugging.

## 1. The two HighLevel HTTP planes

| Plane | Base URL | Auth header | What it governs |
|---|---|---|---|
| **Official API v2 & Workflows v3** | `https://services.leadconnectorhq.com` | `Authorization: Bearer <GHL_PIT or GHL_ACCESS_TOKEN>`, `Version: 2021-07-28` (or `Version: v3` for Workflows v3) | Sub-account CRM data: contacts, tags, pipelines, opportunities, calendars, conversations, workflows, Workflows v3 definitions/logs, forms, surveys, funnels/redirects, custom objects/associations, Voice AI, Conversation AI, custom fields, and custom values. |
| **Internal Web-App Backend** | `https://backend.leadconnectorhq.com` | `token-id: <Firebase_ID_Token>`, `Version: 2021-07-28`, `channel: APP`, `source: WEB_USER` | Agency-wide sub-account directory, 40 location feature flags, user V1/V2 scope catalogs, `+hubpro` user location assignments, Reporting V2 per-dashboard RBAC, Custom SMTP locks, 4-store + 14-product SaaS Billing v2 rebilling, Private Integration Token metadata, and dedicated email domains. |

Sub-account Private Integration Tokens (`pit-...`) cannot call `backend.leadconnectorhq.com` endpoints such as `/reporting/dashboards/:id/permissions`, `/users/permissions`, or `/saas-billing-v2/billing-config/LOCATION/:id`. Conversely, `legends-gohighlevel` uses `BackendClient` with an active worker `token-id` to inspect and govern agency-level and dashboard-level state.

## 2. Safe worker `token-id` resolution (IndexedDB, never SQLite Cookies)

When a headless or containerized Chromium worker is signed into `app.gohighlevel.com`, Firebase Authentication continuously refreshes a 1-hour JWT (`token-id`) inside Chromium's LevelDB IndexedDB folder:

```text
/profile/Default/IndexedDB/https_app.gohighlevel.com_0.indexeddb.leveldb
```

- **Do:** Configure `~/.config/legends-gohighlevel/agency.json` with `company_id`, `worker_ssh`, `worker_container`, and `worker_user_id` (or pass `GHL_TOKEN_ID` in the environment). `BackendClient` reads the latest valid `eyJ...` Firebase JWT directly from `*.ldb` and `*.log` files in IndexedDB over SSH without disturbing the running Chromium session.
- **Never:** Do not read or decrypt `/profile/Default/Cookies` (SQLite cookie store) and do not call `/oauth/2/login/proxy` with decrypted browser cookies. Reading IndexedDB `.ldb`/`.log` files is read-only, requires no decryption, and works for all `backend.leadconnectorhq.com` endpoints.

## 3. The 5-layer sub-account governance architecture

When a sub-account user reports `"You do not have permission to perform this operation"`, cannot see a feature, or has drifting billing markups, the issue lives in one of five independent backend layers. Run `legends-gohighlevel live-audit` to check all five layers across the entire agency in one command:

```sh
legends-gohighlevel live-audit
```

### Layer 1: Location feature flags (`GET/PUT /locations/{locationId}`)

Every sub-account has a `location.permissions` object containing **40 boolean feature switches** (`workflowsEnabled`, `dashboardStatsEnabled`, `funnelsEnabled`, `websitesEnabled`, `botService`, `socialPlanner`, `communitiesEnabled`, `bloggingEnabled`, `affiliateManagerEnabled`, `adwordsReportingEnabled`, `facebookAdsReportingEnabled`, `attributionsReportingEnabled`, `agentReportingEnabled`, `certificatesEnabled`, `coursesEnabled`, `exportPaymentsEnabled`, `goCollaborationEnabled`, `invoiceEnabled`, `onlineListingsEnabled`, `paymentsEnabled`, `recordPaymentEnabled`, `refundsEnabled`, etc.).

When HighLevel provisions a new sub-account via the UI modal without a SaaS plan template, it leaves up to 19 of these 40 flags `false` and leaves `location.reseller` empty `{}`. Calling `PUT /locations/{locationId}` with `{"companyId": "<COMPANY_ID>", "permissions": UNNERFED_LOCATION_PERMISSIONS}` enables all 40 flags and automatically initializes `location.reseller` on the backend. (Never pass `reseller` or `settings.emailIsvSettings` directly in `PUT /locations/{locationId}`, as HighLevel rejects those read-only fields with `HTTP 422`.)

Inspect and remediate Layer 1 across the agency with:

```sh
legends-gohighlevel agency-locations
legends-gohighlevel location-unnerf --all-locations
legends-gohighlevel location-unnerf --all-locations --apply --confirm-plan SHA256_FROM_PREVIEW
```

### Layer 2: User V1 permissions, V2 scopes, Only Assigned Data, and `+hubpro` aliases

Inspect all users or deep-inspect and un-nerf a specific user with:

```sh
legends-gohighlevel agency-users
legends-gohighlevel user-inspect --email user@example.com
legends-gohighlevel user-unnerf --email user@example.com
legends-gohighlevel user-unnerf --email user@example.com --apply --confirm-user USER_ID --confirm-plan SHA256_FROM_PREVIEW
```

Key backend rules for Layer 2:

1. **57 camelCase V1 boolean switches (`user.permissions`):** HighLevel's `GET /users/{id}` returns 57 camelCase boolean switches (including `nativeIntegrationsEnabled`, `privateIntegrationLocationEnabled`, and `subscriptionEnabled` in camelCase, plus 9 read-only/restriction switches that must be `false`: `adPublishingReadOnly`, `assignedDataOnly`, `campaignsReadOnly`, `conversationsReadOnly`, `customMenuLinkReadOnly`, `funnelsReadOnly`, `settingsReadOnly`, `websitesReadOnly`, `workflowsReadOnly`).
2. **132-item Account Admin V2 catalog (`GET /users/permissions?userId={id}&type=account&role=admin`):** Returns a dictionary of 132 capabilities. On a fully un-nerfed `account_admin`, **130 of 132** items have `enabled: true`, and only the 2 mutually exclusive readonly items (`campaigns.readonly` and `workflows.readonly`) are `enabled: false` because `campaigns.write` and `workflows.write` are enabled.
3. **Only Assigned Data (`userConfig.assignedToSupported`):** Inside `GET /users/permissions`, capabilities such as `contacts.readonly`, `opportunities.readonly`, `calendars.readonly`, and `dashboard/stats.readonly` include `userConfig.assignedToSupported`. When `false` (along with V1 `assignedDataOnly: false`), the user can view all records in the sub-account rather than only records explicitly assigned to their user ID.
4. **Primary email vs. `+hubpro` alias location sync (`PUT /users/{userId}`):** If a member has both a primary email user record (`user@domain.com`) and a provisioned `+hubpro` alias (`user+hubpro@domain.com`), both records must hold the same `roles.locationIds` array so the member sees all of their sub-accounts regardless of which login they use.
5. **Critical `PUT /users/{userId}` payload requirement:** HighLevel requires `companyId`, `type`, `role`, and `locationIds` at the **top level** of the JSON body. Use `user-sync-locations` to preview and apply this safely:
   ```sh
   legends-gohighlevel user-sync-locations --user-id PRIMARY_USER_ID --from-user-id ALIAS_USER_ID
   legends-gohighlevel user-sync-locations --user-id PRIMARY_USER_ID --from-user-id ALIAS_USER_ID \
     --apply --confirm-user PRIMARY_USER_ID --confirm-plan SHA256_FROM_PREVIEW
   ```

### Layer 3: Reporting V2 per-dashboard RBAC (`GET/POST /reporting/dashboards/{id}/permissions`)

HighLevel's Reporting V2 micro-frontend (`reporting.*.js`) enforces its own **per-dashboard Role-Based Access Control (RBAC)** table on every dashboard (both `defaultDashboardId` and custom `sharedDashboards`), completely separate from user V1/V2 scopes.

- **The Default Dashboard seeding bug:** When HighLevel creates a new sub-account, it seeds the Default Dashboard (`defaultDashboardId`) with only two role entries (`agency_user: "full"` and `account_user: "read"`), omitting `account_admin` entirely. Similarly, when a custom dashboard is cloned, HighLevel defaults other roles to `"read"`.
- **The `POST` DTO field name trap (`permissionAccess` vs `permission`):**
  - `GET /reporting/dashboards/{dashboardId}/permissions?locationId={locationId}` returns the role array under `data.permission`.
  - `POST /reporting/dashboards/{dashboardId}/permissions?locationId={locationId}` requires the role array under **`permissionAccess`**.

Inspect and unlock all default and custom dashboards across the agency with:

```sh
legends-gohighlevel dashboard-permissions --all-locations
legends-gohighlevel unlock-dashboards --all-locations
legends-gohighlevel unlock-dashboards --all-locations --apply --confirm-plan SHA256_FROM_PREVIEW
```

### Layer 4: Custom SMTP locks (`GET /email-isv/onload` & `PUT /email-isv/Setting/feature/...`)

Inspect and unlock Custom SMTP (`blockAddSmtp: false`) and inspect dedicated LC Email domains with:

```sh
legends-gohighlevel smtp-status --all-locations
legends-gohighlevel smtp-unlock --all-locations
legends-gohighlevel smtp-unlock --all-locations --apply --confirm-plan SHA256_FROM_PREVIEW
legends-gohighlevel email-domains --location-id LOCATION_ID
```

### Layer 5: 4-store + 14-product SaaS Billing v2 rebilling (`1.05x` / `markup: 5`)

Inspect and synchronize `1.05x` (`markup: 5`) rebilling across all 4 HighLevel stores (`saas-billing-v2`, `update-twilio-rebilling`, `location.settings.saasSettings`, and `location-metadata`) and all **14 metered products** (`workflow_premium_actions`, `workflow_ai`, `conversation_AI`, `voiceAI`, `contentAI`, `reviewsAI`, `agentStudio`, `askai`, `aiStudio`, `EmailVerification`, `domainPurchase`, `whatsApp`, `emailWarmup`, `creatorStudio`) with:

```sh
legends-gohighlevel rebilling-status --all-locations
legends-gohighlevel rebilling-sync --all-locations --markup 5
legends-gohighlevel rebilling-sync --all-locations --markup 5 --apply --confirm-plan SHA256_FROM_PREVIEW
```

## 1-Command 5-Layer Full Un-Nerf (`location-full-unnerf`)

To remediate all 5 governance layers on one or more sub-accounts (and optional user email + `+hubpro` alias) in a single preview plan and a single confirmation pass:

```sh
legends-gohighlevel location-full-unnerf --location-ids LOCATION_1,LOCATION_2 --email user@example.com
legends-gohighlevel location-full-unnerf --location-ids LOCATION_1,LOCATION_2 --email user@example.com \
  --apply --confirm-plan SHA256_FROM_PREVIEW
```

## Agency Snapshots V2 & Internal Bulk Workflow Status

HighLevel's Snapshots V2 micro-frontend (`snapshotsApp`) and Workflow Builder service (`WorkflowService`) operate on `https://backend.leadconnectorhq.com` with both `token-id: <firebase-id-token>` and `Authorization: Bearer <firebase-id-token>`:

- **List Snapshots V2:** `GET /snapshots/v2/{companyId}?companyId={companyId}&skip=0&limit=50&type=own` (`snapshots-list`)
- **Inspect Snapshot & 16-Category Assets:** `GET /snapshots/snapshotDetails/{snapshotId}?companyId={companyId}` and `GET /snapshots/{snapshotId}/assets?type=own&companyId={companyId}` (`snapshot-inspect`)
- **Create / Refresh Snapshot V2:** `POST /snapshots/create?companyId={companyId}` (`snapshot-create`) and `POST /snapshots/{snapshotId}/refresh?companyId={companyId}` (`snapshot-refresh`)
- **Push Snapshot V2 to 1 or N Sub-Accounts:** `POST /snapshots/snapshot-push/v2/{snapshotId}/set_assets_to_locations?companyId={companyId}` (`snapshot-push`). By default, `snapshot-push --apply` polls push batch completion (`/snapshots/push-batch/v2/{snapshotId}/batches`), automatically bulk-switches all cloned workflows in the target sub-accounts to `draft`, and unlocks all default/custom dashboard RBAC.
- **Internal Bulk Workflow Status (`PUT /workflow/{locationId}/change-status`):** Unlike the public Workflows API v3 beta (`PUT /workflows/{id}/status` with `Version: v3`, which returns `403 WORKFLOW_API_NOT_ENABLED_FOR_LOCATION` on non-beta sub-accounts), `PUT /workflow/{locationId}/change-status` (`{"workflowIds": [...], "status": "draft"|"published", "updatedBy": "<userId>"}`) works on 100% of locations and updates all workflows in a single HTTP request (`workflow-bulk-status`).
- **Sub-Account Clone Readiness & Brand-Leak Audit:** `legends-gohighlevel location-clone-audit --location-id LOCATION_ID --brand-terms "oldbrand"` verifies snapshot load history, asset counts, workflow draft state, governance readiness, and brand-term occurrences across business profile, custom values, pipelines, calendars, forms, email templates, trigger links, and workflows.
- **1-Command Multi-Sub-Account Batch Cloning (`location-batch-clone`):** `legends-gohighlevel location-batch-clone --source-location-id SOURCE_ID --snapshot-id SNAPSHOT_ID --names "Clone 1,Clone 2,Clone 3,Clone 4" --assign-email user@example.com --create-pits` provisions $N$ sub-accounts (`POST /locations/`), pushes the V2 snapshot in 1 batch, bulk-switches all cloned workflows to `draft`, executes the 5-layer governance un-nerf + pure-API Stripe SaaS Rebilling Hold (`saasMode: "setup_pending"` at `1.05x`), optionally mints 180-scope Private Integration Tokens (`pit-...`), and runs `location-clone-audit` across every created workspace.
- **Headless Private Integration Token (`pit-...`) Creation & Deletion (`pit-create` / `pit-delete`):** `POST /marketplace/private-integration/location/:locationId` (with `"locationId": locationId` in the JSON body and all 180 sub-account V2 scopes derived by subtracting the 13 agency-only scopes from `GET /oauth/static/scopes`) mints a new sub-account Private Integration Token and returns `activeToken` (`pit-...`). Pass `--save-profile <name>` to store it directly in `~/.config/legends-gohighlevel/config.json`. Delete an integration with `DELETE /marketplace/private-integration/location/:locationId/integration/:integrationId` (`pit-delete`).
- **Internal Workflow Step Graph X-Ray & Bulk Step Rebrand (`agency-workflow-xray` / `workflow-steps-rebrand`):** `GET /workflow/:locationId/:workflowId` returns the complete internal workflow definition inside `workflowData.templates` and `workflowData.triggers`. Even when workflows use Email Builder templates or Custom Values, individual workflow steps often hardcode `attributes.from_name`, `attributes.from_email`, `attributes.preHeader`, `attributes.subject`, `attributes.url` (webhooks), or Meta CAPI `attributes.pixel_id` and `attributes.access_token`. Run `legends-gohighlevel agency-workflow-xray --location-id LOCATION_ID --brand-terms "oldbrand"` to inspect every step across all workflows, and `legends-gohighlevel workflow-steps-rebrand --location-id LOCATION_ID --replace-from "OldBrand,oldbrand.com" --replace-to "NewBrand,newbrand.com" --pixel-id NEW_PIXEL_ID` (`PUT /workflow/:locationId/:workflowId`) to bulk-rewrite workflow steps without opening the UI.
- **Agency-Level Atomic Sub-Account Rebrand (`location-rebrand`):** `legends-gohighlevel location-rebrand --location-id LOCATION_ID --name "New Brand" --replace-from "OldBrand,oldbrand.com" --replace-to "NewBrand,newbrand.com" --include-workflow-steps` rewrites Business Profile, Custom Values, Trigger Links, Calendars, and internal Workflow Steps in a single preview-confirmed command.
- **Snapshot Share Links (`snapshot-share-link`):** `POST /snapshots/share/v2/link` generates a shareable snapshot link (`link`, `permanent_link`, `agency_restricted`, or `location_restricted`).
