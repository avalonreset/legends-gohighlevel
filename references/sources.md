# Source ledger

Reviewed 2026-10-31 against official GoHighLevel (HighLevel / LeadConnector) documentation, the October 2026 Developer Wave / LevelUp 2026 Summit releases, and live API v2, API v3, and internal backend verification. These links support provider behavior; module-specific guarantees are supported by implementation and tests.

| Source | Claims covered | Used by |
|---|---|---|
| [HighLevel API v2 Portal](https://marketplace.gohighlevel.com/docs/) | Base URL `https://services.leadconnectorhq.com`, `Version: 2021-07-28` header, resource schemas | API client, CRM operations |
| [Authorization: PIT vs OAuth 2.0](https://marketplace.gohighlevel.com/docs/Authorization/authorization_doc/) | Distinction between sub-account Private Integration Tokens and multi-tenant OAuth 2.0 apps | Authentication |
| [Private Integration Tokens](https://marketplace.gohighlevel.com/docs/Authorization/PrivateIntegrationsToken/index.html) | Static bearer token model (`pit-` prefix), sub-account scoping, 90-day rotation guidance | Authentication, Security |
| [API v2 Scopes and Endpoint Map](https://marketplace.gohighlevel.com/docs/Authorization/Scopes/index.html) | Least-privilege `.readonly` and `.write` scopes per CRM, AI, and Custom Objects domain | Authentication, CRM operations |
| [OAuth FAQ and API v2 Rate Limits](https://marketplace.gohighlevel.com/docs/oauth/Faqs/index.html) | Burst limit (100 requests per 10 seconds), daily limit (200,000 requests per day), `X-RateLimit-*` headers | API client, Troubleshooting |
| [Contacts API](https://marketplace.gohighlevel.com/docs/ghl/contacts/contacts/) | Contact listing, search, upsert, tags, and notes endpoints | CRM operations |
| [Opportunities and Pipelines API](https://marketplace.gohighlevel.com/docs/ghl/opportunities/search-opportunities-advanced/index.html) | Pipeline stage discovery and opportunity search | CRM operations |
| [Calendars API](https://marketplace.gohighlevel.com/docs/ghl/calendars/calendars/) | Sub-account calendar inventory and free-slot queries | CRM operations |
| [Locations and Custom Values API](https://marketplace.gohighlevel.com/docs/ghl/locations/custom-values/) | Sub-account metadata, tags, custom fields, and custom values CRUD | CRM operations |
| [Custom Objects and Associations API](https://marketplace.gohighlevel.com/docs/ghl/objects/objects-api/) | Sub-account custom object schemas (`/objects/`), record search (`/objects/{key}/records/search`), and associations (`/associations/`) | CRM operations |
| [Voice AI and Conversation AI API](https://marketplace.gohighlevel.com/docs/ghl/voice-ai/voice-ai-api/) | Voice AI agents (`/voice-ai/agents`), call logs (`/voice-ai/dashboard/call-logs`), and Conversation AI agents (`/conversation-ai/agents/search`) | CRM operations |
| [Funnels and Redirects API](https://marketplace.gohighlevel.com/docs/ghl/funnels/funnels-api/) | Funnel inventory (`/funnels/funnel/list`) and URL redirect lookup (`/funnels/lookup/redirect/list`) | CRM operations |
| [Workflows API v2 and v3](https://marketplace.gohighlevel.com/docs/ghl/workflows/get-workflow/) | Workflows v2 list (`/workflows/`) and October 2026 Workflows API v3 (`Version: v3` header for `/workflows/step-types`, `/workflows/{id}/definition`, `/workflows/{id}/logs`, `/workflows/definition/validate`, and `/workflows/{id}/status`) | CRM operations |
| [LeadConnector Official MCP Overview](https://marketplace.gohighlevel.com/docs/other/mcp/index.html) | Scope of official MCP server versus deterministic CLI execution | CRM operations, Architecture |

No external documentation corpus is bundled. Summaries are original and links retain upstream attribution. Dates are review dates, not a promise that upstream pages will remain unchanged.
