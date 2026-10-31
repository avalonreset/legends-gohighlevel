# GoHighLevel operating knowledge

Use this vault with the CLI or as a plain Markdown reference. Read the dated [source ledger](sources.md); provider behavior can change.

| Task | Runbook | Evidence to keep privately |
|---|---|---|
| Audit live agency sub-accounts, 5-layer governance, `+hubpro` aliases, Default Dashboard RBAC, and rebilling | [Internal Backend API and Dashboards](internal-backend-and-dashboards.md) | `live-audit` summary, `dashboard-permissions` readback, `rebilling-status` readback, and user location sync receipt |
| Connect a scoped token and audit V1/V2 user scopes | [Authentication and Scopes](authentication.md) | Scope and verification result (`doctor --live` or `user-inspect`), never token value |
| Inspect CRM, Workflows v3, Agent Studio AI, or Custom Objects, or apply a previewed change | [CRM Operations](crm-operations.md) | Preview JSON, SHA-256 hash, approval, and post-write readback |
| Configure safe rebilling (`1.05x`), unlock Custom SMTP, or un-nerf sub-accounts | [Agency Governance and Rebilling](agency-governance.md) | Rebilling audit output, 4-store + 14-product readback, user scope audit, and dashboard RBAC audit |
| Configure Custom SMTP (`Brevo` / BYO) or isolate inbound MX subdomains | [Email and Deliverability](email-and-deliverability.md) | DNS records, `email-domains` output, SMTP active status, and root MX preservation check |
| Diagnose API, dashboard permission, scope, or billing failures | [Troubleshooting](troubleshooting.md) | Sanitized error, `live-audit` findings, rate-limit headers, and observed remote state |
| Keep operating history | [Empire integration](https://github.com/avalonreset/legends-gohighlevel/blob/main/docs/EMPIRE.md) | Canonical project links and private receipts |

This is a focused operational knowledge base for sub-account CRM/AI/Workflows execution, live internal backend governance, and 5-layer permission and rebilling auditing, not a mirror of the entire HighLevel help center. Review guidance after an incident or provider change.
