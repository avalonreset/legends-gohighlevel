# Operate legends-gohighlevel

1. Resolve the selected module source and user workspace. Never save private reports or CRM exports into a managed source checkout.
2. Run `legends-gohighlevel doctor`. This is offline and does not prove sub-account API access.
3. For authorized live sub-account work, load `GHL_PIT` (or `GHL_ACCESS_TOKEN`) and `GHL_LOCATION_ID` from your secret manager into the process environment and run `legends-gohighlevel doctor --live`.
4. Route read-only CRM discovery to `location`, `pipelines`, `opportunities`, `calendars`, `workflows`, `forms`, `surveys`, `custom-values`, `custom-fields`, `contacts`, or `conversations`. Keep `contacts` and `conversations` in their default PII-lean mode unless the user explicitly needs `--full` contact details.
5. Read `wiki/crm-operations.md` before mutating sub-account state. Preview `custom-value-upsert` or `custom-value-delete` first (`writes_sent: 0`). Show the exact `location_id`, `custom_value_id` if present, `before` state, `proposed` payload, and `sha256`.
6. After owner authorization, apply the exact request using `--apply --confirm-location <locationId> --confirm-plan <sha256>`. A stale plan hash must be previewed again.
7. Check the returned `verified` field and `readback` object. On a timeout or error, inspect actual remote state with `custom-values`; never assume no change occurred or retry automatically.
8. For agency rebilling math (`1.05x` Stripe processing-fee shield and 4-store sync payloads), V1/V2 user scope audits, or Custom SMTP (`Add Service`) unlocking, run `rebilling-audit`, `scope-audit`, or `smtp-audit` and read `wiki/agency-governance.md`.
9. Save a private receipt only when requested or part of an authorized workflow. Use `templates/change-receipt.md` or `templates/unnerf-audit-receipt.md` in the selected Empire project.

Read `wiki/authentication.md` for Private Integration scopes and V1/V2 user permission rules, `wiki/email-and-deliverability.md` for Custom SMTP and subdomain MX isolation, and `wiki/troubleshooting.md` for error recovery. Do not enable ambient HighLevel/LeadConnector MCP servers.

Do not install a standalone module skill. The central `cto-legends` skill loads this recipe on demand.
