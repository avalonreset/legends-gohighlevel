# Troubleshooting

## 1. `HighLevel HTTP 401` or `HTTP 403` during `doctor --live`

- **Cause:**
  - `HTTP 401`: `GHL_PIT` (or `GHL_ACCESS_TOKEN`) is expired, revoked, or malformed.
  - `HTTP 403`: A Private Integration Token (`pit-...`) is strictly bound to the sub-account where it was issued. If `GHL_LOCATION_ID` points to a different sub-account, HighLevel returns `HTTP 403 ("Forbidden resource")`. It can also indicate a missing `.readonly` or `.write` scope on the token.
- **Fix:** Confirm `GHL_LOCATION_ID` matches the sub-account that issued `GHL_PIT`, then run `legends-gohighlevel doctor --live` and inspect the per-lane `scope_hint` results.

## 2. Greyed-out `Add Service` button under **Settings > Email Services**

- **Cause:** HighLevel enforces two separate `blockAddSmtp` locks: an agency-level default (`emailIsvSettings.blockAddSmtp`) and a per-location flag (`blockAddSmtp`) stamped onto the sub-account at creation time. Unchecking only the agency checkbox leaves existing sub-accounts locked.
- **Fix:** Run `legends-gohighlevel smtp-audit --company-id COMPANY_ID --location-id LOCATION_ID` and set `blockAddSmtp: false` on both the agency and location endpoints, then verify `GET /email-isv/onload?locationId=LOCATION_ID` returns `"blockAddSmtp": false`.

## 3. Sub-account admin missing Forms, Surveys, Pipelines, or Private Integrations

- **Cause:** Even when V1 `permissions` flags (`funnelsEnabled: true`, `PrivateIntegrationLocationEnabled: true`) are enabled, missing V2 `scopes` (`forms.write`, `surveys.write`, `pipelines.create`, `private-integration-location.readonly`) hide or block those screens. When an Agency Admin worker creates a new sub-account user in the browser, HighLevel's `usersApp` frontend silently strips any V2 scope not held by the creator.
- **Fix:** Run `legends-gohighlevel scope-audit --role admin --account-type account`, ensure the Agency Admin worker holds all 243 V2 scopes, and update the sub-account admin via `PUT /users/{userId}` with `source: "agency_team"`.

## 4. `HTTP 422` when updating a user via `PUT /users/{userId}`

- **Cause:**
  1. `source` was omitted or set to an invalid value (must be `"agency_team"` or `"location_team"`).
  2. `scopes` included expanded `scopesMap` child strings (such as `quizzes.write`) instead of top-level keys from `GET /users/permissions`.
  3. Both sides of a mutually exclusive V2 scope pair (`workflows.readonly` + `workflows.write`, or `campaigns.readonly` + `campaigns.write`) were included.
- **Fix:** Use the sanitized `recommended_v2_scopes` and `required_update_source` output from `legends-gohighlevel scope-audit`.

## 5. `Insufficient funds to send email` despite positive sub-account wallet balance

- **Cause:** On rebilled LC Email, HighLevel debits the parent agency wallet first and then recharges from the sub-account wallet, or the sub-account is still routing through LC Email instead of its connected Custom SMTP provider.
- **Fix:** Either verify the upstream agency wallet payment method is active, or switch the sub-account's connected Custom SMTP provider (`Brevo`, `SendGrid`, `Mailgun`, `Amazon SES`) to **Active** under **Settings > Email Services > SMTP & Mailgun Services** so outbound email bypasses LC Email billing entirely.

## 6. Write timeout or `--confirm-plan` mismatch

- **Cause:** If a network timeout occurs during `--apply`, the remote HighLevel state may already have changed. If another operator edited the custom value between preview and apply, the rebuilt plan hash will differ from `--confirm-plan`.
- **Fix:** Never retry a write blindly. Run `legends-gohighlevel custom-values` to inspect current state, generate a fresh preview, and confirm the new hash before applying.
