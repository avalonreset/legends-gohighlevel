"""JSON CLI with offline doctor, sub-account CRM operations, preview-first mutations, and governance audits."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from . import __version__
from .api import Client, HighLevelError
from .crm import (
    apply_custom_value_plan,
    list_calendars,
    list_custom_fields,
    list_custom_values,
    list_forms,
    list_pipelines,
    list_surveys,
    list_workflows,
    location_snapshot,
    make_custom_value_plan,
    probe_live_lanes,
    search_contacts,
    search_opportunities,
    triage_conversations,
)
from .governance import rebilling_audit, scope_audit, smtp_audit


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_resources() -> dict:
    root = _repo_root()
    candidates = {
        "agent_recipe": root / "docs" / "AGENT-RECIPE.md",
        "wiki_index": root / "wiki" / "index.md",
        "knowledge_pack": root / "knowledge" / "gohighlevel" / "pack.json",
        "sources": root / "references" / "sources.md",
    }
    return {
        "module": "legends-gohighlevel",
        "version": __version__,
        "paths": {k: str(v) for k, v in candidates.items() if v.exists()},
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Offline runtime check; --live probes sub-account API v2 lanes.")
    doctor.add_argument("--live", action="store_true")

    sub.add_parser("resources", help="Show local recipe, wiki, and knowledge-pack paths.")
    sub.add_parser("location", help="Get sub-account metadata for GHL_LOCATION_ID.")
    sub.add_parser("custom-values", help="List sub-account custom values.")
    sub.add_parser("custom-fields", help="List sub-account custom fields.")
    sub.add_parser("pipelines", help="List sub-account pipelines and stages.")
    sub.add_parser("calendars", help="List sub-account calendars.")
    sub.add_parser("workflows", help="List sub-account workflows.")

    forms = sub.add_parser("forms", help="List sub-account forms.")
    forms.add_argument("--limit", type=int, default=50)

    surveys = sub.add_parser("surveys", help="List sub-account surveys.")
    surveys.add_argument("--limit", type=int, default=50)

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

    return p


def execute(args, client_factory=Client) -> dict:
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

    if args.command in {"custom-value-upsert", "custom-value-delete"}:
        confirmations = bool(args.confirm_location or args.confirm_plan)
        if args.apply and not (args.confirm_location and args.confirm_plan):
            raise HighLevelError("--apply requires --confirm-location and --confirm-plan.")
        if confirmations and not args.apply:
            raise HighLevelError("Confirmation flags require --apply.")

    client = client_factory()
    if args.command == "doctor":
        return probe_live_lanes(client)
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
    if args.command == "workflows":
        return list_workflows(client)
    if args.command == "forms":
        return list_forms(client, limit=args.limit)
    if args.command == "surveys":
        return list_surveys(client, limit=args.limit)
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
