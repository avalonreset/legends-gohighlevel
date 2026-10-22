# Changelog

## 0.1.0 (2026-10-22)

- Initial public release of `legends-gohighlevel` (superseding the earlier private `legends-gohighlevel-kit`).
- Pure Python 3.10+ standard-library CLI (`legends-gohighlevel`) with zero external runtime dependencies.
- Sub-account Official HighLevel API v2 inspection across locations, custom values, custom fields, pipelines, opportunities, calendars, workflows, forms, surveys, and PII-lean contacts and conversations.
- Preview-first custom-value mutations (`custom-value-upsert`, `custom-value-delete`) with SHA-256 plan confirmation (`--apply --confirm-location --confirm-plan`) and post-write API readback verification.
- Deterministic agency governance calculators and payload builders (`rebilling-audit`, `scope-audit`, `smtp-audit`) covering the `1.05x` (`db_markup=5`) Stripe fee shield, 4-store rebilling synchronization, V1/V2 user permission rules, worker scope inheritance, and two-level Custom SMTP unlocking.
- Attachable `legends.knowledge-pack/v1` knowledge vault (`knowledge/gohighlevel/pack.json`) and Empire templates.
