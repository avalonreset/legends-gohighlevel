<a name="banner"></a>
<a name="legends-gohighlevel"></a>

# ![legends-gohighlevel](assets/banner.webp)

[![release](https://img.shields.io/github/v/release/avalonreset/legends-gohighlevel?style=flat-square&label=release&labelColor=000000&color=ff0000)](https://github.com/avalonreset/legends-gohighlevel/releases/latest)
[![checks](https://img.shields.io/github/actions/workflow/status/avalonreset/legends-gohighlevel/checks.yml?branch=main&style=flat-square&label=checks&labelColor=000000)](https://github.com/avalonreset/legends-gohighlevel/actions/workflows/checks.yml)
[![license](https://img.shields.io/github/license/avalonreset/legends-gohighlevel?style=flat-square&label=license&labelColor=000000&color=666666)](LICENSE)

**GoHighLevel API v2, Workflows v3, Voice/Conversation AI, Custom Objects, Snapshots V2 Batch Cloning, Workflow Step X-Ray, Atomic Rebranding, and 5-layer SaaS agency governance CLI with preview-first mutations, API readback, and a reusable knowledge vault.**

Use this 110-command Python **GoHighLevel CLI** (`legends-gohighlevel`) with your coding agent across both **Sub-Account Operator** (`GHL_PIT` / multi-profile `config.json`) and **Agency Owner** (`GHL_TOKEN_ID` / `worker_ssh`) planes:
- **Sub-Account CRM, Multi-Location Profiles, Atomic Rebranding, Social Planner & Commerce (`services.leadconnectorhq.com`):** Audit and operate GoHighLevel / HighLevel sub-accounts (`doctor`, `resources`, `subaccount-audit`, `subaccount-rebrand-audit`, `profiles-matrix`, `subaccount-profile-set`/`use`/`delete`, `subaccount-update`, `subaccount-rebrand`, `location`, `subaccount-users`, `pipelines`, `opportunities`, `contacts`, `contact-notes`, `contact-tasks`, `tags`, `calendars`, `calendar-slots`, `calendar-events`, `appointment-create`, `conversations`, `conversation-messages`, `conversation-send`, `workflows`, `workflow-step-types`, `workflow-inspect`, `workflow-logs`, `workflow-validate`, `email-templates`, `trigger-links`, `forms`, `surveys`, `funnels`, `medias`, `products`, `invoices`, `transactions`, `blogs`, `social-accounts`, `social-posts`, `x-bridge-status`, `x-bridge-sync`, `objects`, `object-records`, `associations`, `voice-ai-agents`, `voice-ai-calls`, `conversation-ai-agents`, `custom-fields`, and `custom-values`).
- **Agency Snapshots V2, 1-Command Batch Cloning, A2P 10DLC Trust Center, Headless PIT Minting, Workflow X-Ray & 5-Layer Governance (`backend.leadconnectorhq.com`):** Clone and provision $N$ sub-accounts in a single command (`location-batch-clone`, `location-create`, `location-rename`, `snapshots-list`, `snapshot-inspect`, `snapshot-create`, `snapshot-refresh`, `snapshot-push`, `snapshot-share-link`), audit and stage A2P 10DLC Trust Center and LC Phone compliance (`a2p-preflight`, `a2p-campaign-pack`, `a2p-trust-center-status`, `a2p-trust-center-stage`), mint 180-scope Private Integration Tokens headlessly (`pit-create`, `pit-list`, `pit-delete`), X-Ray and rebrand internal workflow step graphs (`agency-workflow-xray`, `workflow-steps-rebrand --templatize-senders`, `workflow-bulk-status`, `location-rebrand`), and run live 5-layer agency and dashboard RBAC governance (`live-audit`, `location-full-unnerf`, `location-unnerf`, `user-unnerf`, `user-sync-locations`, `unlock-dashboards`, `smtp-unlock`, `rebilling-sync`, `email-domains`) while keeping operating history in Markdown that works with Obsidian and [`legends-empire`](https://github.com/avalonreset/legends-empire).

This is an independent open-source project built on the official HighLevel API v2 and Workflows API v3 (`services.leadconnectorhq.com`) and HighLevel's web-app governance endpoints (`backend.leadconnectorhq.com`). HighLevel provides the CRM platform. This module adds a bounded CLI-first workflow, deterministic governance checks, and source-cited runbooks. It is not affiliated with or endorsed by HighLevel Inc.

## Why use this instead of an ambient GoHighLevel MCP server?

Connecting an ambient HighLevel / LeadConnector MCP server exposes hundreds of unreviewed tools and pulls raw customer personal data into agent context. Calling raw endpoints ad hoc leaves agents guessing about 40 location feature flags, 57 V1 boolean permissions, 130 V2 user scopes, Reporting V2 per-dashboard RBAC (`permissionAccess`), `+hubpro` alias location sync, rate-limit headers, Custom SMTP locks, and 4-store + 14-product SaaS Billing v2 rebilling math.

| Need | What this module supplies |
|---|---|
| Inspect CRM, Commerce, AI, and Workflows v3 without MCP bloat | Deterministic JSON inspection across 26 HighLevel API v2 and v3 resource families with live `X-RateLimit-*` telemetry and multi-profile switching (`--profile`, `profiles-matrix`) |
| Clone $N$ sub-accounts from a Snapshot in 1 command | `location-batch-clone` creates $N$ sub-accounts, pushes a V2 snapshot in 1 batch, bulk-drafts all cloned workflows, runs the 5-layer governance un-nerf + Stripe SaaS Rebilling Hold (`setup_pending`), mints `pit-...` tokens (`--create-pits`), and audits every clone |
| Mint 180-scope Private Integration Tokens (`pit-...`) headlessly | `pit-create` discovers all 180 valid `location`-level OAuth v2 scopes (`GET /oauth/static/scopes` minus agency-only scopes), mints the `pit-...` token via API, and optionally saves it directly to `~/.config/legends-gohighlevel/config.json` (`--save-profile`) |
| X-Ray & rebrand internal workflow steps (`workflowData.templates`) | `agency-workflow-xray` and `workflow-steps-rebrand` inspect and rewrite internal workflow email `from_name`/`from_email`/`subject`/`preHeader`, Meta CAPI `pixel_id`, and brand strings, or convert hardcoded senders to `{{custom_values.*}}` (`--templatize-senders`) |
| Rebrand a sub-account atomically in 1 command | `subaccount-rebrand` (via `GHL_PIT`) and `location-rebrand` (via agency backend) preview and execute atomic find/replace across Business Profile, Custom Values, Trigger Links, Calendars, and internal Workflow Steps |
| Audit a sub-account in one command | `subaccount-audit` and `subaccount-rebrand-audit` check CAN-SPAM/A2P business profile completeness, pipelines, open opportunities, published vs. draft workflows, empty custom values, calendars, forms, funnels, tags, Voice AI, Conversation AI, and leftover template brand terms |
| Audit & un-nerf all 5 agency governance layers in seconds | Live `live-audit` and 1-command `location-full-unnerf` covering 40 location flags, 57 V1 + 130 V2 user scopes + `+hubpro` aliases, Reporting V2 dashboard RBAC, two-level Custom SMTP locks, and 4-store + 14-product `1.05x` SaaS Billing v2 rebilling |
| Keep customer PII out of agent context | `contacts`, `conversations`, and `voice-ai-calls` default to PII-lean metadata (`--full` is explicit opt-in) |
| Review before mutating sub-account or agency state | JSON preview (`writes_sent: 0`) with `before` state, `proposed` payload, and a canonical `sha256` confirmation hash plus immediate post-write API readback |
| Reuse what you learn | Source ledger, operational runbooks, and an attachable `legends.knowledge-pack/v1` vault for [`legends-empire`](https://github.com/avalonreset/legends-empire) |
| Fit the existing ecosystem | One central [`cto-legends`](https://github.com/avalonreset/cto-legends) skill; module instructions loaded on demand |

## Install the GoHighLevel CLI

Python 3.11 or newer. Zero external runtime dependencies and no MCP server.

```sh
git clone https://github.com/avalonreset/legends-gohighlevel.git
cd legends-gohighlevel
python -m pip install .
legends-gohighlevel doctor
```

For live sub-account CRM operations, load `GHL_PIT` (a sub-account Private Integration Token starting with `pit-`, or `GHL_ACCESS_TOKEN`) and `GHL_LOCATION_ID` from your secret manager into the process environment, or configure named sub-account profiles in `~/.config/legends-gohighlevel/config.json` (selectable via `--profile <name>` or `GHL_PROFILE`).

```sh
legends-gohighlevel resources
legends-gohighlevel subaccount-config
legends-gohighlevel subaccount-profile-set --profile-name client-a --location-id LOCATION_ID --pit @/path/to/pit.txt --set-default
legends-gohighlevel doctor --live
legends-gohighlevel subaccount-audit
legends-gohighlevel subaccount-rebrand-audit --brand-terms "oldbrand,olddomain.com"
legends-gohighlevel profiles-matrix
legends-gohighlevel --profile second-subaccount subaccount-audit
legends-gohighlevel location
legends-gohighlevel subaccount-users
legends-gohighlevel pipelines
legends-gohighlevel opportunities --status open --limit 20
legends-gohighlevel calendars
legends-gohighlevel calendar-slots --calendar-id CALENDAR_ID --start-date 1793491200000 --end-date 1793664000000
legends-gohighlevel calendar-events --calendar-id CALENDAR_ID
legends-gohighlevel workflows
legends-gohighlevel email-templates --limit 100
legends-gohighlevel trigger-links
legends-gohighlevel workflow-step-types
legends-gohighlevel workflow-inspect --workflow-id WORKFLOW_ID
legends-gohighlevel workflow-logs --workflow-id WORKFLOW_ID --limit 25
legends-gohighlevel workflow-validate --definition-json ./workflow-def.json
legends-gohighlevel forms --limit 50
legends-gohighlevel surveys --limit 50
legends-gohighlevel funnels --include-redirects
legends-gohighlevel tags
legends-gohighlevel medias --limit 50
legends-gohighlevel products --limit 50
legends-gohighlevel invoices --limit 50
legends-gohighlevel transactions --limit 50
legends-gohighlevel blogs --limit 20
legends-gohighlevel social-accounts
legends-gohighlevel social-posts --limit 25
legends-gohighlevel x-bridge-status
legends-gohighlevel x-bridge-sync
legends-gohighlevel objects
legends-gohighlevel object-records --object-key custom_objects.vehicles --limit 20
legends-gohighlevel associations
legends-gohighlevel voice-ai-agents
legends-gohighlevel voice-ai-calls --limit 20
legends-gohighlevel conversation-ai-agents
legends-gohighlevel custom-values
legends-gohighlevel custom-fields
legends-gohighlevel contacts --limit 20
legends-gohighlevel contact-notes --contact-id CONTACT_ID
legends-gohighlevel contact-tasks --contact-id CONTACT_ID
legends-gohighlevel conversations --limit 20
legends-gohighlevel conversation-messages --conversation-id CONVERSATION_ID
```

## Live 5-layer agency, user scope, dashboard RBAC, SMTP, and rebilling control

For live agency governance over `backend.leadconnectorhq.com`, set `GHL_TOKEN_ID` in the environment or configure `~/.config/legends-gohighlevel/agency.json` (with `company_id`, `worker_ssh`, `worker_container`, and `worker_user_id` for a remote headless worker):

```sh
legends-gohighlevel agency-config
legends-gohighlevel live-audit
legends-gohighlevel agency-locations
legends-gohighlevel agency-users
legends-gohighlevel user-inspect --email user@example.com
legends-gohighlevel dashboard-permissions --all-locations
legends-gohighlevel smtp-status --all-locations
legends-gohighlevel rebilling-status --all-locations
legends-gohighlevel pit-list --location-id LOCATION_ID
legends-gohighlevel email-domains --location-id LOCATION_ID
```

Preview and apply 5-layer remediation across one or all locations:

```sh
# Layer 1: Un-nerf all 40 location.permissions boolean feature flags
legends-gohighlevel location-unnerf --all-locations
legends-gohighlevel location-unnerf --all-locations --apply --confirm-plan SHA256_FROM_PREVIEW

# Layer 2: Un-nerf user V1/V2 scopes and synchronize +hubpro alias locationIds
legends-gohighlevel user-unnerf --email user@example.com
legends-gohighlevel user-unnerf --email user@example.com --apply --confirm-user USER_ID --confirm-plan SHA256_FROM_PREVIEW
legends-gohighlevel user-sync-locations --user-id PRIMARY_USER_ID --from-user-id ALIAS_USER_ID
legends-gohighlevel user-sync-locations --user-id PRIMARY_USER_ID --from-user-id ALIAS_USER_ID \
  --apply --confirm-user PRIMARY_USER_ID --confirm-plan SHA256_FROM_PREVIEW

# Layer 3: Unlock Reporting V2 Default and Custom Dashboard RBAC (account_admin: full, account_user: full)
legends-gohighlevel unlock-dashboards --all-locations
legends-gohighlevel unlock-dashboards --all-locations --apply --confirm-plan SHA256_FROM_PREVIEW

# Layer 4: Unlock Custom SMTP Add Service button at agency and location levels
legends-gohighlevel smtp-unlock --all-locations
legends-gohighlevel smtp-unlock --all-locations --apply --confirm-plan SHA256_FROM_PREVIEW

# Layer 5: Synchronize 1.05x (markup: 5) rebilling across all 4 stores and 14 SaaS Billing v2 products
legends-gohighlevel rebilling-sync --all-locations --markup 5
legends-gohighlevel rebilling-sync --all-locations --markup 5 --apply --confirm-plan SHA256_FROM_PREVIEW

# 1-Command 5-Layer Full Un-Nerf (all 5 governance layers in one preview + apply)
legends-gohighlevel location-full-unnerf --location-id LOCATION_ID --email user@example.com
legends-gohighlevel location-full-unnerf --location-id LOCATION_ID --email user@example.com \
  --apply --confirm-plan SHA256_FROM_PREVIEW

# Agency Snapshots V2, 1-Command Multi-Sub-Account Batch Cloning, PIT Minting & Workflow Step X-Ray
legends-gohighlevel snapshots-list
legends-gohighlevel snapshot-inspect --snapshot-id SNAPSHOT_ID
legends-gohighlevel snapshot-create --name "Master Snapshot" --location-id SOURCE_LOCATION_ID --wait
legends-gohighlevel snapshot-refresh --snapshot-id SNAPSHOT_ID --wait
legends-gohighlevel snapshot-share-link --snapshot-id SNAPSHOT_ID --share-type permanent_link
legends-gohighlevel snapshot-push --snapshot-id SNAPSHOT_ID --location-ids TARGET_LOC_1,TARGET_LOC_2
legends-gohighlevel snapshot-push --snapshot-id SNAPSHOT_ID --location-ids TARGET_LOC_1,TARGET_LOC_2 \
  --apply --confirm-plan SHA256_FROM_PREVIEW
legends-gohighlevel location-create --name "New Client Co" --email "dispatch@example.com" --from-location-id SOURCE_LOC_ID
legends-gohighlevel location-rename --location-id LOCATION_ID --name "Updated Client Co"
legends-gohighlevel location-batch-clone --source-location-id SOURCE_LOC_ID --snapshot-id SNAPSHOT_ID \
  --names "Client Clone 1,Client Clone 2,Client Clone 3,Client Clone 4" --assign-email user@example.com --create-pits
legends-gohighlevel pit-create --location-id LOCATION_ID --name "Agent Integration" --save-profile client-1
legends-gohighlevel agency-workflows --location-id LOCATION_ID
legends-gohighlevel agency-workflow-xray --location-id LOCATION_ID --brand-terms "oldbrand,olddomain.com"
legends-gohighlevel workflow-steps-rebrand --location-id LOCATION_ID --replace-from "OldBrand,olddomain.com" --replace-to "NewBrand,newdomain.com" --pixel-id NEW_PIXEL_ID
legends-gohighlevel workflow-bulk-status --location-id LOCATION_ID --status draft
legends-gohighlevel workflow-bulk-status --location-id LOCATION_ID --status draft --apply --confirm-plan SHA256_FROM_PREVIEW
legends-gohighlevel location-clone-audit --location-id LOCATION_ID --brand-terms "oldbrand"
legends-gohighlevel location-rebrand --location-id LOCATION_ID --name "NewBrand Co" --replace-from "OldBrand" --replace-to "NewBrand" --include-workflow-steps
legends-gohighlevel a2p-preflight --location-id LOCATION_ID --brand-name "Example Concrete" --website "https://example.com" --email "dispatch@example.com" --phone "+15122345678"
legends-gohighlevel a2p-campaign-pack --location-id LOCATION_ID --brand-name "Example Concrete" --website "https://example.com" --email "dispatch@example.com" --phone "+15122345678"
legends-gohighlevel a2p-trust-center-status --location-id LOCATION_ID --area-code 512
legends-gohighlevel a2p-trust-center-stage --location-id LOCATION_ID --brand-name "Example Concrete" --legal-name "Example Concrete LLC" --ein "12-3456789" \
  --website "https://example.com" --email "dispatch@example.com" --phone "+15122345678" --address "100 Main St" --city "Austin" --state "TX" --postal-code "78701" \
  --rep-first-name "Jane" --rep-last-name "Doe" --rep-email "jane.doe@example.com" --rep-phone "+15122345678"
```

## Preview and update sub-account CRM state (`custom-value`, `tag`, `contact`, `opportunity`, `workflow`)

Every sub-account mutation runs in preview mode by default (`writes_sent: 0`) and requires `--apply --confirm-location <locationId> --confirm-plan <sha256>` with immediate post-write API readback verification:

```sh
legends-gohighlevel subaccount-update --name "New Brand LLC" --website "https://newbrand.com"
legends-gohighlevel subaccount-rebrand --name "New Brand LLC" --replace-from "OldBrand,oldbrand.com" --replace-to "NewBrand,newbrand.com"

legends-gohighlevel custom-value-upsert --name "Support Email" --value "help@example.com"
legends-gohighlevel custom-value-upsert --name "Support Email" --value "help@example.com" \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW

legends-gohighlevel custom-field-upsert --name "VAT Number" --data-type TEXT
legends-gohighlevel trigger-link-upsert --name "Booking CTA" --redirect-to "https://newbrand.com/book"
legends-gohighlevel calendar-update --calendar-id CALENDAR_ID --name "Discovery Call" --active
legends-gohighlevel appointment-create --calendar-id CALENDAR_ID --contact-id CONTACT_ID --start-time "2026-12-01T14:00:00Z" --title "Discovery Call"

legends-gohighlevel tag-upsert --name "vip-client"
legends-gohighlevel tag-upsert --name "vip-client" \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW

legends-gohighlevel contact-upsert --email "jane@example.com" --first-name "Jane" --tags "vip-client"
legends-gohighlevel contact-upsert --email "jane@example.com" --first-name "Jane" --tags "vip-client" \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW

legends-gohighlevel contact-tag --contact-id CONTACT_ID --tags "booked-call"
legends-gohighlevel contact-note --contact-id CONTACT_ID --body "Completed discovery call."
legends-gohighlevel contact-task-upsert --contact-id CONTACT_ID --title "Send onboarding deck"
legends-gohighlevel conversation-send --contact-id CONTACT_ID --type SMS --message "Looking forward to our call!"
legends-gohighlevel opportunity-update --opportunity-id OPP_ID --status won --monetary-value 2500

legends-gohighlevel workflow-status --workflow-id WORKFLOW_ID --status published
legends-gohighlevel workflow-status --workflow-id WORKFLOW_ID --status published \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW
```

## Audit agency rebilling, V2 user scopes, Custom SMTP locks, and dashboard RBAC offline

Run the deterministic governance calculators offline (no credentials required):

```sh
legends-gohighlevel rebilling-audit --wallet-topup 10.00 --markup 5 --location-id LOCATION_ID
legends-gohighlevel scope-audit --role admin --account-type account
legends-gohighlevel smtp-audit --company-id COMPANY_ID --location-id LOCATION_ID
legends-gohighlevel dashboard-audit --location-id LOCATION_ID --dashboard-id DASHBOARD_ID
```

## Knowledge vault and Empire

Start at [wiki/index.md](wiki/index.md) or attach the versioned knowledge pack at [knowledge/gohighlevel/pack.json](knowledge/gohighlevel/pack.json) (`legends.knowledge-pack/v1`). Open this repository folder in Obsidian or read it as plain Markdown.

Use [the Empire integration guide](docs/EMPIRE.md) to keep private workspace inventories, change receipts, and un-nerf audits in an existing project. Installing the module never modifies a personal vault automatically.

## Agent setup (via `cto-legends`)

The module recipe is [docs/AGENT-RECIPE.md](docs/AGENT-RECIPE.md). The vendored `skills/cto-legends/SKILL.md` is an unchanged copy of the central router. Do not register a separate GoHighLevel skill.

With the central [`cto-legends`](https://github.com/avalonreset/cto-legends) router:

```sh
cto-legends sync
cto-legends sync --apply
cto-legends install legends-gohighlevel
cto-legends install legends-gohighlevel --apply
cto-legends handoff legends-gohighlevel
cto-legends run legends-gohighlevel -- doctor
```

## Architecture and project layout

```text
Operator / Agent
  -> legends-gohighlevel CLI (sub-account plane + agency governance plane)
  -> Sub-account API v2 & Workflows v3 (services.leadconnectorhq.com via GHL_PIT / config.json)
  -> Internal agency backend (backend.leadconnectorhq.com via GHL_TOKEN_ID / remote worker_ssh)
  -> Plan builder (before-state snapshot + proposed payload + SHA-256 hash)
  -> Explicit confirmation (--apply --confirm-location/--confirm-user --confirm-plan)
  -> Single write request + immediate post-write API readback verification
```

- `legends_gohighlevel/`: Zero-dependency Python 3.11+ CLI (`cli.py`), dual-plane HTTP transport (`api.py`), sub-account CRM/AI/Workflows v3 operations (`crm.py`), 5-layer agency backend auditing and remediation (`agency.py`), deterministic governance calculators (`governance.py`), and sanitized social bridge (`social.py`).
- `wiki/` and `knowledge/gohighlevel/`: Source-cited runbooks (`agency-governance.md`, `internal-backend-and-dashboards.md`, `authentication.md`, `crm-operations.md`, `email-and-deliverability.md`, `troubleshooting.md`) and attachable [`legends-empire`](https://github.com/avalonreset/legends-empire) knowledge pack (`pack.json`).
- `docs/`: Agent recipe, Empire integration guide, release readiness, catalog candidate, and [search strategy](docs/SEARCH-STRATEGY.md).

## FAQ

**Can sub-account owners and multi-location managers use `legends-gohighlevel` without agency backend access?**
Yes. Sub-account operators only need a sub-account Private Integration Token (`GHL_PIT`, starting with `pit-`) and `GHL_LOCATION_ID` (or named profiles in `~/.config/legends-gohighlevel/config.json` managed via `subaccount-profile-set`, `subaccount-profile-use`, `subaccount-profile-delete`, and `profiles-matrix`). All 40 sub-account inspection, atomic rebranding (`subaccount-rebrand`, `subaccount-update`), CRM, calendar booking (`appointment-create`, `calendar-update`), messaging (`conversation-send`), commerce (`products`, `invoices`, `transactions`), AI (`voice-ai-agents`, `conversation-ai-agents`), and workflow commands run directly against `services.leadconnectorhq.com`.

**How do I clone multiple sub-accounts from a Snapshot, mint Private Integration Tokens, and rebrand all workflows and custom values?**
Run `legends-gohighlevel location-batch-clone --source-location-id <sourceId> --snapshot-id <snapshotId> --names "Clone 1,Clone 2,Clone 3,Clone 4" --assign-email <email> --create-pits` (preview first, then repeat with `--apply --confirm-plan <sha256>`). In a single pipeline, it creates all $N$ sub-accounts, pushes the V2 snapshot in one batch, bulk-switches all cloned workflows to `draft`, runs the 5-layer governance un-nerf + pure-API Stripe SaaS Rebilling Hold (`saasMode: "setup_pending"` at `1.05x`), and mints a 180-scope `pit-...` token for each clone. To inspect or rebrand hardcoded sender emails, Meta CAPI Pixel IDs, and brand strings inside workflow steps, run `agency-workflow-xray` and `workflow-steps-rebrand --templatize-senders` (or `location-rebrand --include-workflow-steps`).

**Does `legends-gohighlevel` modify CRM records, workflows, or agency settings immediately?**
No. Every mutation command (`subaccount-update`, `subaccount-rebrand`, `custom-value-upsert`, `custom-value-delete`, `custom-field-upsert`, `custom-field-delete`, `trigger-link-upsert`, `trigger-link-delete`, `calendar-update`, `appointment-create`, `tag-upsert`, `tag-delete`, `contact-upsert`, `contact-tag`, `contact-note`, `contact-task-upsert`, `conversation-send`, `opportunity-update`, `workflow-status`, `location-create`, `location-batch-clone`, `location-rebrand`, `location-full-unnerf`, `location-unnerf`, `user-unnerf`, `user-sync-locations`, `unlock-dashboards`, `smtp-unlock`, `rebilling-sync`, `snapshot-create`, `snapshot-refresh`, `snapshot-push`, `snapshot-share-link`, `workflow-bulk-status`, `workflow-steps-rebrand`, `pit-create`, and `pit-delete`) defaults to a read-only preview (`writes_sent: 0`) that returns the `before` state, `proposed` payload, and a canonical `sha256` hash. Writes execute only when repeated with `--apply` and the matching `--confirm-plan <sha256>`.

**Why does a sub-account show a locked dashboard or missing features even when the user has admin scopes?**
HighLevel enforces permissions across five independent layers: location-level feature flags (`location.permissions`), user V1 boolean flags and V2 scopes (`scopes` + `scopesAssignedToOnly`), Reporting V2 per-dashboard RBAC (`permissionAccess`), two-level Custom SMTP locks (`blockAddSmtp`), and 4-store SaaS Billing v2 rebilling. Run `legends-gohighlevel live-audit` to inspect all five layers across every sub-account in one pass, or `legends-gohighlevel location-full-unnerf` to remediate all five layers in a single confirmed plan.

## Boundaries and verification

```sh
python -m unittest discover -s tests -v
python scripts/check_release.py
```

Exit codes: `0` completed inspection, preview, governance audit, or verified change; `1` operational failure; `2` invalid CLI syntax. A failed write or readback can mean remote state changed: inspect it before retrying.

See [compatibility and verification](docs/RELEASE-READINESS.md), [search positioning](docs/SEARCH-STRATEGY.md), [contributing](CONTRIBUTING.md), [security](SECURITY.md), and [attribution](THIRD_PARTY_NOTICES.md). MIT licensed.

---

**Specification & benchmarks on cto-legends.com:**
- **Module specification & architecture matrix:** [cto-legends.com/modules/legends-gohighlevel](https://cto-legends.com/modules/legends-gohighlevel)
- **Related engineering dispatches:** [How to Build AI Agents: Production CLI & MCP Routing](https://cto-legends.com/blog?post=how-to-build-ai-agents-cli-mcp-routing) · [Claude Code Skills: MCP vs CLI Workflow Architecture](https://cto-legends.com/blog?post=claude-code-skills-mcp-vs-cli-workflow) · [Fractional CTO Advisory: Technical Due Diligence Guide](https://cto-legends.com/blog?post=fractional-cto-technical-due-diligence-guide)
- **Ecosystem hub:** [cto-legends.com/home](https://cto-legends.com/home)
