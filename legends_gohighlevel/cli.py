"""JSON CLI with offline doctor, sub-account CRM operations, live agency backend control, preview-first mutations, and governance audits."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from . import __version__
from .agency import (
    apply_location_rename_plan,
    apply_location_unnerf_plan,
    apply_rebilling_sync_plan,
    apply_smtp_unlock_plan,
    apply_unlock_dashboards_plan,
    apply_user_sync_locations_plan,
    apply_user_unnerf_plan,
    inspect_dashboard_permissions,
    inspect_email_domains,
    inspect_rebilling_status,
    inspect_smtp_status,
    inspect_user,
    list_agency_locations,
    list_agency_users,
    list_private_integrations,
    live_agency_audit,
    make_location_rename_plan,
    make_location_unnerf_plan,
    make_rebilling_sync_plan,
    make_smtp_unlock_plan,
    make_unlock_dashboards_plan,
    make_user_sync_locations_plan,
    make_user_unnerf_plan,
)
from .api import BackendClient, Client, HighLevelError, load_agency_config, load_subaccount_config
from .crm import (
    apply_contact_note_plan,
    apply_contact_tag_plan,
    apply_contact_upsert_plan,
    apply_custom_value_plan,
    apply_opportunity_update_plan,
    apply_tag_plan,
    apply_workflow_status_plan,
    inspect_workflow_definition,
    list_associations,
    list_calendar_free_slots,
    list_calendars,
    list_conversation_ai_agents,
    list_custom_fields,
    list_custom_values,
    list_forms,
    list_funnels,
    list_objects,
    list_pipelines,
    list_surveys,
    list_tags,
    list_voice_ai_agents,
    list_voice_ai_calls,
    list_workflow_logs,
    list_workflow_step_types,
    list_workflows,
    location_snapshot,
    make_contact_note_plan,
    make_contact_tag_plan,
    make_contact_upsert_plan,
    make_custom_value_plan,
    make_opportunity_update_plan,
    make_tag_plan,
    make_workflow_status_plan,
    probe_live_lanes,
    search_contacts,
    search_object_records,
    search_opportunities,
    subaccount_audit,
    triage_conversations,
    validate_workflow_definition,
)
from .governance import dashboard_permission_audit, rebilling_audit, scope_audit, smtp_audit
from .social import (
    DEFAULT_CUTOFF_ISO,
    GhlXBridge,
    XOfficialClient,
    list_social_accounts,
    list_social_posts,
)


def _repo_root(anchor: Path | None = None) -> Path:
    here = (anchor or Path(__file__)).resolve().parent
    data_dir = here / "_data"
    if (data_dir / "docs" / "AGENT-RECIPE.md").is_file() and (data_dir / "knowledge" / "gohighlevel" / "pack.json").is_file():
        return data_dir
    return here.parent


def resolve_resources(anchor: Path | None = None) -> dict:
    here = (anchor or Path(__file__)).resolve().parent
    root = _repo_root(anchor=anchor)
    source = "package_data" if root == (here / "_data").resolve() else "checkout"
    candidates = {
        "agent_recipe": root / "docs" / "AGENT-RECIPE.md",
        "wiki_index": root / "wiki" / "index.md",
        "knowledge_pack": root / "knowledge" / "gohighlevel" / "pack.json",
        "sources": root / "references" / "sources.md",
    }
    complete = all(v.is_file() for v in candidates.values())
    return {
        "ok": complete,
        "module": "legends-gohighlevel",
        "version": __version__,
        "source": source,
        "root": str(root),
        "recipe": str(candidates["agent_recipe"]),
        "pack_manifest": str(candidates["knowledge_pack"]),
        "complete": complete,
        "paths": {k: str(v) for k, v in candidates.items() if v.exists()},
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--profile", help="Named sub-account profile from ~/.config/legends-gohighlevel/config.json.")
    sub = p.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Offline runtime check; --live probes sub-account API v2 lanes.")
    doctor.add_argument("--live", action="store_true")

    sub.add_parser("resources", help="Show local recipe, wiki, and knowledge-pack paths.")
    sub.add_parser("subaccount-config", help="Show resolved sub-account credentials (masked) and named profiles.")
    sub.add_parser("subaccount-audit", help="Run a comprehensive sub-account health, profile, workflow, and custom-value audit.")
    sub.add_parser("agency-config", help="Show resolved agency configuration and worker SSH settings.")
    sub.add_parser("location", help="Get sub-account metadata for GHL_LOCATION_ID.")
    sub.add_parser("custom-values", help="List sub-account custom values.")
    sub.add_parser("custom-fields", help="List sub-account custom fields.")
    sub.add_parser("pipelines", help="List sub-account pipelines and stages.")
    sub.add_parser("calendars", help="List sub-account calendars.")

    cal_slots = sub.add_parser("calendar-slots", help="Query available appointment slots on a sub-account calendar.")
    cal_slots.add_argument("--calendar-id", required=True)
    cal_slots.add_argument("--start-date", required=True, help="Start epoch ms or YYYY-MM-DD.")
    cal_slots.add_argument("--end-date", required=True, help="End epoch ms or YYYY-MM-DD.")
    cal_slots.add_argument("--timezone", help="Optional IANA timezone (e.g. America/New_York).")

    sub.add_parser("workflows", help="List sub-account workflows.")

    forms = sub.add_parser("forms", help="List sub-account forms.")
    forms.add_argument("--limit", type=int, default=50)

    surveys = sub.add_parser("surveys", help="List sub-account surveys.")
    surveys.add_argument("--limit", type=int, default=50)

    sub.add_parser("tags", help="List sub-account tags.")

    funnels = sub.add_parser("funnels", help="List sub-account funnels and optional URL redirects.")
    funnels.add_argument("--limit", type=int, default=50)
    funnels.add_argument("--include-redirects", action="store_true")

    sub.add_parser("objects", help="List standard and custom CRM object schemas.")

    obj_rec = sub.add_parser("object-records", help="Search records for a custom or standard object schema.")
    obj_rec.add_argument("--object-key", required=True, help="Object key (e.g. business or custom_objects.vehicles).")
    obj_rec.add_argument("--query", default="")
    obj_rec.add_argument("--page", type=int, default=1)
    obj_rec.add_argument("--limit", type=int, default=20)

    sub.add_parser("associations", help="List CRM object associations.")
    sub.add_parser("voice-ai-agents", help="List Voice AI agents for GHL_LOCATION_ID.")

    voice_calls = sub.add_parser("voice-ai-calls", help="List Voice AI call logs (PII-lean metadata).")
    voice_calls.add_argument("--limit", type=int, default=20)

    sub.add_parser("conversation-ai-agents", help="List Conversation AI agents for GHL_LOCATION_ID.")
    sub.add_parser("workflow-step-types", help="List Workflows API v3 step types (requires v3 beta on location).")

    wf_insp = sub.add_parser("workflow-inspect", help="Inspect a workflow definition via Workflows API v3.")
    wf_insp.add_argument("--workflow-id", required=True)

    wf_logs = sub.add_parser("workflow-logs", help="List workflow execution logs via Workflows API v3.")
    wf_logs.add_argument("--workflow-id", required=True)
    wf_logs.add_argument("--limit", type=int, default=25)

    wf_val = sub.add_parser("workflow-validate", help="Validate a workflow definition JSON payload via Workflows API v3.")
    wf_val.add_argument("--definition-json", required=True)

    wf_stat = sub.add_parser("workflow-status", help="Preview or apply a workflow status change (published/draft) via Workflows API v3.")
    wf_stat.add_argument("--workflow-id", required=True)
    wf_stat.add_argument("--status", choices=["published", "draft"], required=True)
    wf_stat.add_argument("--apply", action="store_true")
    wf_stat.add_argument("--confirm-location")
    wf_stat.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    contacts = sub.add_parser("contacts", help="List or search contacts (PII-lean by default; --full includes contact fields).")
    contacts.add_argument("--query")
    contacts.add_argument("--limit", type=int, default=20)
    contacts.add_argument("--full", action="store_true")

    opps = sub.add_parser("opportunities", help="Search sub-account opportunities.")
    opps.add_argument("--pipeline-id")
    opps.add_argument("--stage-id")
    opps.add_argument("--status", choices=["open", "won", "lost", "abandoned", "all"])
    opps.add_argument("--limit", type=int, default=20)

    convs = sub.add_parser("conversations", help="Triage recent conversations (PII-lean metadata).")
    convs.add_argument("--limit", type=int, default=20)

    for cmd in ("custom-value-upsert", "custom-value-delete"):
        op = sub.add_parser(cmd, help="Preview a custom-value change; explicit confirmation required to apply.")
        op.add_argument("--name", required=True)
        if cmd == "custom-value-upsert":
            op.add_argument("--value", required=True)
            op.add_argument("--custom-value-id")
        else:
            op.add_argument("--custom-value-id", required=True)
        op.add_argument("--apply", action="store_true")
        op.add_argument("--confirm-location")
        op.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    for tcmd in ("tag-upsert", "tag-delete"):
        tp = sub.add_parser(tcmd, help="Preview or apply a sub-account tag creation or deletion.")
        tp.add_argument("--name", required=True)
        if tcmd == "tag-delete":
            tp.add_argument("--tag-id", required=True)
        tp.add_argument("--apply", action="store_true")
        tp.add_argument("--confirm-location")
        tp.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    c_up = sub.add_parser("contact-upsert", help="Preview or apply a sub-account contact upsert with API readback.")
    c_up.add_argument("--email")
    c_up.add_argument("--phone")
    c_up.add_argument("--first-name")
    c_up.add_argument("--last-name")
    c_up.add_argument("--name")
    c_up.add_argument("--tags", help="Comma-separated list of tags.")
    c_up.add_argument("--apply", action="store_true")
    c_up.add_argument("--confirm-location")
    c_up.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    c_tag = sub.add_parser("contact-tag", help="Preview or apply adding or removing tags on a contact.")
    c_tag.add_argument("--contact-id", required=True)
    c_tag.add_argument("--tags", required=True, help="Comma-separated list of tags.")
    c_tag.add_argument("--remove", action="store_true", help="Remove the specified tags instead of adding them.")
    c_tag.add_argument("--apply", action="store_true")
    c_tag.add_argument("--confirm-location")
    c_tag.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    c_note = sub.add_parser("contact-note", help="Preview or apply adding a note on a contact.")
    c_note.add_argument("--contact-id", required=True)
    c_note.add_argument("--body", required=True)
    c_note.add_argument("--apply", action="store_true")
    c_note.add_argument("--confirm-location")
    c_note.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    o_up = sub.add_parser("opportunity-update", help="Preview or apply updating an opportunity stage, status, value, or title.")
    o_up.add_argument("--opportunity-id", required=True)
    o_up.add_argument("--stage-id")
    o_up.add_argument("--status", choices=["open", "won", "lost", "abandoned"])
    o_up.add_argument("--monetary-value", type=float)
    o_up.add_argument("--title")
    o_up.add_argument("--apply", action="store_true")
    o_up.add_argument("--confirm-location")
    o_up.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    rebill = sub.add_parser("rebilling-audit", help="Calculate HighLevel rebilling multiplier, Stripe fee shield, and 4-store sync payloads.")
    rebill.add_argument("--wallet-topup", type=float, default=10.0)
    rebill.add_argument("--markup", type=int, default=5)
    rebill.add_argument("--location-id")

    scopes = sub.add_parser("scope-audit", help="Audit HighLevel V1 permissions, V2 scopes, mutual exclusions, and worker inheritance.")
    scopes.add_argument("--role", choices=["admin", "user"], default="admin")
    scopes.add_argument("--account-type", choices=["account", "agency"], default="account")
    scopes.add_argument("--current-scopes-json", help="JSON array of current V2 scopes on the user.")
    scopes.add_argument("--creator-scopes-json", help="JSON array of V2 scopes held by the Agency Admin creator.")

    smtp = sub.add_parser("smtp-audit", help="Generate two-level Custom SMTP (Add Service) unlock and verification payloads.")
    smtp.add_argument("--company-id")
    smtp.add_argument("--location-id")

    dash_audit = sub.add_parser("dashboard-audit", help="Generate Default Dashboard per-role RBAC unlock and verification payloads.")
    dash_audit.add_argument("--location-id")
    dash_audit.add_argument("--dashboard-id")
    dash_audit.add_argument("--current-permissions-json", help="JSON array of current {role, permission} objects.")

    ag_locs = sub.add_parser("agency-locations", help="List all sub-accounts in the agency or inspect one location via backend.leadconnectorhq.com.")
    ag_locs.add_argument("--company-id")
    ag_locs.add_argument("--location-id")

    loc_ren = sub.add_parser("location-rename", help="Preview or apply a sub-account name update via PUT /locations/:id.")
    loc_ren.add_argument("--location-id", required=True)
    loc_ren.add_argument("--name", required=True)
    loc_ren.add_argument("--company-id")
    loc_ren.add_argument("--apply", action="store_true")
    loc_ren.add_argument("--confirm-location")
    loc_ren.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    loc_un = sub.add_parser("location-unnerf", help="Preview or apply all 40 location feature flags across one or all locations.")
    loc_un.add_argument("--location-id")
    loc_un.add_argument("--all-locations", action="store_true")
    loc_un.add_argument("--company-id")
    loc_un.add_argument("--apply", action="store_true")
    loc_un.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    ag_users = sub.add_parser("agency-users", help="List all agency and sub-account users and check +hubpro alias location sync.")
    ag_users.add_argument("--company-id")

    u_inspect = sub.add_parser("user-inspect", help="Deep-inspect a user's V1 permissions, V2 scopes, catalog items, and Only Assigned Data flags.")
    u_inspect.add_argument("--user-id")
    u_inspect.add_argument("--email")
    u_inspect.add_argument("--company-id")

    u_sync = sub.add_parser("user-sync-locations", help="Preview or apply locationIds synchronization for a user via PUT /users/:id.")
    u_sync.add_argument("--user-id", required=True)
    u_sync.add_argument("--location-ids", help="Comma-separated list of locationIds to assign.")
    u_sync.add_argument("--from-user-id", help="Copy locationIds from another user record (e.g. +hubpro alias).")
    u_sync.add_argument("--company-id")
    u_sync.add_argument("--apply", action="store_true")
    u_sync.add_argument("--confirm-user")
    u_sync.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    u_unnerf = sub.add_parser("user-unnerf", help="Preview or apply full V1 permissions and V2 scopes on a user via PUT /users/:id.")
    u_unnerf.add_argument("--user-id")
    u_unnerf.add_argument("--email")
    u_unnerf.add_argument("--company-id")
    u_unnerf.add_argument("--apply", action="store_true")
    u_unnerf.add_argument("--confirm-user")
    u_unnerf.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    smtp_stat = sub.add_parser("smtp-status", help="Inspect live Custom SMTP (Add Service / blockAddSmtp) status on one or all locations.")
    smtp_stat.add_argument("--location-id")
    smtp_stat.add_argument("--all-locations", action="store_true")
    smtp_stat.add_argument("--company-id")

    smtp_unl = sub.add_parser("smtp-unlock", help="Preview or apply two-level Custom SMTP (Add Service) unlocking across one or all locations.")
    smtp_unl.add_argument("--location-id")
    smtp_unl.add_argument("--all-locations", action="store_true")
    smtp_unl.add_argument("--company-id")
    smtp_unl.add_argument("--apply", action="store_true")
    smtp_unl.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    dash_perms = sub.add_parser("dashboard-permissions", help="Inspect per-role RBAC across all dashboards on one location or all agency locations.")
    dash_perms.add_argument("--location-id")
    dash_perms.add_argument("--all-locations", action="store_true")
    dash_perms.add_argument("--company-id")

    unlock_dash = sub.add_parser("unlock-dashboards", help="Preview or apply full dashboard RBAC (account_admin: full, account_user: full) on all dashboards in one or all locations.")
    unlock_dash.add_argument("--location-id")
    unlock_dash.add_argument("--all-locations", action="store_true")
    unlock_dash.add_argument("--company-id")
    unlock_dash.add_argument("--apply", action="store_true")
    unlock_dash.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    reb_stat = sub.add_parser("rebilling-status", help="Inspect live 4-store rebilling and 14-product SaaS Billing v2 config across one or all locations.")
    reb_stat.add_argument("--location-id")
    reb_stat.add_argument("--all-locations", action="store_true")
    reb_stat.add_argument("--company-id")
    reb_stat.add_argument("--markup", type=int, default=5)

    reb_sync = sub.add_parser("rebilling-sync", help="Preview or apply live 4-store rebilling synchronization across one or all locations.")
    reb_sync.add_argument("--location-id")
    reb_sync.add_argument("--all-locations", action="store_true")
    reb_sync.add_argument("--company-id")
    reb_sync.add_argument("--markup", type=int, default=5)
    reb_sync.add_argument("--apply", action="store_true")
    reb_sync.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    pit_ls = sub.add_parser("pit-list", help="List Private Integration Tokens configured on a sub-account via backend.leadconnectorhq.com.")
    pit_ls.add_argument("--location-id", required=True)

    em_dom = sub.add_parser("email-domains", help="Inspect dedicated sending domains, Mailgun bucket, and LC Email status for a sub-account.")
    em_dom.add_argument("--location-id", required=True)
    em_dom.add_argument("--company-id")

    live_aud = sub.add_parser("live-audit", help="Run a comprehensive live 5-layer location permission, user scope/alias, dashboard RBAC, Custom SMTP, and rebilling audit across the agency.")
    live_aud.add_argument("--company-id")
    live_aud.add_argument("--markup", type=int, default=5)

    sub.add_parser("social-accounts", help="List connected Social Planner accounts for GHL_LOCATION_ID.")

    soc_posts = sub.add_parser("social-posts", help="List Social Planner posts for GHL_LOCATION_ID.")
    soc_posts.add_argument("--limit", type=int, default=25)

    sub.add_parser("x-bridge-status", help="Verify Official X API OAuth 1.0a connection and inspect SQLite X bridge jobs.")

    xb_sync = sub.add_parser("x-bridge-sync", help="Preview or apply syncing of 16:9 GoHighLevel Social Planner video posts to Official X API.")
    xb_sync.add_argument("--apply", action="store_true")
    xb_sync.add_argument("--cutoff-iso", default=DEFAULT_CUTOFF_ISO)
    xb_sync.add_argument("--reuse-media-id", help="Reuse an already uploaded X media_id_string.")
    xb_sync.add_argument("--local-media", help="Local MP4 path override to avoid re-downloading from CDN.")

    return p


def execute(args, client_factory=Client, backend_factory=BackendClient) -> dict:
    if args.command == "doctor" and not args.live:
        return {
            "module": "legends-gohighlevel",
            "version": __version__,
            "ok": True,
            "mode": "offline",
            "live_access": "not_checked",
        }
    if args.command == "resources":
        return resolve_resources()
    if args.command == "subaccount-config":
        cfg = dict(load_subaccount_config(profile=getattr(args, "profile", None)))
        cfg.pop("_resolved_token", None)
        return cfg
    if args.command == "agency-config":
        return load_agency_config()
    if args.command == "rebilling-audit":
        return rebilling_audit(
            wallet_topup_usd=args.wallet_topup,
            markup=args.markup,
            location_id=args.location_id,
        )
    if args.command == "scope-audit":
        cur = json.loads(args.current_scopes_json) if args.current_scopes_json else None
        creator = json.loads(args.creator_scopes_json) if args.creator_scopes_json else None
        if cur is not None and not isinstance(cur, list):
            raise HighLevelError("--current-scopes-json must be a JSON array.")
        if creator is not None and not isinstance(creator, list):
            raise HighLevelError("--creator-scopes-json must be a JSON array.")
        return scope_audit(
            role=args.role,
            account_type=args.account_type,
            current_scopes=cur,
            creator_scopes=creator,
        )
    if args.command == "smtp-audit":
        return smtp_audit(company_id=args.company_id, location_id=args.location_id)
    if args.command == "dashboard-audit":
        cur_perms = json.loads(args.current_permissions_json) if args.current_permissions_json else None
        if cur_perms is not None and not isinstance(cur_perms, list):
            raise HighLevelError("--current-permissions-json must be a JSON array.")
        return dashboard_permission_audit(
            location_id=args.location_id,
            dashboard_id=args.dashboard_id,
            current_permissions=cur_perms,
        )

    # Internal backend commands
    if args.command in {
        "agency-locations",
        "location-rename",
        "location-unnerf",
        "agency-users",
        "user-inspect",
        "user-sync-locations",
        "user-unnerf",
        "smtp-status",
        "smtp-unlock",
        "dashboard-permissions",
        "unlock-dashboards",
        "rebilling-status",
        "rebilling-sync",
        "pit-list",
        "email-domains",
        "live-audit",
    }:
        if args.command == "location-rename":
            has_conf = bool(args.confirm_location or args.confirm_plan)
            if args.apply and not (args.confirm_location and args.confirm_plan):
                raise HighLevelError("--apply requires --confirm-location and --confirm-plan.")
            if has_conf and not args.apply:
                raise HighLevelError("Confirmation flags require --apply.")
        if args.command in {"user-sync-locations", "user-unnerf"}:
            has_conf = bool(args.confirm_user or args.confirm_plan)
            if args.apply and not (args.confirm_user and args.confirm_plan):
                raise HighLevelError("--apply requires --confirm-user and --confirm-plan.")
            if has_conf and not args.apply:
                raise HighLevelError("Confirmation flags require --apply.")
        if args.command in {"unlock-dashboards", "smtp-unlock", "location-unnerf", "rebilling-sync"}:
            if args.apply and not args.confirm_plan:
                raise HighLevelError("--apply requires --confirm-plan.")
            if args.confirm_plan and not args.apply:
                raise HighLevelError("--confirm-plan requires --apply.")

        backend = backend_factory(company_id=getattr(args, "company_id", None))
        if args.command == "agency-locations":
            return list_agency_locations(
                backend,
                company_id=args.company_id,
                location_id=args.location_id,
            )
        if args.command == "location-rename":
            plan = make_location_rename_plan(
                backend,
                location_id=args.location_id,
                name=args.name,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_location_rename_plan(
                backend,
                plan,
                confirm_location=args.confirm_location,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "location-unnerf":
            plan = make_location_unnerf_plan(
                backend,
                location_id=args.location_id,
                all_locations=args.all_locations,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_location_unnerf_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "agency-users":
            return list_agency_users(backend, company_id=args.company_id)
        if args.command == "user-inspect":
            return inspect_user(
                backend,
                user_id=args.user_id,
                email=args.email,
                company_id=args.company_id,
            )
        if args.command == "user-sync-locations":
            loc_list = (
                [x.strip() for x in args.location_ids.split(",") if x.strip()]
                if args.location_ids
                else None
            )
            plan = make_user_sync_locations_plan(
                backend,
                user_id=args.user_id,
                location_ids=loc_list,
                from_user_id=args.from_user_id,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_user_sync_locations_plan(
                backend,
                plan,
                confirm_user=args.confirm_user,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "user-unnerf":
            plan = make_user_unnerf_plan(
                backend,
                user_id=args.user_id,
                email=args.email,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_user_unnerf_plan(
                backend,
                plan,
                confirm_user=args.confirm_user,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "smtp-status":
            return inspect_smtp_status(
                backend,
                location_id=args.location_id,
                all_locations=args.all_locations,
                company_id=args.company_id,
            )
        if args.command == "smtp-unlock":
            plan = make_smtp_unlock_plan(
                backend,
                location_id=args.location_id,
                all_locations=args.all_locations,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_smtp_unlock_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "dashboard-permissions":
            return inspect_dashboard_permissions(
                backend,
                location_id=args.location_id,
                all_locations=args.all_locations,
                company_id=args.company_id,
            )
        if args.command == "unlock-dashboards":
            plan = make_unlock_dashboards_plan(
                backend,
                location_id=args.location_id,
                all_locations=args.all_locations,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_unlock_dashboards_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "rebilling-status":
            return inspect_rebilling_status(
                backend,
                location_id=args.location_id,
                all_locations=args.all_locations,
                company_id=args.company_id,
                markup=args.markup,
            )
        if args.command == "rebilling-sync":
            plan = make_rebilling_sync_plan(
                backend,
                location_id=args.location_id,
                all_locations=args.all_locations,
                company_id=args.company_id,
                markup=args.markup,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_rebilling_sync_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "pit-list":
            return list_private_integrations(backend, location_id=args.location_id)
        if args.command == "email-domains":
            return inspect_email_domains(
                backend,
                location_id=args.location_id,
                company_id=args.company_id,
            )
        if args.command == "live-audit":
            return live_agency_audit(backend, company_id=args.company_id, markup=args.markup)

    if args.command in {
        "custom-value-upsert",
        "custom-value-delete",
        "workflow-status",
        "tag-upsert",
        "tag-delete",
        "contact-upsert",
        "contact-tag",
        "contact-note",
        "opportunity-update",
    }:
        confirmations = bool(args.confirm_location or args.confirm_plan)
        if args.apply and not (args.confirm_location and args.confirm_plan):
            raise HighLevelError("--apply requires --confirm-location and --confirm-plan.")
        if confirmations and not args.apply:
            raise HighLevelError("Confirmation flags require --apply.")

    prof = getattr(args, "profile", None)
    client = client_factory(profile=prof) if (client_factory is Client and prof) else client_factory()
    if args.command == "doctor":
        return probe_live_lanes(client)
    if args.command == "subaccount-audit":
        return subaccount_audit(client)
    if args.command == "location":
        return location_snapshot(client)
    if args.command == "custom-values":
        return list_custom_values(client)
    if args.command == "custom-fields":
        return list_custom_fields(client)
    if args.command == "pipelines":
        return list_pipelines(client)
    if args.command == "calendars":
        return list_calendars(client)
    if args.command == "calendar-slots":
        return list_calendar_free_slots(
            client,
            calendar_id=args.calendar_id,
            start_date=args.start_date,
            end_date=args.end_date,
            timezone=args.timezone,
        )
    if args.command == "workflows":
        return list_workflows(client)
    if args.command == "forms":
        return list_forms(client, limit=args.limit)
    if args.command == "surveys":
        return list_surveys(client, limit=args.limit)
    if args.command == "tags":
        return list_tags(client)
    if args.command == "funnels":
        return list_funnels(client, limit=args.limit, include_redirects=args.include_redirects)
    if args.command == "objects":
        return list_objects(client)
    if args.command == "object-records":
        return search_object_records(
            client,
            object_key=args.object_key,
            query=args.query,
            page=args.page,
            page_limit=args.limit,
        )
    if args.command == "associations":
        return list_associations(client)
    if args.command == "voice-ai-agents":
        return list_voice_ai_agents(client)
    if args.command == "voice-ai-calls":
        return list_voice_ai_calls(client, limit=args.limit)
    if args.command == "conversation-ai-agents":
        return list_conversation_ai_agents(client)
    if args.command == "workflow-step-types":
        return list_workflow_step_types(client)
    if args.command == "workflow-inspect":
        return inspect_workflow_definition(client, workflow_id=args.workflow_id)
    if args.command == "workflow-logs":
        return list_workflow_logs(client, workflow_id=args.workflow_id, limit=args.limit)
    if args.command == "workflow-validate":
        defn = json.loads(args.definition_json)
        if not isinstance(defn, dict):
            raise HighLevelError("--definition-json must be a JSON object.")
        return validate_workflow_definition(client, definition=defn)
    if args.command == "workflow-status":
        wf_plan = make_workflow_status_plan(
            client,
            workflow_id=args.workflow_id,
            status=args.status,
        )
        if not args.apply:
            return {"mode": "preview", "plan": wf_plan, "writes_sent": 0}
        return apply_workflow_status_plan(
            client,
            wf_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command == "contacts":
        return search_contacts(client, query=args.query, limit=args.limit, full=args.full)
    if args.command == "opportunities":
        return search_opportunities(
            client,
            pipeline_id=args.pipeline_id,
            stage_id=args.stage_id,
            status=args.status,
            limit=args.limit,
        )
    if args.command == "conversations":
        return triage_conversations(client, limit=args.limit)
    if args.command == "social-accounts":
        return list_social_accounts(client)
    if args.command == "social-posts":
        return list_social_posts(client, limit=args.limit)
    if args.command == "x-bridge-status":
        x_client = XOfficialClient()
        bridge = GhlXBridge()
        return {
            "x_user": x_client.verify_user(),
            "db_path": str(bridge.db_path),
            "jobs": bridge.list_jobs(),
        }
    if args.command == "x-bridge-sync":
        bridge = GhlXBridge()
        local_override = Path(args.local_media) if getattr(args, "local_media", None) else None
        return bridge.sync(
            client,
            apply=bool(args.apply),
            cutoff_iso=args.cutoff_iso,
            reuse_media_id=getattr(args, "reuse_media_id", None),
            local_media_override=local_override,
        )

    if args.command in {"tag-upsert", "tag-delete"}:
        t_delete = args.command == "tag-delete"
        t_plan = make_tag_plan(
            client,
            name=args.name,
            tag_id=getattr(args, "tag_id", None),
            delete=t_delete,
        )
        if not args.apply:
            return {"mode": "preview", "plan": t_plan, "writes_sent": 0}
        return apply_tag_plan(
            client,
            t_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )

    if args.command == "contact-upsert":
        tag_list = [x.strip() for x in args.tags.split(",") if x.strip()] if args.tags else None
        c_plan = make_contact_upsert_plan(
            client,
            email=args.email,
            phone=args.phone,
            first_name=args.first_name,
            last_name=args.last_name,
            name=args.name,
            tags=tag_list,
        )
        if not args.apply:
            return {"mode": "preview", "plan": c_plan, "writes_sent": 0}
        return apply_contact_upsert_plan(
            client,
            c_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )

    if args.command == "contact-tag":
        tag_list = [x.strip() for x in args.tags.split(",") if x.strip()]
        ct_plan = make_contact_tag_plan(
            client,
            contact_id=args.contact_id,
            tags=tag_list,
            remove=args.remove,
        )
        if not args.apply:
            return {"mode": "preview", "plan": ct_plan, "writes_sent": 0}
        return apply_contact_tag_plan(
            client,
            ct_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )

    if args.command == "contact-note":
        cn_plan = make_contact_note_plan(
            client,
            contact_id=args.contact_id,
            body=args.body,
        )
        if not args.apply:
            return {"mode": "preview", "plan": cn_plan, "writes_sent": 0}
        return apply_contact_note_plan(
            client,
            cn_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )

    if args.command == "opportunity-update":
        o_plan = make_opportunity_update_plan(
            client,
            opportunity_id=args.opportunity_id,
            pipeline_stage_id=args.stage_id,
            status=args.status,
            monetary_value=args.monetary_value,
            title=args.title,
        )
        if not args.apply:
            return {"mode": "preview", "plan": o_plan, "writes_sent": 0}
        return apply_opportunity_update_plan(
            client,
            o_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )

    delete = args.command == "custom-value-delete"
    plan = make_custom_value_plan(
        client,
        name=args.name,
        value=None if delete else args.value,
        custom_value_id=args.custom_value_id,
        delete=delete,
    )
    if not args.apply:
        return {"mode": "preview", "plan": plan, "writes_sent": 0}
    return apply_custom_value_plan(
        client,
        plan,
        confirm_location=args.confirm_location,
        confirm_plan=args.confirm_plan,
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        result["observed_at"] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except HighLevelError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    except (ValueError, TypeError, KeyError):
        print(
            json.dumps({"ok": False, "error": "Unexpected API or input data; inspect state before retrying."}),
            file=sys.stderr,
        )
        return 1
