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
