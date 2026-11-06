# Agent instructions

Read `docs/AGENT-RECIPE.md`, then `wiki/index.md` and the smallest matching runbook.
Run offline doctor before commands and live doctor before authorized API operations.

- This module is `legends-gohighlevel`. The earlier private `legends-gohighlevel-kit` is a separate compatibility surface.
- Read before mutating sub-account state. Require a reviewed preview plan and the owner's explicit authorization for its Location ID and plan hash.
- Keep Private Integration Tokens (`GHL_PIT`), OAuth credentials, private sub-account inventories, and receipts outside this repository and managed installations.
- **Windows Defender, EDR, and Anti-Ransomware Guardrails:**
  - Never spawn background shells, hidden console windows, execution-policy bypass flags, or encoded PowerShell commands.
  - Never read or scan local desktop browser profile directories (`AppData\Local\Google\Chrome`, `Edge`, `Brave`, `IndexedDB`, `Cookies`, `Login Data`, or `.ldb`/`.log` files) or DPAPI/credential stores to obtain `GHL_TOKEN_ID` or session tokens. Use `GHL_PIT` / `GHL_ACCESS_TOKEN` for sub-account API v2, and `GHL_TOKEN_ID` or remote `worker_ssh` in `~/.config/legends-gohighlevel/agency.json` for agency backend operations.
  - Never print raw secret values (`GHL_PIT`, `GHL_ACCESS_TOKEN`, `GHL_TOKEN_ID`, OAuth tokens) to stdout, logs, or receipts.
- Default to PII-lean contact and conversation inspection; pass `--full` only when the task genuinely requires customer contact details.
- Never enable or fall back to ambient HighLevel/LeadConnector MCP servers.
- Preserve the one-skill router. Module recipes are Markdown, not new host skill registrations.
- Use current official GoHighLevel API v2 sources and date evidence when changing guidance.
- Run offline tests, release checks, and clean installation before release.
