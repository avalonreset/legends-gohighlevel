# CRM, Workflows v3, Agent Studio AI, and Custom Objects operations

Use the CLI for deterministic, PII-lean inspection and preview-first changes against Official HighLevel API v2 and Workflows API v3 (`https://services.leadconnectorhq.com`). Do not enable ambient HighLevel/LeadConnector MCP servers that flood agent context with hundreds of unreviewed tools and raw personal data.

## 1. Sub-account health audit and read-only CRM, Funnels, Tags, and Custom Objects inspection

All read commands output structured JSON with an `observed_at` UTC timestamp and `rate_limits` metadata. Use `--profile <name>` to select a named profile from `~/.config/legends-gohighlevel/config.json`:

```sh
legends-gohighlevel subaccount-config
legends-gohighlevel subaccount-audit
legends-gohighlevel location
legends-gohighlevel pipelines
legends-gohighlevel opportunities --status open --limit 20
legends-gohighlevel calendars
legends-gohighlevel calendar-slots --calendar-id CALENDAR_ID --start-date 1793491200000 --end-date 1793664000000
legends-gohighlevel forms --limit 50
legends-gohighlevel surveys --limit 50
legends-gohighlevel funnels --include-redirects
legends-gohighlevel tags
legends-gohighlevel objects
legends-gohighlevel object-records --object-key custom_objects.vehicles --limit 20
legends-gohighlevel associations
legends-gohighlevel custom-values
legends-gohighlevel custom-fields
```

## 2. Agent Studio: Voice AI and Conversation AI inspection

Inspect Voice AI agents, PII-lean Voice AI call logs (omitting caller phone numbers and raw transcripts by default), and Conversation AI agents:

```sh
legends-gohighlevel voice-ai-agents
legends-gohighlevel voice-ai-calls --limit 20
legends-gohighlevel conversation-ai-agents
```

Note on `/conversation-ai/agents/search`: HighLevel's Conversation AI search endpoint infers the sub-account from the Private Integration Token (`GHL_PIT`) and rejects `?locationId=...` query parameters with `HTTP 422`. `legends-gohighlevel` handles this automatically.

## 3. Workflows API v2 and October 2026 Workflows API v3 (`Version: v3`)

List workflows via API v2 (`Version: 2021-07-28`) or inspect full workflow definitions, execution logs, and step types via HighLevel's October 2026 Workflows API v3 (`Version: v3`):

```sh
legends-gohighlevel workflows
legends-gohighlevel workflow-step-types
legends-gohighlevel workflow-inspect --workflow-id WORKFLOW_ID
legends-gohighlevel workflow-logs --workflow-id WORKFLOW_ID --limit 25
legends-gohighlevel workflow-validate --definition-json '{"name":"Welcome","steps":[]}'
```

If a sub-account does not yet have HighLevel's Workflows API v3 beta enabled, the CLI surfaces a clear diagnostic when HighLevel returns `HTTP 403 WORKFLOW_API_NOT_ENABLED_FOR_LOCATION`.

To preview and update a workflow's status (`published` or `draft`):

```sh
legends-gohighlevel workflow-status --workflow-id WORKFLOW_ID --status published
legends-gohighlevel workflow-status --workflow-id WORKFLOW_ID --status published \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW
```

## 4. PII-lean contact and conversation triage

By default, `contacts` and `conversations` omit personal names, email addresses, phone numbers, and message bodies so agents can inspect tags, counts, and activity without pulling unnecessary customer PII into context:

```sh
legends-gohighlevel contacts --limit 20
legends-gohighlevel contacts --query "vip" --limit 20
legends-gohighlevel conversations --limit 20
```

Pass `--full` on `contacts` only when the task explicitly requires contact names, emails, or phone numbers:

```sh
legends-gohighlevel contacts --query "person@example.com" --full
```

## 5. Preview-first custom-value mutations (`upsert` and `delete`)

Every write command runs in **preview mode** by default (`writes_sent: 0`). It reads current sub-account state, detects whether the operation is a `create`, `update`, or `delete`, and computes a canonical `sha256` plan hash:

```sh
legends-gohighlevel custom-value-upsert --name "Support Email" --value "help@example.com"
```

Review `before`, `proposed`, `action`, and `sha256` in the preview JSON. Only after human approval, execute the exact command with `--apply`, `--confirm-location`, and `--confirm-plan`:

```sh
legends-gohighlevel custom-value-upsert --name "Support Email" --value "help@example.com" \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW
```

To delete a single custom value, obtain its `id` from `custom-values`, preview with both `--name` and `--custom-value-id`, and apply with the preview hash:

```sh
legends-gohighlevel custom-value-delete --name "Support Email" --custom-value-id EXACT_ID
legends-gohighlevel custom-value-delete --name "Support Email" --custom-value-id EXACT_ID \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW
```

## 6. Preview-first tag, contact, and opportunity mutations

Use the same preview-first + `--apply --confirm-location --confirm-plan` contract for sub-account tags, contacts, contact notes, and opportunities:

```sh
legends-gohighlevel tag-upsert --name "vip-client"
legends-gohighlevel tag-delete --name "vip-client" --tag-id TAG_ID

legends-gohighlevel contact-upsert --email "jane@example.com" --first-name "Jane" --tags "vip-client"
legends-gohighlevel contact-tag --contact-id CONTACT_ID --tags "booked-call"
legends-gohighlevel contact-tag --contact-id CONTACT_ID --tags "cold-lead" --remove
legends-gohighlevel contact-note --contact-id CONTACT_ID --body "Completed discovery call."

legends-gohighlevel opportunity-update --opportunity-id OPP_ID --stage-id STAGE_ID --status won --monetary-value 2500
```
