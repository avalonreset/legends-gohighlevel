# CRM operations

Use the CLI for deterministic, PII-lean inspection and preview-first changes against Official HighLevel API v2 (`https://services.leadconnectorhq.com`). Do not enable ambient HighLevel/LeadConnector MCP servers that flood agent context with hundreds of unreviewed tools and raw personal data.

## 1. Read-only sub-account inspection

All read commands output structured JSON with an `observed_at` UTC timestamp and `rate_limits` metadata:

```sh
legends-gohighlevel location
legends-gohighlevel pipelines
legends-gohighlevel opportunities --status open --limit 20
legends-gohighlevel calendars
legends-gohighlevel workflows
legends-gohighlevel forms --limit 50
legends-gohighlevel surveys --limit 50
legends-gohighlevel custom-values
legends-gohighlevel custom-fields
```

## 2. PII-lean contact and conversation triage

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

## 3. Preview-first custom-value mutations (`upsert` and `delete`)

Every write command runs in **preview mode** by default (`writes_sent: 0`). It reads current sub-account state, detects whether the operation is a `create`, `update`, or `delete`, and computes a canonical `sha256` plan hash:

```sh
legends-gohighlevel custom-value-upsert --name "Support Email" --value "help@example.com"
```

Review `before`, `proposed`, `action`, and `sha256` in the preview JSON. Only after human approval, execute the exact command with `--apply`, `--confirm-location`, and `--confirm-plan`:

```sh
legends-gohighlevel custom-value-upsert --name "Support Email" --value "help@example.com" \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW
```

During `--apply`:
1. The CLI rebuilds the plan from live sub-account state and refuses to proceed if the remote record changed since preview (`--confirm-plan` mismatch).
2. It sends a single write request (`POST` or `PUT`) with zero automatic retries.
3. It immediately queries `/locations/{locationId}/customValues` to verify that the created or updated value matches the requested payload (`verified: true`).

To delete a single custom value, obtain its `id` from `custom-values`, preview with both `--name` and `--custom-value-id`, and apply with the preview hash:

```sh
legends-gohighlevel custom-value-delete --name "Support Email" --custom-value-id EXACT_ID
legends-gohighlevel custom-value-delete --name "Support Email" --custom-value-id EXACT_ID \
  --apply --confirm-location YOUR_LOCATION_ID --confirm-plan SHA256_FROM_PREVIEW
```
