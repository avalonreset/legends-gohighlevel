"""JSON CLI with offline doctor, sub-account CRM operations, live agency backend control, preview-first mutations, and governance audits."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from . import __version__
from .agency import (
    apply_location_batch_clone_plan,
    apply_location_create_plan,
    apply_location_full_unnerf_plan,
    apply_location_rebrand_plan,
    apply_location_rename_plan,
    apply_location_unnerf_plan,
    apply_pit_create_plan,
    apply_pit_delete_plan,
    apply_rebilling_sync_plan,
    apply_smtp_unlock_plan,
    apply_snapshot_create_plan,
    apply_snapshot_push_plan,
    apply_snapshot_refresh_plan,
    apply_snapshot_share_link_plan,
    apply_unlock_dashboards_plan,
    apply_user_sync_locations_plan,
    apply_user_unnerf_plan,
    apply_workflow_bulk_status_plan,
    apply_workflow_steps_rebrand_plan,
    inspect_agency_snapshot,
    inspect_agency_workflows_xray,
    inspect_dashboard_permissions,
    inspect_email_domains,
    inspect_location_clone_audit,
    inspect_rebilling_status,
    inspect_smtp_status,
    inspect_user,
    list_agency_locations,
    list_agency_snapshots,
    list_agency_users,
    list_location_workflows_backend,
    list_private_integrations,
    live_agency_audit,
    make_location_batch_clone_plan,
    make_location_create_plan,
    make_location_full_unnerf_plan,
    make_location_rebrand_plan,
    make_location_rename_plan,
    make_location_unnerf_plan,
    make_pit_create_plan,
    make_pit_delete_plan,
    make_rebilling_sync_plan,
    make_smtp_unlock_plan,
    make_snapshot_create_plan,
    make_snapshot_push_plan,
    make_snapshot_refresh_plan,
    make_snapshot_share_link_plan,
    make_unlock_dashboards_plan,
    make_user_sync_locations_plan,
    make_user_unnerf_plan,
    make_workflow_bulk_status_plan,
    make_workflow_steps_rebrand_plan,
)
from .api import (
    BackendClient,
    Client,
    HighLevelError,
    delete_subaccount_profile,
    load_agency_config,
    load_subaccount_config,
    save_subaccount_profile,
    set_default_subaccount_profile,
)
from .crm import (
    apply_appointment_create_plan,
    apply_calendar_update_plan,
    apply_contact_note_plan,
    apply_contact_tag_plan,
    apply_contact_task_plan,
    apply_contact_upsert_plan,
    apply_conversation_send_plan,
    apply_custom_field_plan,
    apply_custom_value_plan,
    apply_opportunity_update_plan,
    apply_subaccount_rebrand_plan,
    apply_subaccount_update_plan,
    apply_tag_plan,
    apply_trigger_link_plan,
    apply_workflow_status_plan,
    inspect_profiles_matrix,
    inspect_workflow_definition,
    list_associations,
    list_blogs,
    list_calendar_events,
    list_calendar_free_slots,
    list_calendars,
    list_contact_notes,
    list_contact_tasks,
    list_conversation_ai_agents,
    list_conversation_messages,
    list_custom_fields,
    list_custom_values,
    list_email_templates,
    list_forms,
    list_funnels,
    list_invoices,
    list_media_files,
    list_objects,
    list_pipelines,
    list_products,
    list_subaccount_users,
    list_surveys,
    list_tags,
    list_transactions,
    list_trigger_links,
    list_voice_ai_agents,
    list_voice_ai_calls,
    list_workflow_logs,
    list_workflow_step_types,
    list_workflows,
    location_snapshot,
    make_appointment_create_plan,
    make_calendar_update_plan,
    make_contact_note_plan,
    make_contact_tag_plan,
    make_contact_task_plan,
    make_contact_upsert_plan,
    make_conversation_send_plan,
    make_custom_field_plan,
    make_custom_value_plan,
    make_opportunity_update_plan,
    make_subaccount_rebrand_plan,
    make_subaccount_update_plan,
    make_tag_plan,
    make_trigger_link_plan,
    make_workflow_status_plan,
    probe_live_lanes,
    search_contacts,
    search_object_records,
    search_opportunities,
    subaccount_audit,
    subaccount_rebrand_audit,
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

    ag_wfs = sub.add_parser("agency-workflows", help="List workflows on any sub-account via backend.leadconnectorhq.com with published/draft counts and CAPI/webhook risk flags.")
    ag_wfs.add_argument("--location-id", required=True)
    ag_wfs.add_argument("--company-id")

    wf_bulk = sub.add_parser("workflow-bulk-status", help="Preview or apply bulk workflow status changes (draft/published) via PUT /workflow/:locationId/change-status.")
    wf_bulk.add_argument("--location-id")
    wf_bulk.add_argument("--location-ids", help="Comma-separated list of locationIds.")
    wf_bulk.add_argument("--workflow-ids", help="Comma-separated list of workflowIds (omit to target all workflows in the location).")
    wf_bulk.add_argument("--status", choices=["draft", "published"], required=True)
    wf_bulk.add_argument("--all", action="store_true", help="Include workflows already in the target status.")
    wf_bulk.add_argument("--company-id")
    wf_bulk.add_argument("--apply", action="store_true")
    wf_bulk.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    snaps_ls = sub.add_parser("snapshots-list", help="List agency snapshots via GET /snapshots/v2/:companyId.")
    snaps_ls.add_argument("--company-id")
    snaps_ls.add_argument("--type", choices=["own", "imported", "shared"], default="own")
    snaps_ls.add_argument("--limit", type=int, default=50)

    snap_insp = sub.add_parser("snapshot-inspect", help="Inspect a snapshot's 16-category asset inventory, dehydration state, and push batches.")
    snap_insp.add_argument("--snapshot-id", required=True)
    snap_insp.add_argument("--company-id")
    snap_insp.add_argument("--type", choices=["own", "imported", "shared"], default="own")

    snap_cr = sub.add_parser("snapshot-create", help="Preview or apply creating a new V2 agency snapshot from a source sub-account.")
    snap_cr.add_argument("--name", required=True)
    snap_cr.add_argument("--location-id", required=True)
    snap_cr.add_argument("--company-id")
    snap_cr.add_argument("--wait", action="store_true", help="Wait for snapshot dehydration to complete.")
    snap_cr.add_argument("--timeout-seconds", type=int, default=90)
    snap_cr.add_argument("--apply", action="store_true")
    snap_cr.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    snap_ref = sub.add_parser("snapshot-refresh", help="Preview or apply refreshing an existing V2 agency snapshot from its linked source sub-account.")
    snap_ref.add_argument("--snapshot-id", required=True)
    snap_ref.add_argument("--company-id")
    snap_ref.add_argument("--wait", action="store_true", help="Wait for snapshot refresh dehydration to complete.")
    snap_ref.add_argument("--timeout-seconds", type=int, default=90)
    snap_ref.add_argument("--apply", action="store_true")
    snap_ref.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    snap_push = sub.add_parser("snapshot-push", help="Preview or apply pushing an agency V2 snapshot into one or more sub-accounts with optional post-push workflow drafting and dashboard unlocking.")
    snap_push.add_argument("--snapshot-id", required=True)
    snap_push.add_argument("--location-id")
    snap_push.add_argument("--location-ids", help="Comma-separated list of target locationIds.")
    snap_push.add_argument("--company-id")
    snap_push.add_argument("--skip-conflicts", action="store_true", help="Skip conflicting assets instead of overwriting conflicts.")
    snap_push.add_argument("--keep-workflow-status", action="store_true", help="Do not automatically bulk-switch target workflows to draft after push.")
    snap_push.add_argument("--skip-unlock-dashboards", action="store_true", help="Do not automatically unlock target dashboards RBAC after push.")
    snap_push.add_argument("--no-wait", action="store_true", help="Return immediately without polling push batch completion.")
    snap_push.add_argument("--timeout-seconds", type=int, default=120)
    snap_push.add_argument("--apply", action="store_true")
    snap_push.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    loc_full = sub.add_parser("location-full-unnerf", help="Preview or apply a single 5-layer governance un-nerf (40 location flags, user scopes + alias, dashboards RBAC, Custom SMTP, and 4-store rebilling).")
    loc_full.add_argument("--location-id")
    loc_full.add_argument("--location-ids", help="Comma-separated list of locationIds.")
    loc_full.add_argument("--user-id")
    loc_full.add_argument("--email")
    loc_full.add_argument("--company-id")
    loc_full.add_argument("--markup", type=int, default=5)
    loc_full.add_argument("--apply", action="store_true")
    loc_full.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    loc_clone_aud = sub.add_parser("location-clone-audit", help="Deep-audit a cloned or existing sub-account via backend.leadconnectorhq.com for asset parity, workflow draft safety, governance health, and brand-term leaks.")
    loc_clone_aud.add_argument("--location-id", required=True)
    loc_clone_aud.add_argument("--company-id")
    loc_clone_aud.add_argument("--brand-terms", help="Comma-separated list of source brand terms to scan for (e.g. webmakelij,intake).")

    em_tmps = sub.add_parser("email-templates", help="List sub-account Email Builder templates via Official API v2.")
    em_tmps.add_argument("--limit", type=int, default=100)

    trig_lnks = sub.add_parser("trigger-links", help="List sub-account trigger links via Official API v2.")

    sub_reb_aud = sub.add_parser("subaccount-rebrand-audit", help="Audit a sub-account via Official API v2 (GHL_PIT) for workflow draft state, integration risk workflows, empty custom values, and source brand terms.")
    sub_reb_aud.add_argument("--brand-terms", help="Comma-separated list of source brand terms to scan for.")

    prof_mat = sub.add_parser("profiles-matrix", help="Compare asset and workflow status across multiple configured sub-account profiles in ~/.config/legends-gohighlevel/config.json.")
    prof_mat.add_argument("--profiles", help="Optional comma-separated list of profile names.")

    prof_set = sub.add_parser("subaccount-profile-set", help="Save or update a named sub-account profile (location_id + PIT) in ~/.config/legends-gohighlevel/config.json.")
    prof_set.add_argument("--profile-name", required=True, help="Profile key (e.g. klant-a or test-2).")
    prof_set.add_argument("--location-id", required=True)
    prof_set.add_argument("--pit", required=True, help="Sub-account Private Integration Token (pit-...).")
    prof_set.add_argument("--name", help="Human-readable workspace label.")
    prof_set.add_argument("--set-default", action="store_true", help="Make this profile the default sub-account profile.")

    prof_use = sub.add_parser("subaccount-profile-use", help="Switch the default sub-account profile in ~/.config/legends-gohighlevel/config.json.")
    prof_use.add_argument("--profile-name", required=True)

    prof_del = sub.add_parser("subaccount-profile-delete", help="Remove a named sub-account profile from ~/.config/legends-gohighlevel/config.json.")
    prof_del.add_argument("--profile-name", required=True)

    sub_up = sub.add_parser("subaccount-update", help="Preview or apply a sub-account Business Profile update via Official API v2 (PUT /locations/:id).")
    sub_up.add_argument("--name")
    sub_up.add_argument("--email")
    sub_up.add_argument("--phone")
    sub_up.add_argument("--website")
    sub_up.add_argument("--address")
    sub_up.add_argument("--city")
    sub_up.add_argument("--state")
    sub_up.add_argument("--postal-code")
    sub_up.add_argument("--country")
    sub_up.add_argument("--timezone")
    sub_up.add_argument("--logo-url")
    sub_up.add_argument("--apply", action="store_true")
    sub_up.add_argument("--confirm-location")
    sub_up.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    sub_reb = sub.add_parser("subaccount-rebrand", help="Preview or apply an atomic sub-account rebrand (Business Profile, Custom Values, Trigger Links, Calendars) via Official API v2 (GHL_PIT).")
    sub_reb.add_argument("--name")
    sub_reb.add_argument("--email")
    sub_reb.add_argument("--phone")
    sub_reb.add_argument("--website")
    sub_reb.add_argument("--address")
    sub_reb.add_argument("--city")
    sub_reb.add_argument("--state")
    sub_reb.add_argument("--postal-code")
    sub_reb.add_argument("--country")
    sub_reb.add_argument("--timezone")
    sub_reb.add_argument("--logo-url")
    sub_reb.add_argument("--replace-from", help="Comma-separated list of old brand terms/URLs to replace.")
    sub_reb.add_argument("--replace-to", help="Comma-separated list of new brand terms/URLs (1-to-1 with --replace-from).")
    sub_reb.add_argument("--custom-values-json", help="JSON object of explicit Custom Value names/keys to values.")
    sub_reb.add_argument("--apply", action="store_true")
    sub_reb.add_argument("--confirm-location")
    sub_reb.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    for cf_cmd in ("custom-field-upsert", "custom-field-delete"):
        cfp = sub.add_parser(cf_cmd, help="Preview or apply a sub-account Custom Field creation, update, or deletion.")
        cfp.add_argument("--name", required=True)
        if cf_cmd == "custom-field-upsert":
            cfp.add_argument("--data-type", default="TEXT", help="Field dataType (e.g. TEXT, LARGE_TEXT, NUMERICAL, PHONE, MONETORY, SINGLE_OPTIONS, MULTIPLE_OPTIONS, DATE).")
            cfp.add_argument("--model", default="contact", choices=["contact", "opportunity"])
            cfp.add_argument("--placeholder")
            cfp.add_argument("--options", help="Comma-separated options for SINGLE_OPTIONS or MULTIPLE_OPTIONS.")
            cfp.add_argument("--custom-field-id")
        else:
            cfp.add_argument("--custom-field-id")
        cfp.add_argument("--apply", action="store_true")
        cfp.add_argument("--confirm-location")
        cfp.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    for tl_cmd in ("trigger-link-upsert", "trigger-link-delete"):
        tlp = sub.add_parser(tl_cmd, help="Preview or apply a sub-account Trigger Link creation, update, or deletion.")
        tlp.add_argument("--name", required=True)
        if tl_cmd == "trigger-link-upsert":
            tlp.add_argument("--redirect-to", required=True)
            tlp.add_argument("--link-id")
        else:
            tlp.add_argument("--link-id")
        tlp.add_argument("--apply", action="store_true")
        tlp.add_argument("--confirm-location")
        tlp.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    cal_up = sub.add_parser("calendar-update", help="Preview or apply updating a sub-account Calendar name, slug, description, or active state.")
    cal_up.add_argument("--calendar-id", required=True)
    cal_up.add_argument("--name")
    cal_up.add_argument("--slug")
    cal_up.add_argument("--description")
    cal_up.add_argument("--active", action="store_true", help="Set calendar isActive=true.")
    cal_up.add_argument("--inactive", action="store_true", help="Set calendar isActive=false.")
    cal_up.add_argument("--apply", action="store_true")
    cal_up.add_argument("--confirm-location")
    cal_up.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    conv_msgs = sub.add_parser("conversation-messages", help="List messages inside a sub-account conversation thread.")
    conv_msgs.add_argument("--conversation-id", required=True)
    conv_msgs.add_argument("--limit", type=int, default=20)

    conv_send = sub.add_parser("conversation-send", help="Preview or apply sending an outbound message (SMS, Email, WhatsApp, Live_Chat) to a contact.")
    conv_send.add_argument("--contact-id", required=True)
    conv_send.add_argument("--type", default="SMS", choices=["SMS", "Email", "WhatsApp", "Live_Chat", "IG", "FB"])
    conv_send.add_argument("--message")
    conv_send.add_argument("--subject")
    conv_send.add_argument("--html")
    conv_send.add_argument("--apply", action="store_true")
    conv_send.add_argument("--confirm-location")
    conv_send.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    pit_cr = sub.add_parser("pit-create", help="Preview or apply creating a full-scope Private Integration Token (pit-...) on a sub-account via backend.leadconnectorhq.com.")
    pit_cr.add_argument("--location-id", required=True)
    pit_cr.add_argument("--name", required=True)
    pit_cr.add_argument("--description", default="")
    pit_cr.add_argument("--save-profile", help="Automatically save the new PIT into ~/.config/legends-gohighlevel/config.json under this profile name.")
    pit_cr.add_argument("--set-default-profile", action="store_true", help="Set --save-profile as the default sub-account profile.")
    pit_cr.add_argument("--reveal-token", action="store_true", help="Include the raw unmasked token in the applied output.")
    pit_cr.add_argument("--company-id")
    pit_cr.add_argument("--apply", action="store_true")
    pit_cr.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    pit_del = sub.add_parser("pit-delete", help="Preview or apply deleting a Private Integration on a sub-account via backend.leadconnectorhq.com.")
    pit_del.add_argument("--location-id", required=True)
    pit_del.add_argument("--integration-id", required=True)
    pit_del.add_argument("--company-id")
    pit_del.add_argument("--apply", action="store_true")
    pit_del.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    loc_cr = sub.add_parser("location-create", help="Preview or apply creating a new sub-account via POST /locations/ on backend.leadconnectorhq.com.")
    loc_cr.add_argument("--name", required=True)
    loc_cr.add_argument("--from-location-id", help="Inherit country, timezone, and contact defaults from an existing sub-account.")
    loc_cr.add_argument("--email")
    loc_cr.add_argument("--phone")
    loc_cr.add_argument("--website")
    loc_cr.add_argument("--address")
    loc_cr.add_argument("--city")
    loc_cr.add_argument("--state")
    loc_cr.add_argument("--postal-code")
    loc_cr.add_argument("--country")
    loc_cr.add_argument("--timezone")
    loc_cr.add_argument("--company-id")
    loc_cr.add_argument("--apply", action="store_true")
    loc_cr.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    loc_bclone = sub.add_parser("location-batch-clone", help="1-command multi-sub-account batch cloner: creates N sub-accounts, pushes a V2 snapshot in 1 batch, drafts all workflows, runs 5-layer governance un-nerf + Stripe hold, and audits all clones.")
    loc_bclone.add_argument("--source-location-id", required=True)
    loc_bclone.add_argument("--names", required=True, help="Comma-separated list of target sub-account names to provision and clone.")
    loc_bclone.add_argument("--snapshot-id", help="Existing V2 snapshot ID to push (if omitted, creates a fresh snapshot from --source-location-id).")
    loc_bclone.add_argument("--assign-email", help="Assign all cloned sub-accounts to this user email (plus +hubpro alias).")
    loc_bclone.add_argument("--assign-user-id", help="Assign all cloned sub-accounts to this user ID.")
    loc_bclone.add_argument("--keep-workflow-status", action="store_true", help="Do not bulk-switch cloned workflows to draft.")
    loc_bclone.add_argument("--skip-unnerf", action="store_true", help="Skip the 5-layer governance un-nerf and Stripe rebilling hold step.")
    loc_bclone.add_argument("--create-pits", action="store_true", help="Automatically mint a 180-scope Private Integration Token on each cloned sub-account.")
    loc_bclone.add_argument("--markup", type=int, default=5)
    loc_bclone.add_argument("--timeout-seconds", type=int, default=180)
    loc_bclone.add_argument("--company-id")
    loc_bclone.add_argument("--apply", action="store_true")
    loc_bclone.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    loc_reb = sub.add_parser("location-rebrand", help="Preview or apply an agency-level atomic sub-account rebrand (Business Profile, Custom Values, Trigger Links, Calendars, and optional internal Workflow Steps) via backend.leadconnectorhq.com.")
    loc_reb.add_argument("--location-id", required=True)
    loc_reb.add_argument("--name")
    loc_reb.add_argument("--email")
    loc_reb.add_argument("--phone")
    loc_reb.add_argument("--website")
    loc_reb.add_argument("--address")
    loc_reb.add_argument("--city")
    loc_reb.add_argument("--state")
    loc_reb.add_argument("--postal-code")
    loc_reb.add_argument("--country")
    loc_reb.add_argument("--timezone")
    loc_reb.add_argument("--logo-url")
    loc_reb.add_argument("--replace-from", help="Comma-separated list of old brand terms/URLs to replace.")
    loc_reb.add_argument("--replace-to", help="Comma-separated list of new brand terms/URLs (1-to-1 with --replace-from).")
    loc_reb.add_argument("--custom-values-json", help="JSON object of explicit Custom Value names/keys to values.")
    loc_reb.add_argument("--include-workflow-steps", action="store_true", help="Also apply --replace-from/--replace-to inside internal workflow action steps.")
    loc_reb.add_argument("--workflow-from-name", help="Rewrite email step from_name across workflows.")
    loc_reb.add_argument("--workflow-from-email", help="Rewrite email step from_email across workflows.")
    loc_reb.add_argument("--workflow-pixel-id", help="Rewrite Meta CAPI step pixel_id across workflows.")
    loc_reb.add_argument("--workflow-capi-token", help="Rewrite Meta CAPI step access_token across workflows.")
    loc_reb.add_argument("--company-id")
    loc_reb.add_argument("--apply", action="store_true")
    loc_reb.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    wf_xray = sub.add_parser("agency-workflow-xray", help="Deep-inspect internal workflow action steps (email senders/preheaders, Meta CAPI pixels, webhook URLs, and brand-term leaks) via GET /workflow/:locationId/:workflowId.")
    wf_xray.add_argument("--location-id", required=True)
    wf_xray.add_argument("--workflow-id", help="Inspect a single workflow ID (omit to x-ray all workflows in the location).")
    wf_xray.add_argument("--brand-terms", help="Comma-separated list of source brand terms to scan for inside workflow steps.")
    wf_xray.add_argument("--company-id")

    wf_sreb = sub.add_parser("workflow-steps-rebrand", help="Preview or apply bulk rebranding of internal workflow steps (email from_name/from_email/subject/preHeader, webhook URLs, Meta CAPI pixel_id/access_token) via PUT /workflow/:locationId/:workflowId.")
    wf_sreb.add_argument("--location-id", required=True)
    wf_sreb.add_argument("--workflow-ids", help="Comma-separated list of workflow IDs (omit to scan all workflows in the location).")
    wf_sreb.add_argument("--replace-from", help="Comma-separated list of old brand terms/URLs to replace inside workflow steps.")
    wf_sreb.add_argument("--replace-to", help="Comma-separated list of new brand terms/URLs (1-to-1 with --replace-from).")
    wf_sreb.add_argument("--from-name", help="Explicitly set email step from_name across matching steps.")
    wf_sreb.add_argument("--from-email", help="Explicitly set email step from_email across matching steps.")
    wf_sreb.add_argument("--templatize-senders", action="store_true", help="Convert hardcoded email step from_name/from_email to {{location.name}} and {{location.email}}.")
    wf_sreb.add_argument("--pixel-id", help="Explicitly set Meta CAPI step pixel_id across matching steps.")
    wf_sreb.add_argument("--capi-access-token", help="Explicitly set Meta CAPI step access_token across matching steps.")
    wf_sreb.add_argument("--company-id")
    wf_sreb.add_argument("--apply", action="store_true")
    wf_sreb.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    snap_sh = sub.add_parser("snapshot-share-link", help="Preview or apply generating a shareable snapshot link via POST /snapshots/share/v2/link.")
    snap_sh.add_argument("--snapshot-id", required=True)
    snap_sh.add_argument("--share-type", default="link", choices=["link", "permanent_link", "agency_restricted", "location_restricted"])
    snap_sh.add_argument("--relationship-number", help="Required if --share-type is agency_restricted.")
    snap_sh.add_argument("--share-location-id", help="Required if --share-type is location_restricted.")
    snap_sh.add_argument("--company-id")
    snap_sh.add_argument("--apply", action="store_true")
    snap_sh.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    sub.add_parser("subaccount-users", help="List users assigned to the sub-account via Official API v2 (GET /users/?locationId=...).")

    c_notes = sub.add_parser("contact-notes", help="List notes on a contact via Official API v2.")
    c_notes.add_argument("--contact-id", required=True)

    c_tasks = sub.add_parser("contact-tasks", help="List tasks on a contact via Official API v2.")
    c_tasks.add_argument("--contact-id", required=True)

    c_task_up = sub.add_parser("contact-task-upsert", help="Preview or apply creating or updating a task on a contact via Official API v2.")
    c_task_up.add_argument("--contact-id", required=True)
    c_task_up.add_argument("--title", required=True)
    c_task_up.add_argument("--body")
    c_task_up.add_argument("--due-date", help="ISO-8601 due date (e.g. 2026-12-31T17:00:00Z).")
    c_task_up.add_argument("--completed", action="store_true")
    c_task_up.add_argument("--assigned-to", help="User ID to assign the task to.")
    c_task_up.add_argument("--task-id", help="Task ID to update (omit to create a new task).")
    c_task_up.add_argument("--apply", action="store_true")
    c_task_up.add_argument("--confirm-location")
    c_task_up.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    cal_evs = sub.add_parser("calendar-events", help="List calendar events/appointments in the sub-account via Official API v2.")
    cal_evs.add_argument("--calendar-id", help="Calendar ID (defaults to first sub-account calendar if omitted).")
    cal_evs.add_argument("--user-id")
    cal_evs.add_argument("--group-id")
    cal_evs.add_argument("--start-time", help="Epoch ms start time (defaults to 30 days ago).")
    cal_evs.add_argument("--end-time", help="Epoch ms end time (defaults to 60 days ahead).")

    appt_cr = sub.add_parser("appointment-create", help="Preview or apply booking a calendar appointment via Official API v2.")
    appt_cr.add_argument("--calendar-id", required=True)
    appt_cr.add_argument("--contact-id", required=True)
    appt_cr.add_argument("--start-time", required=True, help="ISO-8601 start time (e.g. 2026-12-01T10:00:00-05:00).")
    appt_cr.add_argument("--end-time", help="ISO-8601 end time.")
    appt_cr.add_argument("--title")
    appt_cr.add_argument("--status", default="confirmed", choices=["confirmed", "new", "cancelled", "showed", "noshow", "invalid"])
    appt_cr.add_argument("--assigned-user-id")
    appt_cr.add_argument("--address")
    appt_cr.add_argument("--apply", action="store_true")
    appt_cr.add_argument("--confirm-location")
    appt_cr.add_argument("--confirm-plan", help="SHA-256 from the reviewed preview.")

    medias_cmd = sub.add_parser("medias", help="List files in the sub-account Media Library via Official API v2.")
    medias_cmd.add_argument("--limit", type=int, default=50)
    medias_cmd.add_argument("--query", help="Optional filename search query.")

    prods_cmd = sub.add_parser("products", help="List products in the sub-account via Official API v2.")
    prods_cmd.add_argument("--limit", type=int, default=50)

    invs_cmd = sub.add_parser("invoices", help="List invoices in the sub-account via Official API v2.")
    invs_cmd.add_argument("--limit", type=int, default=50)
    invs_cmd.add_argument("--offset", type=int, default=0)

    txs_cmd = sub.add_parser("transactions", help="List payment transactions in the sub-account via Official API v2.")
    txs_cmd.add_argument("--limit", type=int, default=50)
    txs_cmd.add_argument("--offset", type=int, default=0)

    blogs_cmd = sub.add_parser("blogs", help="List blog sites in the sub-account via Official API v2.")
    blogs_cmd.add_argument("--limit", type=int, default=20)
    blogs_cmd.add_argument("--skip", type=int, default=0)

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


def _parse_replace_pairs(replace_from: str | None, replace_to: str | None) -> list[tuple[str, str]]:
    if not replace_from and not replace_to:
        return []
    if not replace_from or replace_to is None:
        raise HighLevelError("Provide both --replace-from and --replace-to (comma-separated 1-to-1 pairs).")
    from_items = [x.strip() for x in replace_from.split(",") if x.strip()]
    to_items = [x.strip() for x in replace_to.split(",")]
    if len(from_items) != len(to_items):
        raise HighLevelError("--replace-from and --replace-to must have the same number of comma-separated items.")
    return list(zip(from_items, to_items))


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
    if args.command == "subaccount-profile-set":
        return save_subaccount_profile(
            profile=args.profile_name,
            location_id=args.location_id,
            pit=args.pit,
            name=args.name,
            set_default=bool(args.set_default),
        )
    if args.command == "subaccount-profile-use":
        return set_default_subaccount_profile(profile=args.profile_name)
    if args.command == "subaccount-profile-delete":
        return delete_subaccount_profile(profile=args.profile_name)
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

    if args.command == "profiles-matrix":
        prof_list = [x.strip() for x in args.profiles.split(",") if x.strip()] if args.profiles else None
        return inspect_profiles_matrix(profiles=prof_list, client_factory=client_factory)

    # Internal backend commands
    if args.command in {
        "agency-locations",
        "location-create",
        "location-batch-clone",
        "location-rebrand",
        "location-rename",
        "location-unnerf",
        "location-full-unnerf",
        "location-clone-audit",
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
        "pit-create",
        "pit-delete",
        "email-domains",
        "live-audit",
        "agency-workflows",
        "agency-workflow-xray",
        "workflow-bulk-status",
        "workflow-steps-rebrand",
        "snapshots-list",
        "snapshot-inspect",
        "snapshot-create",
        "snapshot-refresh",
        "snapshot-push",
        "snapshot-share-link",
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
        if args.command in {
            "unlock-dashboards",
            "smtp-unlock",
            "location-create",
            "location-batch-clone",
            "location-rebrand",
            "location-unnerf",
            "location-full-unnerf",
            "rebilling-sync",
            "pit-create",
            "pit-delete",
            "workflow-bulk-status",
            "workflow-steps-rebrand",
            "snapshot-create",
            "snapshot-refresh",
            "snapshot-push",
            "snapshot-share-link",
        }:
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
        if args.command == "agency-workflows":
            return list_location_workflows_backend(backend, location_id=args.location_id)
        if args.command == "workflow-bulk-status":
            loc_list = (
                [x.strip() for x in args.location_ids.split(",") if x.strip()]
                if args.location_ids
                else None
            )
            wf_list = (
                [x.strip() for x in args.workflow_ids.split(",") if x.strip()]
                if args.workflow_ids
                else None
            )
            plan = make_workflow_bulk_status_plan(
                backend,
                status=args.status,
                location_id=args.location_id,
                location_ids=loc_list,
                workflow_ids=wf_list,
                only_changed=not bool(args.all),
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_workflow_bulk_status_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "snapshots-list":
            return list_agency_snapshots(
                backend,
                company_id=args.company_id,
                snapshot_type=args.type,
                limit=args.limit,
            )
        if args.command == "snapshot-inspect":
            return inspect_agency_snapshot(
                backend,
                snapshot_id=args.snapshot_id,
                company_id=args.company_id,
                snapshot_type=args.type,
            )
        if args.command == "snapshot-create":
            plan = make_snapshot_create_plan(
                backend,
                name=args.name,
                location_id=args.location_id,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_snapshot_create_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
                wait=bool(args.wait),
                timeout_seconds=args.timeout_seconds,
            )
        if args.command == "snapshot-refresh":
            plan = make_snapshot_refresh_plan(
                backend,
                snapshot_id=args.snapshot_id,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_snapshot_refresh_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
                wait=bool(args.wait),
                timeout_seconds=args.timeout_seconds,
            )
        if args.command == "snapshot-push":
            loc_list = (
                [x.strip() for x in args.location_ids.split(",") if x.strip()]
                if args.location_ids
                else []
            )
            if args.location_id and args.location_id.strip():
                if args.location_id.strip() not in loc_list:
                    loc_list.append(args.location_id.strip())
            plan = make_snapshot_push_plan(
                backend,
                snapshot_id=args.snapshot_id,
                location_ids=loc_list,
                company_id=args.company_id,
                overwrite_conflicts=not bool(args.skip_conflicts),
                draft_workflows=not bool(args.keep_workflow_status),
                unlock_dashboards=not bool(args.skip_unlock_dashboards),
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_snapshot_push_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
                wait=not bool(args.no_wait),
                timeout_seconds=args.timeout_seconds,
            )
        if args.command == "location-full-unnerf":
            loc_list = (
                [x.strip() for x in args.location_ids.split(",") if x.strip()]
                if args.location_ids
                else None
            )
            plan = make_location_full_unnerf_plan(
                backend,
                location_id=args.location_id,
                location_ids=loc_list,
                user_id=args.user_id,
                email=args.email,
                company_id=args.company_id,
                markup=args.markup,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_location_full_unnerf_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "location-clone-audit":
            terms = (
                [x.strip() for x in args.brand_terms.split(",") if x.strip()]
                if args.brand_terms
                else None
            )
            return inspect_location_clone_audit(
                backend,
                location_id=args.location_id,
                company_id=args.company_id,
                brand_terms=terms,
            )
        if args.command == "pit-create":
            plan = make_pit_create_plan(
                backend,
                location_id=args.location_id,
                name=args.name,
                description=args.description,
                save_profile=args.save_profile,
                set_default_profile=bool(args.set_default_profile),
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_pit_create_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
                reveal_token=bool(args.reveal_token),
            )
        if args.command == "pit-delete":
            plan = make_pit_delete_plan(
                backend,
                location_id=args.location_id,
                integration_id=args.integration_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_pit_delete_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "location-create":
            plan = make_location_create_plan(
                backend,
                name=args.name,
                from_location_id=args.from_location_id,
                email=args.email,
                phone=args.phone,
                website=args.website,
                address=args.address,
                city=args.city,
                state=args.state,
                postal_code=args.postal_code,
                country=args.country,
                timezone=args.timezone,
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_location_create_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "location-batch-clone":
            target_names = [x.strip() for x in args.names.split(",") if x.strip()]
            plan = make_location_batch_clone_plan(
                backend,
                source_location_id=args.source_location_id,
                names=target_names,
                snapshot_id=args.snapshot_id,
                assign_email=args.assign_email,
                assign_user_id=args.assign_user_id,
                draft_workflows=not bool(args.keep_workflow_status),
                full_unnerf=not bool(args.skip_unnerf),
                markup=args.markup,
                create_pits=bool(args.create_pits),
                company_id=args.company_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_location_batch_clone_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
                timeout_seconds=args.timeout_seconds,
            )
        if args.command == "location-rebrand":
            pairs = _parse_replace_pairs(args.replace_from, args.replace_to)
            cv_map = json.loads(args.custom_values_json) if args.custom_values_json else None
            if cv_map is not None and not isinstance(cv_map, dict):
                raise HighLevelError("--custom-values-json must be a JSON object.")
            plan = make_location_rebrand_plan(
                backend,
                location_id=args.location_id,
                company_id=args.company_id,
                name=args.name,
                email=args.email,
                phone=args.phone,
                website=args.website,
                address=args.address,
                city=args.city,
                state=args.state,
                postal_code=args.postal_code,
                country=args.country,
                timezone=args.timezone,
                logo_url=args.logo_url,
                replace_pairs=pairs,
                custom_values_override=cv_map,
                include_workflow_steps=bool(args.include_workflow_steps),
                workflow_from_name=args.workflow_from_name,
                workflow_from_email=args.workflow_from_email,
                workflow_pixel_id=args.workflow_pixel_id,
                workflow_capi_token=args.workflow_capi_token,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_location_rebrand_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "agency-workflow-xray":
            terms = (
                [x.strip() for x in args.brand_terms.split(",") if x.strip()]
                if args.brand_terms
                else None
            )
            return inspect_agency_workflows_xray(
                backend,
                location_id=args.location_id,
                workflow_id=args.workflow_id,
                brand_terms=terms,
            )
        if args.command == "workflow-steps-rebrand":
            pairs = _parse_replace_pairs(args.replace_from, args.replace_to)
            wf_ids = (
                [x.strip() for x in args.workflow_ids.split(",") if x.strip()]
                if args.workflow_ids
                else None
            )
            plan = make_workflow_steps_rebrand_plan(
                backend,
                location_id=args.location_id,
                workflow_ids=wf_ids,
                replace_pairs=pairs,
                from_name=args.from_name,
                from_email=args.from_email,
                pixel_id=args.pixel_id,
                capi_access_token=args.capi_access_token,
                templatize_senders=bool(args.templatize_senders),
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_workflow_steps_rebrand_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )
        if args.command == "snapshot-share-link":
            plan = make_snapshot_share_link_plan(
                backend,
                snapshot_id=args.snapshot_id,
                share_type=args.share_type,
                company_id=args.company_id,
                relationship_number=args.relationship_number,
                share_location_id=args.share_location_id,
            )
            if not args.apply:
                return {"mode": "preview", "plan": plan, "writes_sent": 0}
            return apply_snapshot_share_link_plan(
                backend,
                plan,
                confirm_plan=args.confirm_plan,
            )

    if args.command in {
        "custom-value-upsert",
        "custom-value-delete",
        "custom-field-upsert",
        "custom-field-delete",
        "trigger-link-upsert",
        "trigger-link-delete",
        "calendar-update",
        "appointment-create",
        "conversation-send",
        "subaccount-update",
        "subaccount-rebrand",
        "workflow-status",
        "tag-upsert",
        "tag-delete",
        "contact-upsert",
        "contact-tag",
        "contact-note",
        "contact-task-upsert",
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
    if args.command == "subaccount-rebrand-audit":
        terms = (
            [x.strip() for x in args.brand_terms.split(",") if x.strip()]
            if args.brand_terms
            else None
        )
        return subaccount_rebrand_audit(client, brand_terms=terms)
    if args.command == "subaccount-update":
        su_plan = make_subaccount_update_plan(
            client,
            name=args.name,
            email=args.email,
            phone=args.phone,
            website=args.website,
            address=args.address,
            city=args.city,
            state=args.state,
            postal_code=args.postal_code,
            country=args.country,
            timezone=args.timezone,
            logo_url=args.logo_url,
        )
        if not args.apply:
            return {"mode": "preview", "plan": su_plan, "writes_sent": 0}
        return apply_subaccount_update_plan(
            client,
            su_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command == "subaccount-rebrand":
        pairs = _parse_replace_pairs(args.replace_from, args.replace_to)
        cv_map = json.loads(args.custom_values_json) if args.custom_values_json else None
        if cv_map is not None and not isinstance(cv_map, dict):
            raise HighLevelError("--custom-values-json must be a JSON object.")
        sr_plan = make_subaccount_rebrand_plan(
            client,
            name=args.name,
            email=args.email,
            phone=args.phone,
            website=args.website,
            address=args.address,
            city=args.city,
            state=args.state,
            postal_code=args.postal_code,
            country=args.country,
            timezone=args.timezone,
            logo_url=args.logo_url,
            replace_pairs=pairs,
            custom_values_override=cv_map,
        )
        if not args.apply:
            return {"mode": "preview", "plan": sr_plan, "writes_sent": 0}
        return apply_subaccount_rebrand_plan(
            client,
            sr_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command in {"custom-field-upsert", "custom-field-delete"}:
        cf_action = "delete" if args.command == "custom-field-delete" else "upsert"
        opts = [x.strip() for x in args.options.split(",") if x.strip()] if getattr(args, "options", None) else None
        cf_plan = make_custom_field_plan(
            client,
            action=cf_action,
            name=args.name,
            data_type=getattr(args, "data_type", "TEXT"),
            model=getattr(args, "model", "contact"),
            placeholder=getattr(args, "placeholder", None),
            options=opts,
            custom_field_id=getattr(args, "custom_field_id", None),
        )
        if not args.apply:
            return {"mode": "preview", "plan": cf_plan, "writes_sent": 0}
        return apply_custom_field_plan(
            client,
            cf_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command in {"trigger-link-upsert", "trigger-link-delete"}:
        tl_action = "delete" if args.command == "trigger-link-delete" else "upsert"
        tl_plan = make_trigger_link_plan(
            client,
            action=tl_action,
            name=args.name,
            redirect_to=getattr(args, "redirect_to", None),
            link_id=getattr(args, "link_id", None),
        )
        if not args.apply:
            return {"mode": "preview", "plan": tl_plan, "writes_sent": 0}
        return apply_trigger_link_plan(
            client,
            tl_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command == "calendar-update":
        if args.active and args.inactive:
            raise HighLevelError("Pass either --active or --inactive, not both.")
        is_act = True if args.active else (False if args.inactive else None)
        cal_plan = make_calendar_update_plan(
            client,
            calendar_id=args.calendar_id,
            name=args.name,
            slug=args.slug,
            description=args.description,
            is_active=is_act,
        )
        if not args.apply:
            return {"mode": "preview", "plan": cal_plan, "writes_sent": 0}
        return apply_calendar_update_plan(
            client,
            cal_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command == "conversation-messages":
        return list_conversation_messages(
            client,
            conversation_id=args.conversation_id,
            limit=args.limit,
        )
    if args.command == "conversation-send":
        cs_plan = make_conversation_send_plan(
            client,
            contact_id=args.contact_id,
            message_type=args.type,
            message=args.message,
            subject=args.subject,
            html=args.html,
        )
        if not args.apply:
            return {"mode": "preview", "plan": cs_plan, "writes_sent": 0}
        return apply_conversation_send_plan(
            client,
            cs_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command == "email-templates":
        return list_email_templates(client, limit=args.limit)
    if args.command == "trigger-links":
        return list_trigger_links(client)
    if args.command == "subaccount-users":
        return list_subaccount_users(client)
    if args.command == "contact-notes":
        return list_contact_notes(client, contact_id=args.contact_id)
    if args.command == "contact-tasks":
        return list_contact_tasks(client, contact_id=args.contact_id)
    if args.command == "contact-task-upsert":
        ctk_plan = make_contact_task_plan(
            client,
            contact_id=args.contact_id,
            title=args.title,
            body=args.body,
            due_date=args.due_date,
            completed=bool(args.completed),
            assigned_to=args.assigned_to,
            task_id=args.task_id,
        )
        if not args.apply:
            return {"mode": "preview", "plan": ctk_plan, "writes_sent": 0}
        return apply_contact_task_plan(
            client,
            ctk_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command == "calendar-events":
        return list_calendar_events(
            client,
            calendar_id=args.calendar_id,
            user_id=args.user_id,
            group_id=args.group_id,
            start_time=args.start_time,
            end_time=args.end_time,
        )
    if args.command == "appointment-create":
        ap_plan = make_appointment_create_plan(
            client,
            calendar_id=args.calendar_id,
            contact_id=args.contact_id,
            start_time=args.start_time,
            end_time=args.end_time,
            title=args.title,
            appointment_status=args.status,
            assigned_user_id=args.assigned_user_id,
            address=args.address,
        )
        if not args.apply:
            return {"mode": "preview", "plan": ap_plan, "writes_sent": 0}
        return apply_appointment_create_plan(
            client,
            ap_plan,
            confirm_location=args.confirm_location,
            confirm_plan=args.confirm_plan,
        )
    if args.command == "medias":
        return list_media_files(client, limit=args.limit, query_str=args.query)
    if args.command == "products":
        return list_products(client, limit=args.limit)
    if args.command == "invoices":
        return list_invoices(client, limit=args.limit, offset=args.offset)
    if args.command == "transactions":
        return list_transactions(client, limit=args.limit, offset=args.offset)
    if args.command == "blogs":
        return list_blogs(client, limit=args.limit, skip=args.skip)
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
