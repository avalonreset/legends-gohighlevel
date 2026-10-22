"""Sub-account CRM inspection and preview-first mutations with SHA-256 plan confirmation."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .api import Client, HighLevelError, valid_id

CORE_LANES = (
    ("location", "locations.readonly", lambda loc: (f"/locations/{loc}", None)),
    ("contacts", "contacts.readonly", lambda loc: ("/contacts/", {"locationId": loc, "limit": 1})),
    ("pipelines", "opportunities.readonly", lambda loc: ("/opportunities/pipelines", {"locationId": loc})),
    ("calendars", "calendars.readonly", lambda loc: ("/calendars/", {"locationId": loc})),
    ("conversations", "conversations.readonly", lambda loc: ("/conversations/search", {"locationId": loc, "limit": 1})),
    ("custom_values", "locations/customValues.readonly", lambda loc: (f"/locations/{loc}/customValues", None)),
    ("workflows", "workflows.readonly", lambda loc: ("/workflows/", {"locationId": loc})),
    ("forms", "forms.readonly", lambda loc: ("/forms/", {"locationId": loc, "limit": 1})),
)


def plan_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def probe_live_lanes(client: Client) -> dict[str, Any]:
    loc = client.location_id
    lanes = []
    passed = 0
    for name, scope, builder in CORE_LANES:
        path, query = builder(loc)
        try:
            client.request("GET", path, query=query)
            lanes.append({"lane": name, "scope_hint": scope, "ok": True})
            passed += 1
        except HighLevelError as exc:
            lanes.append({"lane": name, "scope_hint": scope, "ok": False, "error": str(exc)})
    return {
        "ok": passed >= 4,
        "mode": "live",
        "auth_kind": client.auth_kind,
        "location_id": loc,
        "lanes_passed": passed,
        "lanes_total": len(CORE_LANES),
        "lanes": lanes,
        "rate_limits": client.last_rate_limits,
    }


def location_snapshot(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", f"/locations/{loc}")
    raw = res.get("location", res)
    if not isinstance(raw, dict):
        raise HighLevelError("Invalid location response.")
    keep = ("id", "name", "companyId", "timezone", "country", "state", "city", "postalCode", "website", "settings")
    return {
        "location": {k: raw[k] for k in keep if k in raw},
        "rate_limits": client.last_rate_limits,
    }


def list_custom_values(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", f"/locations/{loc}/customValues")
    items = res.get("customValues", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected customValues list.")
    cleaned = [
        {
            "id": str(item.get("id", "")),
            "name": str(item.get("name", "")),
            "fieldKey": str(item.get("fieldKey", "")),
            "value": item.get("value"),
        }
        for item in items
        if isinstance(item, dict)
    ]
    return {"location_id": loc, "count": len(cleaned), "custom_values": cleaned, "rate_limits": client.last_rate_limits}


def list_custom_fields(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", f"/locations/{loc}/customFields")
    items = res.get("customFields", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected customFields list.")
    cleaned = [
        {
            "id": str(item.get("id", "")),
            "name": str(item.get("name", "")),
            "fieldKey": str(item.get("fieldKey", "")),
            "dataType": str(item.get("dataType", "")),
        }
        for item in items
        if isinstance(item, dict)
    ]
    return {"location_id": loc, "count": len(cleaned), "custom_fields": cleaned, "rate_limits": client.last_rate_limits}


def list_pipelines(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/opportunities/pipelines", query={"locationId": loc})
    items = res.get("pipelines", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected pipelines list.")
    pipelines = []
    for p in items:
        if not isinstance(p, dict):
            continue
        stages = [
            {"id": str(s.get("id", "")), "name": str(s.get("name", "")), "position": s.get("position")}
            for s in (p.get("stages") or [])
            if isinstance(s, dict)
        ]
        pipelines.append({"id": str(p.get("id", "")), "name": str(p.get("name", "")), "stages": stages})
    return {"location_id": loc, "count": len(pipelines), "pipelines": pipelines, "rate_limits": client.last_rate_limits}


def list_calendars(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/calendars/", query={"locationId": loc})
    items = res.get("calendars", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected calendars list.")
    cals = [
        {
            "id": str(c.get("id", "")),
            "name": str(c.get("name", "")),
            "calendarType": c.get("calendarType"),
            "isActive": c.get("isActive"),
        }
        for c in items
        if isinstance(c, dict)
    ]
    return {"location_id": loc, "count": len(cals), "calendars": cals, "rate_limits": client.last_rate_limits}


def list_workflows(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/workflows/", query={"locationId": loc})
    items = res.get("workflows", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected workflows list.")
    workflows = [
        {
            "id": str(w.get("id", "")),
            "name": str(w.get("name", "")),
            "status": w.get("status"),
            "version": w.get("version"),
        }
        for w in items
        if isinstance(w, dict)
    ]
    return {"location_id": loc, "count": len(workflows), "workflows": workflows, "rate_limits": client.last_rate_limits}


def list_forms(client: Client, limit: int = 50) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/forms/", query={"locationId": loc, "limit": max(1, min(limit, 100))})
    items = res.get("forms", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected forms list.")
    forms = [{"id": str(f.get("id", "")), "name": str(f.get("name", "")), "type": f.get("type")} for f in items if isinstance(f, dict)]
    return {"location_id": loc, "count": len(forms), "forms": forms, "rate_limits": client.last_rate_limits}


def list_surveys(client: Client, limit: int = 50) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/surveys/", query={"locationId": loc, "limit": max(1, min(limit, 100))})
    items = res.get("surveys", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected surveys list.")
    surveys = [{"id": str(s.get("id", "")), "name": str(s.get("name", "")), "type": s.get("type")} for s in items if isinstance(s, dict)]
    return {"location_id": loc, "count": len(surveys), "surveys": surveys, "rate_limits": client.last_rate_limits}


def search_contacts(client: Client, query: str | None = None, limit: int = 20, full: bool = False) -> dict[str, Any]:
    loc = client.location_id
    q: dict[str, Any] = {"locationId": loc, "limit": max(1, min(limit, 100))}
    if query:
        q["query"] = query.strip()
    res = client.request("GET", "/contacts/", query=q)
    items = res.get("contacts", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected contacts list.")
    contacts = []
    for c in items:
        if not isinstance(c, dict):
            continue
        entry: dict[str, Any] = {
            "id": str(c.get("id", "")),
            "type": c.get("type"),
            "tags": c.get("tags") or [],
            "dateAdded": c.get("dateAdded"),
        }
        if full:
            for k in ("contactName", "firstName", "lastName", "email", "phone", "companyName"):
                if k in c:
                    entry[k] = c[k]
        contacts.append(entry)
    return {
        "location_id": loc,
        "pii_mode": "full" if full else "lean",
        "count": len(contacts),
        "contacts": contacts,
        "rate_limits": client.last_rate_limits,
    }


def search_opportunities(
    client: Client,
    pipeline_id: str | None = None,
    stage_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    loc = client.location_id
    q: dict[str, Any] = {"location_id": loc, "limit": max(1, min(limit, 100))}
    if pipeline_id:
        q["pipeline_id"] = valid_id(pipeline_id)
    if stage_id:
        q["pipeline_stage_id"] = valid_id(stage_id)
    if status:
        q["status"] = status.strip()
    res = client.request("GET", "/opportunities/search", query=q)
    items = res.get("opportunities", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected opportunities list.")
    opps = [
        {
            "id": str(o.get("id", "")),
            "name": str(o.get("name", "")),
            "pipelineId": o.get("pipelineId"),
            "pipelineStageId": o.get("pipelineStageId"),
            "status": o.get("status"),
            "monetaryValue": o.get("monetaryValue"),
            "contactId": o.get("contactId"),
        }
        for o in items
        if isinstance(o, dict)
    ]
    return {"location_id": loc, "count": len(opps), "opportunities": opps, "rate_limits": client.last_rate_limits}


def triage_conversations(client: Client, limit: int = 20) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/conversations/search", query={"locationId": loc, "limit": max(1, min(limit, 100))})
    items = res.get("conversations", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected conversations list.")
    convs = [
        {
            "id": str(c.get("id", "")),
            "contactId": c.get("contactId"),
            "type": c.get("type"),
            "unreadCount": c.get("unreadCount"),
            "lastMessageType": c.get("lastMessageType"),
            "lastMessageDirection": c.get("lastMessageDirection"),
            "lastMessageDate": c.get("lastMessageDate"),
        }
        for c in items
        if isinstance(c, dict)
    ]
    return {
        "location_id": loc,
        "pii_mode": "lean",
        "count": len(convs),
        "conversations": convs,
        "rate_limits": client.last_rate_limits,
    }


def make_custom_value_plan(
    client: Client,
    *,
    name: str,
    value: str | None = None,
    custom_value_id: str | None = None,
    delete: bool = False,
) -> dict[str, Any]:
    clean_name = (name or "").strip()
    if not clean_name or len(clean_name) > 120:
        raise HighLevelError("Custom value name is required (1..120 characters).")
    if not delete and value is None:
        raise HighLevelError("Custom value content (--value) is required for upsert.")

    loc = client.location_id
    inventory = list_custom_values(client)["custom_values"]
    if custom_value_id:
        cid = valid_id(custom_value_id)
        matches = [item for item in inventory if item["id"] == cid]
        if len(matches) != 1:
            raise HighLevelError(f"Custom value ID '{cid}' was not found in location '{loc}'.")
        before = matches[0]
        if before["name"].strip().lower() != clean_name.lower() and delete:
            raise HighLevelError("Custom value name does not match the specified --custom-value-id.")
    else:
        if delete:
            raise HighLevelError("Deleting a custom value requires an explicit --custom-value-id.")
        matches = [item for item in inventory if item["name"].strip().lower() == clean_name.lower()]
        if len(matches) > 1:
            raise HighLevelError("Multiple custom values share that name; pass --custom-value-id explicitly.")
        before = matches[0] if matches else None

    action = "delete" if delete else ("update" if before else "create")
    proposed = None if delete else {"name": clean_name, "value": str(value)}
    plan_core = {
        "resource": "custom_value",
        "action": action,
        "location_id": loc,
        "custom_value_id": before["id"] if before else None,
        "before": before,
        "proposed": proposed,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_custom_value_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    loc = client.location_id
    if confirm_location != loc:
        raise HighLevelError("--confirm-location does not match the active GHL_LOCATION_ID.")
    if confirm_plan != plan["sha256"]:
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    action = plan["action"]
    if action == "create":
        created = client.request("POST", f"/locations/{loc}/customValues", body=plan["proposed"])
        cv = created.get("customValue", created)
        new_id = valid_id(str(cv.get("id", "")))
        after_list = list_custom_values(client)["custom_values"]
        readback = next((item for item in after_list if item["id"] == new_id), None)
        verified = bool(
            readback
            and readback["name"] == plan["proposed"]["name"]
            and str(readback.get("value", "")) == plan["proposed"]["value"]
        )
        if not verified:
            raise HighLevelError("Custom value creation readback did not match the requested payload.")
        return {
            "mode": "applied",
            "action": "create",
            "location_id": loc,
            "custom_value_id": new_id,
            "verified": True,
            "readback": readback,
        }

    cid = valid_id(str(plan["custom_value_id"]))
    if action == "update":
        client.request("PUT", f"/locations/{loc}/customValues/{cid}", body=plan["proposed"])
        after_list = list_custom_values(client)["custom_values"]
        readback = next((item for item in after_list if item["id"] == cid), None)
        verified = bool(
            readback
            and readback["name"] == plan["proposed"]["name"]
            and str(readback.get("value", "")) == plan["proposed"]["value"]
        )
        if not verified:
            raise HighLevelError("Custom value update readback did not match the requested payload.")
        return {
            "mode": "applied",
            "action": "update",
            "location_id": loc,
            "custom_value_id": cid,
            "verified": True,
            "readback": readback,
        }

    if action == "delete":
        client.request("DELETE", f"/locations/{loc}/customValues/{cid}")
        after_list = list_custom_values(client)["custom_values"]
        still_present = any(item["id"] == cid for item in after_list)
        if still_present:
            raise HighLevelError("Custom value deletion readback failed; record is still present.")
        return {
            "mode": "applied",
            "action": "delete",
            "location_id": loc,
            "custom_value_id": cid,
            "verified": True,
        }

    raise HighLevelError("Unsupported plan action.")
