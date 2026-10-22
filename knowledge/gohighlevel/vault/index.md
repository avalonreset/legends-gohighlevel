# GoHighLevel operating knowledge

Use this vault with the CLI or as a plain Markdown reference. Read the dated [source ledger](sources.md); provider behavior can change.

| Task | Runbook | Evidence to keep privately |
|---|---|---|
| Connect a scoped token and audit V1/V2 user scopes | [Authentication and Scopes](authentication.md) | Scope and verification result (`doctor --live`), never token value |
| Inspect CRM state or apply a previewed change | [CRM Operations](crm-operations.md) | Preview JSON, SHA-256 hash, approval, and post-write readback |
| Configure safe rebilling (`1.05x`), unlock Custom SMTP, or un-nerf sub-accounts | [Agency Governance and Rebilling](agency-governance.md) | Rebilling audit output, 4-store readback, and user scope audit |
| Configure Custom SMTP (`Brevo` / BYO) or isolate inbound MX subdomains | [Email and Deliverability](email-and-deliverability.md) | DNS records, SMTP active status, and root MX preservation check |
| Diagnose API, scope, or billing failures | [Troubleshooting](troubleshooting.md) | Sanitized error, rate-limit headers, and observed remote state |
| Capture change and audit records | [Change receipt](templates/change-receipt.md), [Sub-account inventory](templates/subaccount-inventory.md), [Un-nerf audit receipt](templates/unnerf-audit-receipt.md) | Canonical project links and private receipts |

This is a focused operational knowledge base for sub-account CRM execution and agency governance, not a mirror of the entire HighLevel help center. Review guidance after an incident or provider change.
