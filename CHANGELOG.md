# Changelog

## 0.3.2 (2026-11-05)

- Added `setup.py` build-time wheel data mirror (`legends_gohighlevel/_data/`), `.legends-module`, `assets/manifest.json`, `scripts/smoke_installed_resources.py`, and `scripts/verify_knowledge_attachment.py` so standalone wheel installs resolve all knowledge packs, recipes, and references outside a source checkout.
- Updated `resolve_resources()` in `legends_gohighlevel/cli.py` to check `legends_gohighlevel/_data` first and aligned `knowledge/gohighlevel/pack.json` version with the package release.
- Upgraded `scripts/check_release.py` and `.github/workflows/checks.yml` with Gold-Standard EDR/metadata/dash gates and multi-OS `empire-attachment` CI verification.

## 0.3.1 (2026-11-04)

- **Endpoint Security (EDR) Hardening (`legends_gohighlevel/api.py`, `AGENTS.md`, `docs/AGENT-RECIPE.md`, `README.md`, `docs/catalog-entry.candidate.json`):** Removed local desktop browser `IndexedDB` directory scraping (`extract_local_token_from_indexeddb` and `local_indexeddb_path`) and added explicit agent guardrails prohibiting local Chrome, Brave, or Edge profile directory access so Python processes never trigger endpoint infostealer heuristics on Windows or macOS workstations. `BackendClient` resolves `token-id` strictly from `GHL_TOKEN_ID` or remote headless container `worker_ssh`.
- **Release Hygiene (`scripts/check_release.py`, `docs/EMPIRE.md`):** Added automated release verification against ASCII control characters and `U+FFFD` replacement diamonds, and aligned `legends-empire` CLI examples in `docs/EMPIRE.md`.

## 0.3.0 (2026-10-31)

- Upgraded `live-audit` to a full **5-layer live agency audit**:
  - **Layer 1 (Location feature flags):** Audits all 40 boolean switches in `location.permissions` (`UNNERFED_LOCATION_PERMISSIONS`) and `reseller` initialization; added preview-first `location-unnerf`.
  - **Layer 2 (User V1/V2 scopes, worker health, and `+hubpro` aliases):** Expanded `UNNERFED_V1_PERMISSIONS` to all 57 camelCase boolean keys returned by `GET /users/{id}`, verified 130/130 active Account Admin V2 scopes (`CRITICAL_ACCOUNT_ADMIN_V2_SCOPES`), and handled optional `AGENCY_ONLY_V2_SCOPES` on agency workers.
  - **Layer 3 (Reporting V2 Dashboard RBAC):** Audits both `defaultDashboardId` and all custom `sharedDashboards` per sub-account (`unlock-dashboards`).
  - **Layer 4 (Custom SMTP locks):** Audits and unlocks `blockAddSmtp` at both company and location levels (`smtp-status`, `smtp-unlock`).
  - **Layer 5 (4-store + 14-product SaaS Billing v2 rebilling):** Expanded `SAAS_BILLING_V2_KEYS` from 11 to all 14 metered usage products (adding `whatsApp`, `emailWarmup`, and `creatorStudio`) and added `rebilling-status` and preview-first `rebilling-sync` across `saas-billing-v2`, `update-twilio-rebilling`, `location.settings.saasSettings`, and `location-metadata`.
- Added HighLevel October 2026 / LevelUp 2026 API v2 and Workflows API v3 (`Version: v3`) commands on `Client` (`https://services.leadconnectorhq.com`):
  - **Workflows API v3 (`Version: v3`):** `workflow-step-types`, `workflow-inspect`, `workflow-logs`, `workflow-validate`, and preview-first `workflow-status` (`published` / `draft`), with explicit `WORKFLOW_API_NOT_ENABLED_FOR_LOCATION` detection.
  - **Agent Studio (Voice AI & Conversation AI):** `voice-ai-agents`, PII-lean `voice-ai-calls`, and `conversation-ai-agents`.
  - **Custom Objects & Associations v2:** `objects`, `object-records`, and `associations`.
  - **Funnels, Redirects, & Tags:** `funnels` (with `--include-redirects` and automatic `limit <= 20` redirect pagination), `tags`, `tag-upsert`, and `tag-delete`.
  - **Sub-Account Owner Health & CRM Mutations:** Added `subaccount-config` and `--profile <name>` (supporting multi-sub-account profiles in `~/.config/legends-gohighlevel/config.json`), `subaccount-audit` (1-command sub-account health, CAN-SPAM/A2P profile completeness, workflow status, and empty custom-value audit), `calendar-slots`, and preview-first `contact-upsert`, `contact-tag`, `contact-note`, and `opportunity-update` with SHA-256 confirmation and API readback.
- Added `local_indexeddb_path` support in `BackendClient` alongside `GHL_TOKEN_ID` and `worker_ssh` so agency owners running a local browser profile can use `BackendClient` without SSH or Docker.
- Added internal backend Private Integration Token metadata inspection (`pit-list`, masked token suffixes and scopes) and LC Email / Mailgun dedicated sending domain inspection (`email-domains`).
- Sanitized `legends_gohighlevel/social.py` (`ghl-x-bridge`) for open-source portability (env-driven credentials via `os.environ` / `GHL_ENV_FILE` and configurable `~/.config/legends-gohighlevel/x-bridge` state directory).

## 0.2.0 (2026-10-24)

- Added internal web-app and agency backend client (`BackendClient`, `https://backend.leadconnectorhq.com`) with safe worker Firebase `token-id` resolution from `GHL_TOKEN_ID` or SSH IndexedDB extraction (`~/.config/legends-gohighlevel/agency.json`).
- Added live 3-layer agency health and permission audit (`live-audit`) checking location feature flags, user V1/V2 scopes and `assignedToSupported` ("Only Assigned Data"), `+hubpro` alias `locationIds` synchronization, and Reporting V2 Default Dashboard per-role RBAC across all sub-accounts.
- Added live agency and dashboard commands: `agency-config`, `agency-locations`, `agency-users`, `user-inspect`, preview-first `user-sync-locations`, `dashboard-permissions`, preview-first `unlock-dashboards`, and offline `dashboard-audit`.
- Added [wiki/internal-backend-and-dashboards.md](wiki/internal-backend-and-dashboards.md) documenting the 3-layer permission architecture, Reporting V2 Default Dashboard RBAC (`permissionAccess` DTO contract), and `PUT /users/:id` top-level `companyId` validation rules.

## 0.1.0 (2026-10-22)

- Initial public release of `legends-gohighlevel` (superseding the earlier private `legends-gohighlevel-kit`).
- Pure Python 3.10+ standard-library CLI (`legends-gohighlevel`) with zero external runtime dependencies.
- Sub-account Official HighLevel API v2 inspection across locations, custom values, custom fields, pipelines, opportunities, calendars, workflows, forms, surveys, and PII-lean contacts and conversations.
- Preview-first custom-value mutations (`custom-value-upsert`, `custom-value-delete`) with SHA-256 plan confirmation (`--apply --confirm-location --confirm-plan`) and post-write API readback verification.
- Deterministic agency governance calculators and payload builders (`rebilling-audit`, `scope-audit`, `smtp-audit`) covering the `1.05x` (`db_markup=5`) Stripe fee shield, 4-store rebilling synchronization, V1/V2 user permission rules, worker scope inheritance, and two-level Custom SMTP unlocking.
- Attachable `legends.knowledge-pack/v1` knowledge vault (`knowledge/gohighlevel/pack.json`) and Empire templates.
