# Security

Do not include Private Integration Tokens (`GHL_PIT`), OAuth credentials, sub-account customer PII, or raw API responses in public issues. Report suspected vulnerabilities privately through the repository's GitHub security reporting feature when available; otherwise contact the maintainer through a private channel.

Use narrowly scoped sub-account Private Integration Tokens. The CLI reads credentials only from the process environment, uses verified HTTPS against `https://services.leadconnectorhq.com`, refuses HTTP redirects, and performs no automatic retries on writes.

Live mutations require explicit confirmation of the active Location ID and preview SHA-256 hash (`--apply --confirm-location --confirm-plan`). This is an operator guard, not an access-control boundary or atomic transaction. HighLevel token scopes and sub-account isolation are the actual authorization boundary.

If a request times out after submission, the provider may have changed state. Inspect remote state before repeating the operation. No automatic rollback is performed.

Only the current release candidate is maintained during the 0.1 series. Reported compatibility and test coverage are in `docs/RELEASE-READINESS.md`.
