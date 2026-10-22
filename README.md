<a name="banner"></a>
<a name="legends-gohighlevel"></a>

# ![legends-gohighlevel](assets/banner.webp)

[![release](https://img.shields.io/github/v/release/avalonreset/legends-gohighlevel?style=flat-square&label=release&labelColor=000000&color=ff0000)](https://github.com/avalonreset/legends-gohighlevel/releases/latest)
[![checks](https://github.com/avalonreset/legends-gohighlevel/actions/workflows/checks.yml/badge.svg)](https://github.com/avalonreset/legends-gohighlevel/actions/workflows/checks.yml)
[![license](https://img.shields.io/github/license/avalonreset/legends-gohighlevel?style=flat-square&label=license&labelColor=000000&color=666666)](LICENSE)

**GoHighLevel CRM and sub-account governance CLI with preview-first changes, API readback, and a reusable knowledge vault.**

Use this Python **GoHighLevel CLI** with your agent to inspect sub-account CRM resources (pipelines, opportunities, contacts, calendars, conversations, workflows, forms, surveys, custom fields, and custom values), preview and verify custom-value mutations, audit agency rebilling and V1/V2 user scopes, and keep operating history in Markdown that works with Obsidian and [legends-empire](https://github.com/avalonreset/legends-empire).

This is an independent community project built on the official HighLevel API v2 (`services.leadconnectorhq.com`). HighLevel provides the CRM platform. This module adds a bounded CLI-first workflow, deterministic governance checks, and source-cited runbooks. It is not affiliated with or endorsed by HighLevel Inc.

## Why use this with an agent?

Connecting an ambient HighLevel MCP server exposes hundreds of unreviewed tools and pulls raw customer personal data into agent context. Calling raw endpoints ad hoc leaves agents guessing about V1 vs. V2 user scopes, rate-limit headers, Custom SMTP locks, and multi-store rebilling math.

| Need | What this module supplies |
|---|---|
| Inspect CRM state without MCP bloat | Deterministic JSON inspection across 10 HighLevel API v2 resource families with live `X-RateLimit-*` telemetry |
| Keep customer PII out of agent context | `contacts` and `conversations` default to PII-lean metadata (`--full` is explicit opt-in) |
| Review before mutating sub-account state | JSON preview with `before` state, `proposed` payload, and a canonical `sha256` confirmation hash |
| Verify what actually changed | Single-resource writes with zero automatic retries and immediate post-write API readback verification |
| Un-nerf sub-accounts and protect agency margins | Offline `rebilling-audit` (`1.05x` / `db_markup=5` Stripe fee shield across all 4 billing stores), `scope-audit` (V1/V2 user permissions and worker scope inheritance), and `smtp-audit` (two-level Custom SMTP unlock) |
| Reuse what you learn | Source ledger, operational runbooks, and an attachable `legends.knowledge-pack/v1` vault for `legends-empire` |
| Fit the existing ecosystem | One central `cto-legends` skill; module instructions loaded on demand |

## Install the GoHighLevel CLI

Python 3.10 or newer. Zero external runtime dependencies and no MCP server.

```sh
git clone https://github.com/avalonreset/legends-gohighlevel.git
cd legends-gohighlevel
python -m pip install .
legends-gohighlevel doctor
```

For live sub-account operations, load `GHL_PIT` (a sub-account Private Integration Token starting with `pit-`, or `GHL_ACCESS_TOKEN`) and `GHL_LOCATION_ID` from your secret manager into the process environment. The CLI never reads `.env` files automatically or accepts tokens on the command line.

```sh
legends-gohighlevel doctor --live
legends-gohighlevel location
legends-gohighlevel pipelines
legends-gohighlevel opportunities --status open --limit 20
legends-gohighlevel calendars
legends-gohighlevel workflows
legends-gohighlevel forms --limit 50
legends-gohighlevel surveys --limit 50
legends-gohighlevel custom-values
legends-gohighlevel custom-fields
legends-gohighlevel contacts --limit 20
legends-gohighlevel conversations --limit 20
```

## Preview and update sub-account custom values

```sh
legends-gohighlevel custom-value-upsert --name "Support Email" --value "help@example.com"
```

This reads current sub-account state and returns a preview plan (`writes_sent: 0`) with `before`, `proposed`, `action`, and `sha256`.

Only after approving that preview, repeat the command with `--apply`, `--confirm-location`, and `--confirm-plan`:

```sh
legends-gohighlevel custom-value-upsert --name "Support Email" --value "help@example.com" \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW
```

To delete a single custom value, obtain its ID from `custom-values`, preview first, and confirm with its exact ID and hash:

```sh
legends-gohighlevel custom-value-delete --name "Support Email" --custom-value-id EXACT_ID
legends-gohighlevel custom-value-delete --name "Support Email" --custom-value-id EXACT_ID \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW
```

## Audit agency rebilling, V2 user scopes, and Custom SMTP locks

Run the deterministic governance calculators offline (no credentials required):

```sh
legends-gohighlevel rebilling-audit --wallet-topup 10.00 --markup 5 --location-id LOCATION_ID
legends-gohighlevel scope-audit --role admin --account-type account
legends-gohighlevel smtp-audit --company-id COMPANY_ID --location-id LOCATION_ID
```

- **`rebilling-audit`:** Computes HighLevel's `ui_multiplier = (parseInt(db_markup) + 100) / 100` formula, Stripe's `2.9% + $0.30` processing fee on pre-paid wallet reloads, wholesale usage unlocked, net agency margin, and the exact 4-store synchronization payloads (`saas-billing-v2`, `update-twilio-rebilling`, `update-mailgun-rebilling`, and `location-metadata`).
- **`scope-audit`:** Audits HighLevel's 50 V1 `permissions` flags and 130+ V2 `scopes`, enforces mutual-exclusion rules (`workflows.readonly` vs. `workflows.write`, `campaigns.readonly` vs. `campaigns.write`), and detects when an Agency Admin creator would silently strip V2 scopes (`forms.write`, `surveys.write`, `pipelines.create`, `private-integration-location.readonly`) when creating a sub-account user.
- **`smtp-audit`:** Generates the two-level unlock payloads (`emailIsvSettings.blockAddSmtp: false` at the agency level and `blockAddSmtp: false` at the location level) required to enable the sub-account **Add Service** button for Custom SMTP providers (`Brevo`, `SendGrid`, `Mailgun`, `Amazon SES`).

## Knowledge vault and Empire

Start at [wiki/index.md](wiki/index.md) or attach the versioned knowledge pack at [knowledge/gohighlevel/pack.json](knowledge/gohighlevel/pack.json) (`legends.knowledge-pack/v1`). Open this repository folder in Obsidian or read it as plain Markdown.

Use [the Empire integration guide](docs/EMPIRE.md) to keep private workspace inventories, change receipts, and un-nerf audits in an existing project. Installing the module never modifies a personal vault automatically.

## CTO Legends router

The module recipe is [docs/AGENT-RECIPE.md](docs/AGENT-RECIPE.md). The vendored `skills/cto-legends/SKILL.md` is an unchanged copy of the central router. Do not register a separate GoHighLevel skill.

With the central [cto-legends](https://github.com/avalonreset/cto-legends) router:

```sh
cto-legends sync
cto-legends sync --apply
cto-legends install legends-gohighlevel
cto-legends install legends-gohighlevel --apply
cto-legends handoff legends-gohighlevel
cto-legends run legends-gohighlevel -- doctor
```

## Boundaries and verification

```sh
python -m unittest discover -s tests -v
python scripts/check_release.py
```

Exit codes: `0` completed inspection, preview, governance audit, or verified change; `1` operational failure; `2` invalid CLI syntax. A failed write or readback can mean remote state changed: inspect it before retrying.

See [compatibility and verification](docs/RELEASE-READINESS.md), [contributing](CONTRIBUTING.md), [security](SECURITY.md), and [attribution](THIRD_PARTY_NOTICES.md). MIT licensed.
