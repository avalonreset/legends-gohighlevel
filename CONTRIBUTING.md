# Contributing

Read AGENTS.md and the source ledger. Keep one registered router skill, private evidence outside the repository, and domain claims tied to official sources.

Run `python -m unittest discover -s tests -v` and `python scripts/check_release.py`.
Add behavioral tests for transport, rate-limit header parsing, preview/confirmation guards, governance calculators, and readback failures. Tests must use synthetic records and no network credentials.

Do not broaden executable scope by adding an unrestricted raw write escape hatch or ambient MCP dependency.

Use plain language. Keep existing attribution and the approved typography style.
