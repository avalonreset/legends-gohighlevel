# Fit the module into legends-empire

The public knowledge vault is reusable operational guidance. Your private Empire holds actual workspaces, Location IDs, client records, decisions, evidence, and follow-up tasks.

1. Select your existing CRM or agency operations project. Respect its canonical path and any migration sidecar; do not create a competing task ledger.
2. Attach the versioned knowledge library (`knowledge/gohighlevel/pack.json`, schema `legends.knowledge-pack/v1`) through `legends-empire` (`knowledge attach`) or link directly to `wiki/index.md`. Attachment previews first, writes into `wiki/library/legends-gohighlevel/gohighlevel`, and refuses to overwrite locally edited reference files.
3. Copy a template into the selected private project only when requested. Record the real observation date and link evidence stored outside managed installations.
4. Keep source observations, interpretation, decisions, and outstanding verification separate. Never store Private Integration Tokens (`GHL_PIT`), OAuth tokens, or raw customer PII dumps inside knowledge notes.
5. Link one authoritative sub-account inventory from related projects.

Templates:

- [Sub-account inventory](../templates/subaccount-inventory.md)
- [CRM change receipt](../templates/change-receipt.md)
- [Agency un-nerf audit receipt](../templates/unnerf-audit-receipt.md)

Attach the knowledge pack with `legends-empire`:

```sh
legends-empire knowledge attach \
  --vault <VAULT_ROOT> \
  --operation-id attach-legends-gohighlevel-0.3.4 \
  --generated-at 2026-11-06T22:00:00Z \
  knowledge/gohighlevel/pack.json

legends-empire knowledge attach \
  --vault <VAULT_ROOT> \
  --operation-id attach-legends-gohighlevel-0.3.4 \
  --generated-at 2026-11-06T22:00:00Z \
  --approved-plan-sha256 <SHA256> \
  --apply \
  knowledge/gohighlevel/pack.json
```

Plain Markdown works without Obsidian plugins or a Home installation. No automatic vault writes or paid integration is required.
