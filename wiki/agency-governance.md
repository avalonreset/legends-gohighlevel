# Agency governance, un-nerfing, and safe rebilling

When operating a GoHighLevel Agency account (such as the \$297 Agency Unlimited plan) that provisions sub-accounts for members or clients, HighLevel initializes several hidden restrictions and markup defaults. Use the governance and live-audit commands to audit and verify safe configurations.

## 1. The rebilling markup formula and `1.05x` Stripe fee shield

In HighLevel's agency billing frontend (`locations` bundle), the UI multiplier (`1.05x`, `1.10x`, `6.00x`) is computed from the database integer `markup` field using:

```text
ui_multiplier = (parseInt(db_markup) + 100) / 100
db_markup     = round(ui_multiplier * 100 - 100)
```

- `db_markup: 0` = `1.00x` (0% markup)
- `db_markup: 5` = `1.05x` (+5% markup, HighLevel's built-in default on the \$297 plan)
- `db_markup: 10` = `1.10x` (+10% markup)

### Why `db_markup: 5` (`1.05x`) is the safe zero-loss floor

Sub-account usage (SMS, voice, LC Email, Content AI, Voice AI, Conversation AI, Reviews AI, Workflow Premium Actions, WhatsApp, Email Warmup, Creator Studio) runs on a **pre-paid wallet model**:

1. The sub-account owner attaches their credit card via Stripe (`Rebilling is on hold, pending payment` until a card is added).
2. When the sub-account tops up its wallet by **\$10.00**, Stripe deducts **`2.9% + $0.30` (\$0.59)** from the \$10.00 charge, depositing **\$9.41** into the agency's Stripe account.
3. If the agency sets `db_markup: 0` (`1.00x`), the sub-account unlocks a full **\$10.00** of wholesale usage on the agency's master HighLevel balance while the agency only netted **\$9.41** after Stripe fees, causing an automatic **-\$0.59 out-of-pocket loss** on every \$10.00 reload.
4. At `db_markup: 5` (`1.05x`), a \$10.00 wallet reload unlocks **\$9.52** (`$10.00 / 1.05`) of wholesale usage, offsetting Stripe's processing fee so the agency never loses money out of pocket.

Run the deterministic rebilling calculator and 4-store payload generator at any time:

```sh
legends-gohighlevel rebilling-audit --wallet-topup 10.00 --markup 5 --location-id LOCATION_ID
```

## 2. The four HighLevel rebilling stores and 14 SaaS Billing v2 products

HighLevel stores rebilling markups across **four separate backend endpoints** that must be kept in sync per location:

1. **SaaS Billing v2 (`GET /saas-billing-v2/billing-config/LOCATION/{locationId}` and `PUT /saas-billing-v2/billing-config/group/{locationId}/{keys}`):** Controls all **14 metered usage products**: `workflow_premium_actions`, `workflow_ai`, `conversation_AI`, `voiceAI`, `contentAI`, `reviewsAI`, `agentStudio`, `askai`, `aiStudio`, `EmailVerification`, `domainPurchase`, `whatsApp`, `emailWarmup`, and `creatorStudio`.
   - Required `PUT` payload: `{"entityType": "LOCATION", "enabled": true, "optIn": true, "markups": {"workflow_premium_actions": 5, ...}}` (where `enabled` is `true` for `activated` or `setup_pending` locations, and `false` for `not_activated` locations).
2. **Twilio / LC Phone Rebilling (`POST /saas_service/saas-config/{locationId}/update-twilio-rebilling`):** `{"enabled": true, "markup": 5}` (succeeds with plain-text `"OK"` when `saasMode == "activated"`).
3. **Location SaaS Settings (`PUT /locations/{locationId}`):** Updates `settings.saasSettings.twilioRebilling` (`{"enabled": isActivated, "markup": 5}`) and `settings.saasSettings.mailgunRebilling` (`{"enabled": isActivated, "markup": 5, "price": 0.00070875}`).
4. **Location Metadata (`PUT /saas-api/location-metadata/{locationId}`):** Syncs `attachedRebillingConfig` (`Phone` and `Email` at `markup: 5`), `twilioRebilling`, and `mailgunRebilling`.

Inspect or synchronize all 4 stores across the agency with:

```sh
legends-gohighlevel rebilling-status --all-locations
legends-gohighlevel rebilling-sync --all-locations --markup 5
legends-gohighlevel rebilling-sync --all-locations --markup 5 --apply --confirm-plan SHA256_FROM_PREVIEW
```

## 3. Unlocking Custom SMTP (`Add Service` button)

By default, HighLevel disables the **Add Service** button under **Settings > Email Services > SMTP & Mailgun Services** inside sub-accounts so users cannot connect third-party SMTP providers (`Brevo`, `SendGrid`, `Mailgun`, `Amazon SES`).

HighLevel enforces **two independent locks** that must both be set to `false`:

1. **Agency-wide default (`PUT /email-isv/Setting/feature/company/{companyId}`):**
   `{"emailIsvSettings": {"blockAddSmtp": false}}`
2. **Per-location lock (`PUT /email-isv/Setting/feature/location/{locationId}`):**
   `{"blockAddSmtp": false}` (stamped onto each location at creation time if the agency lock was previously enabled).

Generate and verify the exact unlock payloads offline or apply live with:

```sh
legends-gohighlevel smtp-audit --company-id COMPANY_ID --location-id LOCATION_ID
legends-gohighlevel smtp-status --all-locations
legends-gohighlevel smtp-unlock --all-locations
legends-gohighlevel smtp-unlock --all-locations --apply --confirm-plan SHA256_FROM_PREVIEW
```

## 4. Unlocking Default Dashboard per-role RBAC (`account_admin: full`, `account_user: full`)

When HighLevel provisions a new sub-account, it seeds the sub-account's Default Dashboard (`defaultDashboardId`) with only `agency_user: "full"` and `account_user: "read"`, omitting `account_admin`. Because `account_admin` is omitted, sub-account admins (`type: "account", role: "admin"`) receive `"You do not have permission to perform this operation"` (`errorType = "permission_error"`) when trying to edit or clone the Default Dashboard.

Unlocking `account_admin: "full"` and `account_user: "full"` on all default and custom dashboards via `POST /reporting/dashboards/{dashboardId}/permissions?locationId={locationId}` (`permissionAccess` field) is strictly scoped to that sub-account's dashboard and poses zero cross-tenant or agency risk.

Audit offline or unlock live across all agency sub-accounts:

```sh
legends-gohighlevel dashboard-audit --location-id LOCATION_ID --dashboard-id DASHBOARD_ID
legends-gohighlevel dashboard-permissions --all-locations
legends-gohighlevel unlock-dashboards --all-locations
legends-gohighlevel unlock-dashboards --all-locations --apply --confirm-plan SHA256_FROM_PREVIEW
```

## 5. Sub-account billing holds and 24-hour grace deletion

- **Billing Hold (`payment_method_required`):** Before releasing sub-account access to a member or client, enable Stripe rebilling on the location (`Rebilling is on hold, pending payment`) and grant the sub-account admin `locations.billing.manage` (`View and Manage Billing Details`) plus `internaltools.billing-common.write` (`Account Billing 1/1`) so they can enter their own payment card on `/v2/location/{locationId}/payment_setup`.
- **Soft Deletion (`DELETE /locations/{locationId}?newAccount=false`):** Deleting a sub-account schedules a 24-hour grace period (`deletionScheduledAt: now + 24h`) before permanent purge. Always remove or reassign orphan test users after retiring canary locations.
