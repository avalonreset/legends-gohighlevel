# Release readiness

Release: `legends-gohighlevel` 0.3.0. Release date: 2026-10-31.

Status: `0.3.0` verified across offline unit tests (`tests/test_gohighlevel.py` and `tests/test_social_x_bridge.py`), clean-environment wheel/sdist installation, `legends-empire` `0.3.2` knowledge-pack attachment (preview, apply, repeat noop, and conflict refusal), live GoHighLevel API v2 and v3 sub-account read/write verification (`subaccount-audit`, disposable `tag`, `contact`, `note`, and `custom-value` round trips), and live 5-layer agency audit and remediation across all 23 sub-accounts and 16 users (`ok: true`, `issue_count: 0`).

| Gate | State |
|---|---|
| Product rename (`legends-gohighlevel`) and portable Python 3.11+ package | Completed (`0.3.0`) |
| Official-source knowledge vault, `legends.knowledge-pack/v1` pack, and Empire templates | Completed and verified through `legends-empire` `0.3.2` (preview, apply, repeat noop, and conflict refusal) |
| Attribution and MIT license | Completed |
| House banner and social image | Rendered and visually inspected |
| Offline behavior tests | Passed 16 unit tests on Windows and POSIX (`test_gohighlevel.py` and `test_social_x_bridge.py`) |
| Clean wheel and source installation | Passed isolated wheel and source-distribution installs with offline doctor; archive contents checked |
| Router recipe and isolated catalog integration | Passed real manager installation/probes against a local archive fixture; intent routing, legacy `legends-gohighlevel-kit` compatibility, and handoff verified |
| Live API v2 & v3 read and disposable write canaries | Passed `subaccount-audit` across 2 live sub-accounts, 20-lane API v2/v3 read smoke, and disposable `custom-value`, `tag`, and `contact` create/update/readback/cleanup round trips |
| Live 5-layer agency backend governance | Passed 5-layer `live-audit` (`location-unnerf`, `user-unnerf`, `user-sync-locations`, `unlock-dashboards`, `smtp-unlock`, `rebilling-sync`) with `issue_count: 0` |
| Linux/macOS/Windows hosted CI | Configured in `.github/workflows/checks.yml` across `ubuntu-latest`, `windows-latest`, and `macos-latest` (`3.11`, `3.13`) |

The wheel installs the CLI. The source distribution includes the knowledge vault (`wiki/` and `knowledge/gohighlevel/pack.json`), agent recipe, governance calculators, and presentation files. No private tokens, customer PII, or predecessor host paths are included.
