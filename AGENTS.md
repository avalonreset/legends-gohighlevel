# Agent instructions

Read `docs/AGENT-RECIPE.md`, then `wiki/index.md` and the smallest matching runbook.
Run offline doctor before commands and live doctor before authorized API operations.

- This module is `legends-gohighlevel`. The earlier private `legends-gohighlevel-kit` is a separate compatibility surface.
- Read before mutating sub-account state. Require a reviewed preview plan and the owner's explicit authorization for its Location ID and plan hash.
- Keep Private Integration Tokens (`GHL_PIT`), OAuth credentials, private sub-account inventories, and receipts outside this repository and managed installations.
- Default to PII-lean contact and conversation inspection; pass `--full` only when the task genuinely requires customer contact details.
- Never enable or fall back to ambient HighLevel/LeadConnector MCP servers.
- Preserve the one-skill router. Module recipes are Markdown, not new host skill registrations.
- Use current official GoHighLevel API v2 sources and date evidence when changing guidance.
- Run offline tests, release checks, and clean installation before release.
