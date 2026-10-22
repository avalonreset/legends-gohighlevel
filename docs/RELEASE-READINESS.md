# Release readiness

Release: `legends-gohighlevel` 0.1.0. Release date: 2026-10-22.

Status: `0.1.0` candidate verified across offline unit tests, clean-environment wheel/sdist installation, `legends-empire` `0.3.2` knowledge-pack attachment (preview, apply, repeat noop, and conflict refusal), live GoHighLevel API v2 8-lane read smoke, and live disposable custom-value create/update/readback/delete round-trip validation.

| Gate | State |
|---|---|
| Product rename (`legends-gohighlevel`) and portable Python package | Completed |
| Official-source knowledge vault, `legends.knowledge-pack/v1` pack, and Empire templates | Completed and verified through `legends-empire` `0.3.2` (preview, apply, repeat noop, and conflict refusal) |
| Attribution and MIT license | Completed |
| House banner and social image | Rendered and visually inspected |
| Offline behavior tests | Passed on Windows and POSIX |
| Clean wheel and source installation | Passed isolated wheel and source-distribution installs with offline doctor; archive contents checked |
| Router recipe and isolated catalog integration | Passed real manager installation/probes against a local archive fixture; intent routing, legacy `legends-gohighlevel-kit` compatibility, and handoff verified |
| Live API v2 read smoke | Passed 8-lane sub-account read verification (`location`, `contacts`, `pipelines`, `calendars`, `conversations`, `custom_values`, `workflows`, `forms`) with live rate-limit telemetry |
| Live API v2 write round trip | Passed authorized disposable custom-value creation, exact-ID update, API readback, and exact-ID deletion; final inventory confirmed zero test records |
| Linux/macOS/Windows hosted CI | Configured in `.github/workflows/checks.yml` across `ubuntu-latest`, `windows-latest`, and `macos-latest` (`3.10`, `3.13`) |

The wheel installs the CLI. The source distribution includes the knowledge vault (`wiki/` and `knowledge/gohighlevel/pack.json`), agent recipe, governance calculators, and presentation files. No private tokens, customer PII, or predecessor host paths are included.
