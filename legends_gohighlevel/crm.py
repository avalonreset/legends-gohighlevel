"""Sub-account CRM inspection and preview-first mutations with SHA-256 plan confirmation."""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from .api import API_VERSION_V3, Client, HighLevelError, load_subaccount_config, valid_id, valid_object_key

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
    keep = (
        "id",
        "name",
        "companyId",
        "email",
        "phone",
        "address",
        "timezone",
        "country",
        "state",
        "city",
        "postalCode",
        "website",
        "logoUrl",
        "domain",
        "settings",
    )
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


def list_tags(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", f"/locations/{loc}/tags")
    items = res.get("tags", [])
    if not isinstance(items, list):
        raise HighLevelError("Expected tags list.")
    tags = [
        {
            "id": str(t.get("id", "")),
            "name": str(t.get("name", "")),
        }
        for t in items
        if isinstance(t, dict)
    ]
    return {"location_id": loc, "count": len(tags), "tags": tags, "rate_limits": client.last_rate_limits}


def list_funnels(client: Client, limit: int = 50, include_redirects: bool = False) -> dict[str, Any]:
    loc = client.location_id
    bounded = max(1, min(int(limit), 100))
    res = client.request("GET", "/funnels/funnel/list", query={"locationId": loc, "limit": bounded})
    raw_funnels = res.get("funnels", [])
    if not isinstance(raw_funnels, list):
        raise HighLevelError("Expected funnels list.")
    funnels = [
        {
            "id": str(f.get("_id") or f.get("id") or ""),
            "name": str(f.get("name") or ""),
            "type": f.get("type"),
            "domainId": f.get("domainId"),
            "step_count": len(f.get("steps") or []) if isinstance(f.get("steps"), list) else None,
        }
        for f in raw_funnels
        if isinstance(f, dict)
    ]
    out: dict[str, Any] = {
        "location_id": loc,
        "count": len(funnels),
        "funnels": funnels,
        "rate_limits": client.last_rate_limits,
    }
    if include_redirects:
        red_res = client.request(
            "GET",
            "/funnels/lookup/redirect/list",
            query={"locationId": loc, "limit": min(bounded, 20), "offset": 0},
        )
        raw_red = red_res.get("data", [])
        out["redirects"] = [
            {
                "id": str(r.get("id") or r.get("_id") or ""),
                "domain": r.get("domain"),
                "path": r.get("path"),
                "target": r.get("target"),
                "action": r.get("action"),
            }
            for r in (raw_red if isinstance(raw_red, list) else [])
            if isinstance(r, dict)
        ]
    return out


def list_objects(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/objects/", query={"locationId": loc})
    raw_objs = res.get("objects", [])
    if not isinstance(raw_objs, list):
        raise HighLevelError("Expected objects list.")
    objects = [
        {
            "id": str(o.get("id") or ""),
            "key": o.get("key"),
            "labels": o.get("labels"),
            "primaryDisplayProperty": o.get("primaryDisplayProperty"),
            "standard": bool(o.get("standard", False)),
        }
        for o in raw_objs
        if isinstance(o, dict)
    ]
    return {"location_id": loc, "count": len(objects), "objects": objects, "rate_limits": client.last_rate_limits}


def search_object_records(
    client: Client,
    *,
    object_key: str,
    query: str = "",
    page: int = 1,
    page_limit: int = 20,
) -> dict[str, Any]:
    loc = client.location_id
    clean_key = valid_object_key(object_key)
    body: dict[str, Any] = {
        "locationId": loc,
        "page": max(1, int(page)),
        "pageLimit": max(1, min(int(page_limit), 100)),
    }
    if query.strip():
        body["query"] = query.strip()
    res = client.request("POST", f"/objects/{clean_key}/records/search", body=body)
    raw_records = res.get("records") or res.get("customObjectRecords") or res.get("data") or []
    records = [
        {
            "id": str(r.get("id") or ""),
            "objectKey": r.get("objectKey") or clean_key,
            "properties": r.get("properties") or {},
            "createdAt": r.get("createdAt"),
            "updatedAt": r.get("updatedAt"),
        }
        for r in (raw_records if isinstance(raw_records, list) else [])
        if isinstance(r, dict)
    ]
    return {
        "location_id": loc,
        "object_key": clean_key,
        "count": len(records),
        "total": res.get("total", len(records)),
        "records": records,
        "rate_limits": client.last_rate_limits,
    }


def list_associations(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/associations/", query={"locationId": loc})
    raw_assocs = res.get("associations", [])
    if not isinstance(raw_assocs, list):
        raise HighLevelError("Expected associations list.")
    associations = [
        {
            "id": str(a.get("id") or ""),
            "key": a.get("key"),
            "associationType": a.get("associationType"),
            "firstObjectKey": a.get("firstObjectKey"),
            "firstObjectLabel": a.get("firstObjectLabel"),
            "secondObjectKey": a.get("secondObjectKey"),
            "secondObjectLabel": a.get("secondObjectLabel"),
        }
        for a in raw_assocs
        if isinstance(a, dict)
    ]
    return {
        "location_id": loc,
        "count": len(associations),
        "associations": associations,
        "rate_limits": client.last_rate_limits,
    }


def list_voice_ai_agents(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/voice-ai/agents", query={"locationId": loc})
    raw_agents = res.get("agents", [])
    if not isinstance(raw_agents, list):
        raise HighLevelError("Expected voice AI agents list.")
    agents = [
        {
            "id": str(a.get("id") or a.get("_id") or ""),
            "name": a.get("name") or a.get("agentName"),
            "status": a.get("status"),
            "voiceId": a.get("voiceId"),
            "phoneNumbers": a.get("phoneNumbers") or [],
        }
        for a in raw_agents
        if isinstance(a, dict)
    ]
    return {
        "location_id": loc,
        "count": len(agents),
        "total": res.get("total", len(agents)),
        "agents": agents,
        "rate_limits": client.last_rate_limits,
    }


def list_voice_ai_calls(client: Client, limit: int = 20) -> dict[str, Any]:
    loc = client.location_id
    bounded = max(1, min(int(limit), 100))
    res = client.request(
        "GET",
        "/voice-ai/dashboard/call-logs",
        query={"locationId": loc, "pageSize": bounded, "page": 1},
    )
    raw_logs = res.get("callLogs", [])
    if not isinstance(raw_logs, list):
        raise HighLevelError("Expected callLogs list.")
    calls = [
        {
            "id": str(c.get("id") or c.get("_id") or ""),
            "agentId": c.get("agentId"),
            "contactId": c.get("contactId"),
            "status": c.get("status"),
            "durationSeconds": c.get("duration") or c.get("durationSeconds"),
            "createdAt": c.get("createdAt"),
        }
        for c in raw_logs
        if isinstance(c, dict)
    ]
    return {
        "location_id": loc,
        "pii_mode": "lean",
        "count": len(calls),
        "total": res.get("totalRecords", len(calls)),
        "call_logs": calls,
        "rate_limits": client.last_rate_limits,
    }


def list_conversation_ai_agents(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/conversation-ai/agents/search")
    raw_agents = res.get("agents", [])
    if not isinstance(raw_agents, list):
        raise HighLevelError("Expected conversation AI agents list.")
    agents = [
        {
            "id": str(a.get("id") or a.get("_id") or ""),
            "name": a.get("name"),
            "status": a.get("status"),
            "mode": a.get("mode"),
            "channels": a.get("channels") or [],
        }
        for a in raw_agents
        if isinstance(a, dict)
    ]
    return {
        "location_id": loc,
        "count": len(agents),
        "total": res.get("totalCount", len(agents)),
        "agents": agents,
        "rate_limits": client.last_rate_limits,
    }


def list_workflow_step_types(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request(
        "GET",
        "/workflows/step-types",
        query={"locationId": loc},
        version=API_VERSION_V3,
    )
    return {
        "location_id": loc,
        "api_version": API_VERSION_V3,
        "step_types": res.get("stepTypes") or res.get("data") or res,
        "rate_limits": client.last_rate_limits,
    }


def inspect_workflow_definition(client: Client, *, workflow_id: str) -> dict[str, Any]:
    loc = client.location_id
    wid = valid_id(workflow_id)
    res = client.request(
        "GET",
        f"/workflows/{wid}/definition",
        query={"locationId": loc},
        version=API_VERSION_V3,
    )
    return {
        "location_id": loc,
        "workflow_id": wid,
        "api_version": API_VERSION_V3,
        "definition": res.get("definition") or res.get("workflow") or res,
        "rate_limits": client.last_rate_limits,
    }


def list_workflow_logs(client: Client, *, workflow_id: str, limit: int = 25) -> dict[str, Any]:
    loc = client.location_id
    wid = valid_id(workflow_id)
    bounded = max(1, min(int(limit), 100))
    res = client.request(
        "GET",
        f"/workflows/{wid}/logs",
        query={"locationId": loc, "limit": bounded},
        version=API_VERSION_V3,
    )
    return {
        "location_id": loc,
        "workflow_id": wid,
        "api_version": API_VERSION_V3,
        "logs": res.get("logs") or res.get("data") or [],
        "rate_limits": client.last_rate_limits,
    }


def validate_workflow_definition(client: Client, *, definition: dict[str, Any]) -> dict[str, Any]:
    loc = client.location_id
    payload = dict(definition)
    payload.setdefault("locationId", loc)
    res = client.request(
        "POST",
        "/workflows/definition/validate",
        body=payload,
        version=API_VERSION_V3,
    )
    return {
        "location_id": loc,
        "api_version": API_VERSION_V3,
        "validation": res,
        "rate_limits": client.last_rate_limits,
    }


def make_workflow_status_plan(
    client: Client,
    *,
    workflow_id: str,
    status: str,
) -> dict[str, Any]:
    loc = client.location_id
    wid = valid_id(workflow_id)
    clean_status = (status or "").strip().lower()
    if clean_status not in {"published", "draft"}:
        raise HighLevelError("Workflow status must be 'published' or 'draft'.")
    inventory = list_workflows(client)["workflows"]
    before = next((w for w in inventory if w["id"] == wid), None)
    proposed = {"locationId": loc, "status": clean_status}
    plan_core = {
        "resource": "workflow_status",
        "action": "update_status",
        "location_id": loc,
        "workflow_id": wid,
        "before": before,
        "proposed": proposed,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_workflow_status_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    loc = client.location_id
    if confirm_location != loc:
        raise HighLevelError("--confirm-location does not match the active GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    wid = valid_id(str(plan["workflow_id"]))
    res = client.request(
        "PUT",
        f"/workflows/{wid}/status",
        body=plan["proposed"],
        version=API_VERSION_V3,
    )
    return {
        "mode": "applied",
        "action": "update_status",
        "location_id": loc,
        "workflow_id": wid,
        "status": plan["proposed"]["status"],
        "response": res,
        "verified": True,
    }


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


def list_calendar_free_slots(
    client: Client,
    *,
    calendar_id: str,
    start_date: int | str,
    end_date: int | str,
    timezone: str | None = None,
) -> dict[str, Any]:
    cid = valid_id(calendar_id)
    query: dict[str, Any] = {
        "startDate": str(start_date).strip(),
        "endDate": str(end_date).strip(),
    }
    if timezone and timezone.strip():
        query["timezone"] = timezone.strip()
    res = client.request("GET", f"/calendars/{cid}/free-slots", query=query)
    slots_by_date = {
        k: v for k, v in res.items() if k != "traceId"
    }
    return {
        "location_id": client.location_id,
        "calendar_id": cid,
        "slots": slots_by_date,
        "rate_limits": client.last_rate_limits,
    }


def make_tag_plan(
    client: Client,
    *,
    name: str,
    tag_id: str | None = None,
    delete: bool = False,
) -> dict[str, Any]:
    loc = client.location_id
    clean_name = (name or "").strip()
    if not clean_name:
        raise HighLevelError("Tag name must not be empty.")
    inventory = list_tags(client)["tags"]
    matched = None
    if tag_id:
        tid = valid_id(tag_id)
        for item in inventory:
            if item["id"] == tid:
                matched = item
                break
        if matched is None:
            raise HighLevelError("Specified tag_id was not found in this location.")
    else:
        for item in inventory:
            if item["name"].strip().lower() == clean_name.lower():
                matched = item
                break

    if delete:
        if matched is None or not tag_id:
            raise HighLevelError("Tag delete requires --tag-id of an existing tag.")
        plan_core = {
            "resource": "tag",
            "action": "delete",
            "location_id": loc,
            "tag_id": matched["id"],
            "before": matched,
            "proposed": None,
        }
    else:
        plan_core = {
            "resource": "tag",
            "action": "noop" if matched is not None else "create",
            "location_id": loc,
            "tag_id": matched["id"] if matched else None,
            "before": matched,
            "proposed": {"name": clean_name},
        }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_tag_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    loc = client.location_id
    if confirm_location != loc:
        raise HighLevelError("--confirm-location does not match GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    action = plan["action"]
    if action == "noop":
        return {
            "mode": "applied",
            "action": "noop",
            "location_id": loc,
            "tag_id": plan["tag_id"],
            "verified": True,
            "readback": plan["before"],
        }
    if action == "create":
        res = client.request("POST", f"/locations/{loc}/tags", body=plan["proposed"])
        tag_obj = res.get("tag", res)
        new_id = valid_id(str(tag_obj.get("id", "")))
        rb_res = client.request("GET", f"/locations/{loc}/tags/{new_id}")
        rb_tag = rb_res.get("tag", rb_res) if isinstance(rb_res, dict) else {}
        if not rb_tag.get("id"):
            after = list_tags(client)["tags"]
            rb_tag = next((t for t in after if t["id"] == new_id), None) or {}
        if str(rb_tag.get("name", "")).lower() != plan["proposed"]["name"].lower():
            raise HighLevelError("Tag creation readback did not match the requested payload.")
        return {
            "mode": "applied",
            "action": "create",
            "location_id": loc,
            "tag_id": new_id,
            "verified": True,
            "readback": {"id": new_id, "name": rb_tag.get("name")},
        }
    if action == "delete":
        tid = valid_id(str(plan["tag_id"]))
        client.request("DELETE", f"/locations/{loc}/tags/{tid}")
        return {
            "mode": "applied",
            "action": "delete",
            "location_id": loc,
            "tag_id": tid,
            "verified": True,
        }
    raise HighLevelError("Unsupported tag plan action.")


def make_contact_upsert_plan(
    client: Client,
    *,
    email: str | None = None,
    phone: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    name: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    clean_email = (email or "").strip()
    clean_phone = (phone or "").strip()
    if not clean_email and not clean_phone:
        raise HighLevelError("contact-upsert requires at least --email or --phone.")
    payload: dict[str, Any] = {"locationId": loc}
    if clean_email:
        payload["email"] = clean_email
    if clean_phone:
        payload["phone"] = clean_phone
    if first_name and first_name.strip():
        payload["firstName"] = first_name.strip()
    if last_name and last_name.strip():
        payload["lastName"] = last_name.strip()
    if name and name.strip():
        payload["name"] = name.strip()
    if tags:
        payload["tags"] = [t.strip() for t in tags if t.strip()]
    plan_core = {
        "resource": "contact",
        "action": "upsert",
        "location_id": loc,
        "proposed": payload,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_contact_upsert_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    loc = client.location_id
    if confirm_location != loc:
        raise HighLevelError("--confirm-location does not match GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    res = client.request("POST", "/contacts/upsert", body=plan["proposed"])
    c_obj = res.get("contact", res)
    cid = valid_id(str(c_obj.get("id", "")))
    readback_res = client.request("GET", f"/contacts/{cid}")
    rb_contact = readback_res.get("contact", readback_res)
    if str(rb_contact.get("id", "")) != cid:
        raise HighLevelError("Contact upsert readback failed.")
    return {
        "mode": "applied",
        "action": "upsert",
        "location_id": loc,
        "contact_id": cid,
        "new": res.get("new"),
        "verified": True,
        "readback": {
            "id": cid,
            "tags": rb_contact.get("tags") or [],
            "dateUpdated": rb_contact.get("dateUpdated"),
        },
    }


def make_contact_tag_plan(
    client: Client,
    *,
    contact_id: str,
    tags: list[str],
    remove: bool = False,
) -> dict[str, Any]:
    loc = client.location_id
    cid = valid_id(contact_id)
    clean_tags = [t.strip() for t in (tags or []) if t.strip()]
    if not clean_tags:
        raise HighLevelError("Provide at least one tag via --tags.")
    before_res = client.request("GET", f"/contacts/{cid}")
    before_contact = before_res.get("contact", before_res)
    before_tags = list(before_contact.get("tags") or [])
    plan_core = {
        "resource": "contact_tags",
        "action": "remove_tags" if remove else "add_tags",
        "location_id": loc,
        "contact_id": cid,
        "before_tags": before_tags,
        "proposed": {"tags": clean_tags},
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_contact_tag_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    loc = client.location_id
    if confirm_location != loc:
        raise HighLevelError("--confirm-location does not match GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    cid = valid_id(str(plan["contact_id"]))
    method = "DELETE" if plan["action"] == "remove_tags" else "POST"
    client.request(method, f"/contacts/{cid}/tags", body=plan["proposed"])
    after_res = client.request("GET", f"/contacts/{cid}")
    after_contact = after_res.get("contact", after_res)
    after_tags = [str(t).lower() for t in (after_contact.get("tags") or [])]
    target_tags = [str(t).lower() for t in plan["proposed"]["tags"]]
    if method == "POST":
        verified = all(t in after_tags for t in target_tags)
    else:
        verified = all(t not in after_tags for t in target_tags)
    if not verified:
        raise HighLevelError("Contact tag mutation readback did not match requested tags.")
    return {
        "mode": "applied",
        "action": plan["action"],
        "location_id": loc,
        "contact_id": cid,
        "verified": True,
        "tags": after_contact.get("tags") or [],
    }


def make_contact_note_plan(
    client: Client,
    *,
    contact_id: str,
    body: str,
) -> dict[str, Any]:
    loc = client.location_id
    cid = valid_id(contact_id)
    clean_body = (body or "").strip()
    if not clean_body:
        raise HighLevelError("Contact note body must not be empty.")
    plan_core = {
        "resource": "contact_note",
        "action": "create_note",
        "location_id": loc,
        "contact_id": cid,
        "proposed": {"body": clean_body},
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_contact_note_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    loc = client.location_id
    if confirm_location != loc:
        raise HighLevelError("--confirm-location does not match GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    cid = valid_id(str(plan["contact_id"]))
    res = client.request("POST", f"/contacts/{cid}/notes", body=plan["proposed"])
    note_obj = res.get("note", res)
    nid = valid_id(str(note_obj.get("id", "")))
    return {
        "mode": "applied",
        "action": "create_note",
        "location_id": loc,
        "contact_id": cid,
        "note_id": nid,
        "verified": True,
    }


def make_opportunity_update_plan(
    client: Client,
    *,
    opportunity_id: str,
    pipeline_stage_id: str | None = None,
    status: str | None = None,
    monetary_value: float | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    oid = valid_id(opportunity_id)
    before_res = client.request("GET", f"/opportunities/{oid}")
    before_opp = before_res.get("opportunity", before_res)
    proposed: dict[str, Any] = {}
    if pipeline_stage_id:
        proposed["pipelineStageId"] = valid_id(pipeline_stage_id)
    if status:
        clean_st = status.strip().lower()
        if clean_st not in {"open", "won", "lost", "abandoned"}:
            raise HighLevelError("Opportunity status must be open, won, lost, or abandoned.")
        proposed["status"] = clean_st
    if monetary_value is not None:
        proposed["monetaryValue"] = float(monetary_value)
    if title and title.strip():
        proposed["name"] = title.strip()
    if not proposed:
        raise HighLevelError("Provide at least one field to update on the opportunity.")
    plan_core = {
        "resource": "opportunity",
        "action": "update",
        "location_id": loc,
        "opportunity_id": oid,
        "before": {
            "id": oid,
            "name": before_opp.get("name"),
            "status": before_opp.get("status"),
            "pipelineId": before_opp.get("pipelineId"),
            "pipelineStageId": before_opp.get("pipelineStageId"),
            "monetaryValue": before_opp.get("monetaryValue"),
        },
        "proposed": proposed,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_opportunity_update_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    loc = client.location_id
    if confirm_location != loc:
        raise HighLevelError("--confirm-location does not match GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    oid = valid_id(str(plan["opportunity_id"]))
    client.request("PUT", f"/opportunities/{oid}", body=plan["proposed"])
    after_res = client.request("GET", f"/opportunities/{oid}")
    after_opp = after_res.get("opportunity", after_res)
    for k, v in plan["proposed"].items():
        if k == "monetaryValue":
            if abs(float(after_opp.get(k) or 0.0) - float(v)) > 1e-4:
                raise HighLevelError("Opportunity update readback mismatch on field monetaryValue.")
        elif after_opp.get(k) != v:
            raise HighLevelError(f"Opportunity update readback mismatch on field {k}.")
    return {
        "mode": "applied",
        "action": "update",
        "location_id": loc,
        "opportunity_id": oid,
        "verified": True,
        "readback": {
            "id": oid,
            "name": after_opp.get("name"),
            "status": after_opp.get("status"),
            "pipelineStageId": after_opp.get("pipelineStageId"),
            "monetaryValue": after_opp.get("monetaryValue"),
        },
    }


def subaccount_audit(client: Client) -> dict[str, Any]:
    """Run a comprehensive sub-account health and readiness audit using Official API v2 (GHL_PIT + GHL_LOCATION_ID)."""
    raw_loc_res = client.request("GET", f"/locations/{client.location_id}")
    raw_loc = raw_loc_res.get("location", raw_loc_res)
    if not isinstance(raw_loc, dict):
        raw_loc = {}
    loc_info = location_snapshot(client)["location"]
    required_profile_fields = ["name", "email", "website", "address", "city", "state", "postalCode", "timezone"]
    missing_profile_fields = [f for f in required_profile_fields if not raw_loc.get(f)]

    pipelines_info = list_pipelines(client)
    opps_info = search_opportunities(client, status="open", limit=20)
    calendars_info = list_calendars(client)
    workflows_info = list_workflows(client)
    forms_info = list_forms(client, limit=50)
    surveys_info = list_surveys(client, limit=50)
    funnels_info = list_funnels(client, limit=50, include_redirects=True)
    tags_info = list_tags(client)
    cv_info = list_custom_values(client)
    cf_info = list_custom_fields(client)
    voice_info = list_voice_ai_agents(client)
    conv_ai_info = list_conversation_ai_agents(client)

    workflows = workflows_info["workflows"]
    published_wf = [w for w in workflows if str(w.get("status", "")).lower() == "published"]
    draft_wf = [w for w in workflows if str(w.get("status", "")).lower() != "published"]

    empty_custom_values = [
        {"id": cv["id"], "name": cv["name"], "fieldKey": cv["fieldKey"]}
        for cv in cv_info["custom_values"]
        if not str(cv.get("value") or "").strip()
    ]

    warnings: list[dict[str, Any]] = []
    if missing_profile_fields:
        warnings.append(
            {
                "area": "business_profile",
                "missing_fields": missing_profile_fields,
                "note": "Populate missing business profile fields in Settings > Business Profile for CAN-SPAM and A2P 10DLC compliance.",
            }
        )
    if empty_custom_values:
        warnings.append(
            {
                "area": "custom_values",
                "empty_count": len(empty_custom_values),
                "empty_custom_values": empty_custom_values,
                "note": "Empty custom values render blank when referenced in email or SMS templates.",
            }
        )
    if draft_wf:
        warnings.append(
            {
                "area": "workflows",
                "draft_count": len(draft_wf),
                "draft_workflows": [{"id": w["id"], "name": w["name"]} for w in draft_wf],
                "note": "Draft workflows do not trigger on live inbound events until published.",
            }
        )

    return {
        "ok": len(missing_profile_fields) == 0,
        "location_id": client.location_id,
        "auth_kind": client.auth_kind,
        "business_profile": loc_info,
        "missing_profile_fields": missing_profile_fields,
        "summary": {
            "pipelines": pipelines_info["count"],
            "open_opportunities": opps_info["count"],
            "calendars": calendars_info["count"],
            "workflows_total": workflows_info["count"],
            "workflows_published": len(published_wf),
            "workflows_draft": len(draft_wf),
            "forms": forms_info["count"],
            "surveys": surveys_info["count"],
            "funnels": funnels_info["count"],
            "redirects": len(funnels_info.get("redirects") or []),
            "tags": tags_info["count"],
            "custom_values_total": cv_info["count"],
            "custom_values_empty": len(empty_custom_values),
            "custom_fields": cf_info["count"],
            "voice_ai_agents": voice_info["count"],
            "conversation_ai_agents": conv_ai_info["count"],
            "warning_count": len(warnings),
        },
        "warnings": warnings,
        "rate_limits": client.last_rate_limits,
    }


def list_email_templates(client: Client, limit: int = 100) -> dict[str, Any]:
    loc = client.location_id
    res = client.request(
        "GET",
        "/emails/builder",
        query={"locationId": loc, "limit": str(max(1, min(limit, 100)))},
    )
    raw = res.get("builders") if isinstance(res.get("builders"), list) else (res.get("templates") or res.get("emails") or [])
    if not isinstance(raw, list):
        raw = []
    templates = [
        {
            "id": str(item.get("id") or item.get("_id") or ""),
            "name": str(item.get("name") or item.get("title") or ""),
            "type": item.get("templateType") or item.get("type"),
            "updatedBy": item.get("updatedBy"),
            "dateUpdated": item.get("dateUpdated") or item.get("updatedAt"),
        }
        for item in raw
        if isinstance(item, dict)
    ]
    raw_total = res.get("total", len(templates))
    if isinstance(raw_total, list) and raw_total and isinstance(raw_total[0], dict):
        raw_total = raw_total[0].get("total", len(templates))
    return {
        "location_id": loc,
        "count": len(templates),
        "total": int(raw_total) if isinstance(raw_total, (int, float)) else len(templates),
        "email_templates": templates,
        "rate_limits": client.last_rate_limits,
    }


def list_trigger_links(client: Client) -> dict[str, Any]:
    loc = client.location_id
    res = client.request("GET", "/links/", query={"locationId": loc})
    raw = res.get("links", [])
    if not isinstance(raw, list):
        raw = []
    links = [
        {
            "id": str(item.get("id") or item.get("_id") or ""),
            "name": str(item.get("name") or ""),
            "redirectTo": item.get("redirectTo"),
            "fieldKey": item.get("fieldKey"),
        }
        for item in raw
        if isinstance(item, dict)
    ]
    return {
        "location_id": loc,
        "count": len(links),
        "links": links,
        "rate_limits": client.last_rate_limits,
    }


def _find_brand_hits(text: str | None, terms: list[str]) -> list[str]:
    if not text or not terms:
        return []
    low = str(text).lower()
    return [t for t in terms if t and t.lower() in low]


def subaccount_rebrand_audit(
    client: Client,
    *,
    brand_terms: list[str] | None = None,
) -> dict[str, Any]:
    """Audit a cloned or existing sub-account via Official API v2 for workflow draft safety, empty custom values, and source brand-term occurrences."""
    clean_terms = [t.strip() for t in (brand_terms or []) if t and t.strip()]
    loc_info = location_snapshot(client)["location"]
    workflows_info = list_workflows(client)
    pipelines_info = list_pipelines(client)
    calendars_info = list_calendars(client)
    forms_info = list_forms(client, limit=50)
    surveys_info = list_surveys(client, limit=50)
    funnels_info = list_funnels(client, limit=50, include_redirects=True)
    cv_info = list_custom_values(client)
    cf_info = list_custom_fields(client)
    tags_info = list_tags(client)

    try:
        emails_info = list_email_templates(client, limit=100)
    except HighLevelError:
        emails_info = {"count": 0, "email_templates": []}
    try:
        links_info = list_trigger_links(client)
    except HighLevelError:
        links_info = {"count": 0, "links": []}

    workflows = workflows_info["workflows"]
    published_wf = [w for w in workflows if str(w.get("status", "")).lower() == "published"]
    draft_wf = [w for w in workflows if str(w.get("status", "")).lower() != "published"]

    risk_keywords = ("capi", "webhook", "meta", "facebook", "stripe", "payment", "betaling", "slack", "zapier", "make")
    integration_risk_workflows = [
        {"id": w["id"], "name": w["name"], "status": w.get("status")}
        for w in workflows
        if any(k in str(w.get("name") or "").lower() for k in risk_keywords)
    ]

    empty_custom_values = [
        {"id": cv["id"], "name": cv["name"], "fieldKey": cv["fieldKey"]}
        for cv in cv_info["custom_values"]
        if not str(cv.get("value") or "").strip()
    ]

    brand_matches: list[dict[str, Any]] = []
    if clean_terms:
        for field_name in ("name", "email", "website", "phone"):
            val = loc_info.get(field_name)
            hits = _find_brand_hits(str(val or ""), clean_terms)
            if hits:
                brand_matches.append(
                    {
                        "category": "business_profile",
                        "field": field_name,
                        "value": val,
                        "matched_terms": hits,
                    }
                )
        for cv in cv_info["custom_values"]:
            hits = _find_brand_hits(f"{cv.get('name', '')} {cv.get('value', '')}", clean_terms)
            if hits:
                brand_matches.append(
                    {
                        "category": "custom_value",
                        "id": cv["id"],
                        "name": cv["name"],
                        "value": cv.get("value"),
                        "matched_terms": hits,
                    }
                )
        for p in pipelines_info["pipelines"]:
            hits = _find_brand_hits(p.get("name"), clean_terms)
            if hits:
                brand_matches.append(
                    {
                        "category": "pipeline",
                        "id": p["id"],
                        "name": p["name"],
                        "matched_terms": hits,
                    }
                )
        for c in calendars_info["calendars"]:
            hits = _find_brand_hits(f"{c.get('name', '')} {c.get('slug', '')}", clean_terms)
            if hits:
                brand_matches.append(
                    {
                        "category": "calendar",
                        "id": c["id"],
                        "name": c["name"],
                        "slug": c.get("slug"),
                        "matched_terms": hits,
                    }
                )
        for f in forms_info["forms"]:
            hits = _find_brand_hits(f.get("name"), clean_terms)
            if hits:
                brand_matches.append(
                    {
                        "category": "form",
                        "id": f["id"],
                        "name": f["name"],
                        "matched_terms": hits,
                    }
                )
        for em in emails_info["email_templates"]:
            hits = _find_brand_hits(em.get("name"), clean_terms)
            if hits:
                brand_matches.append(
                    {
                        "category": "email_template",
                        "id": em["id"],
                        "name": em["name"],
                        "matched_terms": hits,
                    }
                )
        for lk in links_info["links"]:
            hits = _find_brand_hits(f"{lk.get('name', '')} {lk.get('redirectTo', '')}", clean_terms)
            if hits:
                brand_matches.append(
                    {
                        "category": "trigger_link",
                        "id": lk["id"],
                        "name": lk["name"],
                        "redirectTo": lk.get("redirectTo"),
                        "matched_terms": hits,
                    }
                )
        for wf in workflows:
            hits = _find_brand_hits(wf.get("name"), clean_terms)
            if hits:
                brand_matches.append(
                    {
                        "category": "workflow",
                        "id": wf["id"],
                        "name": wf["name"],
                        "status": wf.get("status"),
                        "matched_terms": hits,
                    }
                )

    return {
        "ok": len(published_wf) == 0,
        "location_id": client.location_id,
        "business_profile": loc_info,
        "all_workflows_draft": len(published_wf) == 0,
        "asset_counts": {
            "workflows_total": len(workflows),
            "workflows_published": len(published_wf),
            "workflows_draft": len(draft_wf),
            "pipelines": pipelines_info["count"],
            "calendars": calendars_info["count"],
            "forms": forms_info["count"],
            "surveys": surveys_info["count"],
            "funnels": funnels_info["count"],
            "email_templates": emails_info["count"],
            "trigger_links": links_info["count"],
            "custom_values": cv_info["count"],
            "custom_fields": cf_info["count"],
            "tags": tags_info["count"],
        },
        "published_workflows": [{"id": w["id"], "name": w["name"]} for w in published_wf],
        "integration_risk_workflows": integration_risk_workflows,
        "empty_custom_values": empty_custom_values,
        "brand_terms_checked": clean_terms,
        "brand_match_count": len(brand_matches),
        "brand_matches": brand_matches,
        "rate_limits": client.last_rate_limits,
    }


def inspect_profiles_matrix(
    *,
    profiles: list[str] | None = None,
    client_factory=Client,
) -> dict[str, Any]:
    """Compare asset and workflow status across multiple configured sub-account profiles."""
    base_cfg = load_subaccount_config()
    available_profiles = list((base_cfg.get("profiles") or {}).keys())
    target_profiles = (
        [p.strip() for p in profiles if p and p.strip()]
        if profiles
        else (available_profiles if available_profiles else [base_cfg.get("selected_profile", "default")])
    )
    rows: list[dict[str, Any]] = []
    all_ok = True
    for prof_name in target_profiles:
        try:
            c = client_factory(profile=prof_name)
            loc = location_snapshot(c)["location"]
            wfs = list_workflows(c)["workflows"]
            pub_count = sum(1 for w in wfs if str(w.get("status", "")).lower() == "published")
            draft_count = len(wfs) - pub_count
            pipes = list_pipelines(c)["count"]
            cals = list_calendars(c)["count"]
            forms_cnt = list_forms(c, limit=50)["count"]
            cvs = list_custom_values(c)["count"]
            rows.append(
                {
                    "profile": prof_name,
                    "ok": True,
                    "location_id": c.location_id,
                    "name": loc.get("name"),
                    "domain": loc.get("domain"),
                    "workflows_total": len(wfs),
                    "workflows_published": pub_count,
                    "workflows_draft": draft_count,
                    "pipelines": pipes,
                    "calendars": cals,
                    "forms": forms_cnt,
                    "custom_values": cvs,
                }
            )
        except HighLevelError as exc:
            all_ok = False
            rows.append(
                {
                    "profile": prof_name,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return {
        "ok": all_ok,
        "profile_count": len(rows),
        "profiles": rows,
    }


def make_subaccount_update_plan(
    client: Client,
    *,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
    timezone: str | None = None,
    logo_url: str | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    before = location_snapshot(client)["location"]
    updates: dict[str, Any] = {}
    field_map = {
        "name": name,
        "email": email,
        "phone": phone,
        "website": website,
        "address": address,
        "city": city,
        "state": state,
        "postalCode": postal_code,
        "country": country,
        "timezone": timezone,
        "logoUrl": logo_url,
    }
    for key, val in field_map.items():
        if val is not None and str(val).strip():
            updates[key] = str(val).strip()
    if not updates:
        raise HighLevelError("Provide at least one sub-account profile field to update.")
    plan_core = {
        "resource": "subaccount_profile",
        "action": "update",
        "location_id": loc,
        "before": {k: before.get(k) for k in updates},
        "proposed_request": {
            "method": "PUT",
            "path": f"/locations/{loc}",
            "payload": updates,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_subaccount_update_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_location != client.location_id:
        raise HighLevelError("--confirm-location must equal GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = client.request(req["method"], req["path"], body=req["payload"])
    after = location_snapshot(client)["location"]
    return {
        "mode": "applied",
        "action": "update",
        "location_id": client.location_id,
        "before": plan.get("before"),
        "after": {k: after.get(k) for k in req["payload"]},
        "verified": True,
        "response": res,
        "rate_limits": client.last_rate_limits,
    }


def make_custom_field_plan(
    client: Client,
    *,
    action: str,
    name: str,
    data_type: str = "TEXT",
    model: str = "contact",
    placeholder: str | None = None,
    options: list[str] | None = None,
    custom_field_id: str | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    clean_name = (name or "").strip()
    if not clean_name:
        raise HighLevelError("Custom field name is required.")
    existing = list_custom_fields(client)["custom_fields"]
    matched = None
    if custom_field_id:
        fid = valid_id(custom_field_id)
        matched = next((f for f in existing if f["id"] == fid), None)
    else:
        matched = next((f for f in existing if f["name"].lower() == clean_name.lower()), None)

    if action == "delete":
        target_id = valid_id(custom_field_id or (matched["id"] if matched else None))
        plan_core = {
            "resource": "custom_field",
            "action": "delete",
            "location_id": loc,
            "custom_field_id": target_id,
            "before": matched,
            "proposed_request": {
                "method": "DELETE",
                "path": f"/locations/{loc}/customFields/{target_id}",
                "payload": None,
            },
        }
        return {**plan_core, "sha256": plan_digest(plan_core)}

    payload: dict[str, Any] = {
        "name": clean_name,
        "dataType": (data_type or "TEXT").strip().upper(),
        "model": (model or "contact").strip(),
    }
    if placeholder is not None:
        payload["placeholder"] = placeholder
    if options:
        payload["options"] = [str(o).strip() for o in options if str(o).strip()]

    if matched:
        fid = valid_id(matched["id"])
        req = {
            "method": "PUT",
            "path": f"/locations/{loc}/customFields/{fid}",
            "payload": payload,
        }
        resolved_action = "update"
    else:
        req = {
            "method": "POST",
            "path": f"/locations/{loc}/customFields",
            "payload": payload,
        }
        resolved_action = "create"

    plan_core = {
        "resource": "custom_field",
        "action": resolved_action,
        "location_id": loc,
        "before": matched,
        "proposed_request": req,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_custom_field_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_location != client.location_id:
        raise HighLevelError("--confirm-location must equal GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = client.request(req["method"], req["path"], body=req["payload"])
    return {
        "mode": "applied",
        "action": plan["action"],
        "location_id": client.location_id,
        "verified": True,
        "response": res,
        "rate_limits": client.last_rate_limits,
    }


def make_trigger_link_plan(
    client: Client,
    *,
    action: str,
    name: str,
    redirect_to: str | None = None,
    link_id: str | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    clean_name = (name or "").strip()
    existing = list_trigger_links(client)["links"]
    matched = None
    if link_id:
        lid = valid_id(link_id)
        matched = next((lk for lk in existing if lk["id"] == lid), None)
    elif clean_name:
        matched = next((lk for lk in existing if lk["name"].lower() == clean_name.lower()), None)

    if action == "delete":
        target_id = valid_id(link_id or (matched["id"] if matched else None))
        plan_core = {
            "resource": "trigger_link",
            "action": "delete",
            "location_id": loc,
            "link_id": target_id,
            "before": matched,
            "proposed_request": {
                "method": "DELETE",
                "path": f"/links/{target_id}",
                "payload": None,
            },
        }
        return {**plan_core, "sha256": plan_digest(plan_core)}

    if not clean_name or not (redirect_to and redirect_to.strip()):
        raise HighLevelError("Trigger link --name and --redirect-to are required.")
    url = redirect_to.strip()
    if matched:
        target_id = valid_id(matched["id"])
        req = {
            "method": "PUT",
            "path": f"/links/{target_id}",
            "payload": {"name": clean_name, "redirectTo": url},
        }
        resolved_action = "update"
    else:
        req = {
            "method": "POST",
            "path": "/links/",
            "payload": {"locationId": loc, "name": clean_name, "redirectTo": url},
        }
        resolved_action = "create"
    plan_core = {
        "resource": "trigger_link",
        "action": resolved_action,
        "location_id": loc,
        "before": matched,
        "proposed_request": req,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_trigger_link_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_location != client.location_id:
        raise HighLevelError("--confirm-location must equal GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = client.request(req["method"], req["path"], body=req["payload"])
    return {
        "mode": "applied",
        "action": plan["action"],
        "location_id": client.location_id,
        "verified": True,
        "response": res,
        "rate_limits": client.last_rate_limits,
    }


def make_calendar_update_plan(
    client: Client,
    *,
    calendar_id: str,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    cid = valid_id(calendar_id)
    cal_res = client.request("GET", f"/calendars/{cid}")
    cal = cal_res.get("calendar", cal_res)
    if not isinstance(cal, dict):
        cal = {}
    updates: dict[str, Any] = {}
    if name is not None and name.strip():
        updates["name"] = name.strip()
    if slug is not None and slug.strip():
        updates["slug"] = slug.strip()
    if description is not None:
        updates["description"] = description
    if is_active is not None:
        updates["isActive"] = bool(is_active)
    if not updates:
        raise HighLevelError("Provide at least one calendar field to update (--name, --slug, --description, or --active/--inactive).")
    plan_core = {
        "resource": "calendar",
        "action": "update",
        "location_id": loc,
        "calendar_id": cid,
        "before": {
            "name": cal.get("name"),
            "slug": cal.get("slug"),
            "description": cal.get("description"),
            "isActive": cal.get("isActive"),
        },
        "proposed_request": {
            "method": "PUT",
            "path": f"/calendars/{cid}",
            "payload": updates,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_calendar_update_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_location != client.location_id:
        raise HighLevelError("--confirm-location must equal GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = client.request(req["method"], req["path"], body=req["payload"])
    return {
        "mode": "applied",
        "action": "update",
        "location_id": client.location_id,
        "calendar_id": plan["calendar_id"],
        "verified": True,
        "response": res,
        "rate_limits": client.last_rate_limits,
    }


def list_conversation_messages(
    client: Client,
    *,
    conversation_id: str,
    limit: int = 20,
) -> dict[str, Any]:
    cid = valid_id(conversation_id)
    res = client.request(
        "GET",
        f"/conversations/{cid}/messages",
        query={"limit": max(1, min(int(limit), 100))},
    )
    raw_msgs = res.get("messages")
    if isinstance(raw_msgs, dict) and isinstance(raw_msgs.get("messages"), list):
        raw_list = raw_msgs["messages"]
    elif isinstance(raw_msgs, list):
        raw_list = raw_msgs
    else:
        raw_list = []
    messages = [
        {
            "id": str(m.get("id") or ""),
            "type": m.get("type") or m.get("messageType"),
            "direction": m.get("direction"),
            "status": m.get("status"),
            "body": m.get("body"),
            "subject": m.get("subject"),
            "dateAdded": m.get("dateAdded"),
        }
        for m in raw_list
        if isinstance(m, dict)
    ]
    return {
        "location_id": client.location_id,
        "conversation_id": cid,
        "count": len(messages),
        "messages": messages,
        "rate_limits": client.last_rate_limits,
    }


def make_conversation_send_plan(
    client: Client,
    *,
    contact_id: str,
    message_type: str = "SMS",
    message: str | None = None,
    subject: str | None = None,
    html: str | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    cid = valid_id(contact_id)
    mtype = (message_type or "SMS").strip()
    if mtype not in {"SMS", "Email", "WhatsApp", "Live_Chat", "IG", "FB"}:
        raise HighLevelError("Unsupported message --type; choose SMS, Email, WhatsApp, Live_Chat, IG, or FB.")
    payload: dict[str, Any] = {
        "type": mtype,
        "contactId": cid,
    }
    if message is not None and message.strip():
        payload["message"] = message.strip()
    if subject is not None and subject.strip():
        payload["subject"] = subject.strip()
    if html is not None and html.strip():
        payload["html"] = html.strip()
    if "message" not in payload and "html" not in payload:
        raise HighLevelError("Provide --message or --html to send a conversation message.")
    plan_core = {
        "resource": "conversation_message",
        "action": "send",
        "location_id": loc,
        "contact_id": cid,
        "proposed_request": {
            "method": "POST",
            "path": "/conversations/messages",
            "payload": payload,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_conversation_send_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_location != client.location_id:
        raise HighLevelError("--confirm-location must equal GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = client.request(req["method"], req["path"], body=req["payload"])
    return {
        "mode": "applied",
        "action": "send",
        "location_id": client.location_id,
        "contact_id": plan["contact_id"],
        "verified": True,
        "response": res,
        "rate_limits": client.last_rate_limits,
    }


def _apply_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    out = text
    for old_val, new_val in replacements:
        if not old_val:
            continue
        pattern = re.compile(re.escape(old_val), re.IGNORECASE)
        out = pattern.sub(new_val, out)
    return out


def make_subaccount_rebrand_plan(
    client: Client,
    *,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
    timezone: str | None = None,
    logo_url: str | None = None,
    replace_pairs: list[tuple[str, str]] | None = None,
    custom_values_override: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build an atomic sub-account rebranding plan across Business Profile, Custom Values, Trigger Links, and Calendars."""
    loc = client.location_id
    before_loc = location_snapshot(client)["location"]
    clean_pairs = [(str(k).strip(), str(v).strip()) for k, v in (replace_pairs or []) if str(k).strip()]
    cv_overrides = {str(k).strip().lower(): (str(k).strip(), str(v)) for k, v in (custom_values_override or {}).items() if str(k).strip()}

    profile_updates: dict[str, Any] = {}
    explicit_profile = {
        "name": name,
        "email": email,
        "phone": phone,
        "website": website,
        "address": address,
        "city": city,
        "state": state,
        "postalCode": postal_code,
        "country": country,
        "timezone": timezone,
        "logoUrl": logo_url,
    }
    for k, v in explicit_profile.items():
        if v is not None and str(v).strip():
            profile_updates[k] = str(v).strip()
        elif clean_pairs and isinstance(before_loc.get(k), str) and before_loc.get(k):
            replaced = _apply_replacements(str(before_loc[k]), clean_pairs)
            if replaced != before_loc[k]:
                profile_updates[k] = replaced

    existing_cvs = list_custom_values(client)["custom_values"]
    cv_mutations: list[dict[str, Any]] = []
    matched_override_keys: set[str] = set()
    for cv in existing_cvs:
        cv_id = cv["id"]
        cv_name = cv["name"]
        old_val = str(cv.get("value") or "")
        low_name = cv_name.lower()
        low_key = str(cv.get("fieldKey") or "").lower()
        new_val = old_val
        if low_name in cv_overrides:
            new_val = cv_overrides[low_name][1]
            matched_override_keys.add(low_name)
        elif low_key in cv_overrides:
            new_val = cv_overrides[low_key][1]
            matched_override_keys.add(low_key)
        elif clean_pairs and old_val:
            new_val = _apply_replacements(old_val, clean_pairs)
        if new_val != old_val:
            cv_mutations.append(
                {
                    "action": "update",
                    "id": cv_id,
                    "name": cv_name,
                    "before_value": old_val,
                    "after_value": new_val,
                    "request": {
                        "method": "PUT",
                        "path": f"/locations/{loc}/customValues/{cv_id}",
                        "payload": {"name": cv_name, "value": new_val},
                    },
                }
            )

    for low_k, (orig_name, val) in cv_overrides.items():
        if low_k not in matched_override_keys:
            cv_mutations.append(
                {
                    "action": "create",
                    "id": None,
                    "name": orig_name,
                    "before_value": None,
                    "after_value": val,
                    "request": {
                        "method": "POST",
                        "path": f"/locations/{loc}/customValues",
                        "payload": {"name": orig_name, "value": val},
                    },
                }
            )

    link_mutations: list[dict[str, Any]] = []
    if clean_pairs:
        try:
            existing_links = list_trigger_links(client)["links"]
        except HighLevelError:
            existing_links = []
        for lk in existing_links:
            lid = lk["id"]
            old_name = str(lk.get("name") or "")
            old_url = str(lk.get("redirectTo") or "")
            new_name = _apply_replacements(old_name, clean_pairs)
            new_url = _apply_replacements(old_url, clean_pairs)
            if new_name != old_name or new_url != old_url:
                link_mutations.append(
                    {
                        "id": lid,
                        "before_name": old_name,
                        "after_name": new_name,
                        "before_redirect_to": old_url,
                        "after_redirect_to": new_url,
                        "request": {
                            "method": "PUT",
                            "path": f"/links/{lid}",
                            "payload": {"name": new_name, "redirectTo": new_url},
                        },
                    }
                )

    calendar_mutations: list[dict[str, Any]] = []
    if clean_pairs:
        existing_cals = list_calendars(client)["calendars"]
        for cal in existing_cals:
            cid = cal["id"]
            old_name = str(cal.get("name") or "")
            new_name = _apply_replacements(old_name, clean_pairs)
            if new_name != old_name:
                calendar_mutations.append(
                    {
                        "id": cid,
                        "before_name": old_name,
                        "after_name": new_name,
                        "request": {
                            "method": "PUT",
                            "path": f"/calendars/{cid}",
                            "payload": {"name": new_name},
                        },
                    }
                )

    plan_core = {
        "resource": "subaccount_rebrand",
        "action": "rebrand",
        "location_id": loc,
        "replace_pairs": [{"from": k, "to": v} for k, v in clean_pairs],
        "business_profile_update": (
            {
                "before": {k: before_loc.get(k) for k in profile_updates},
                "after": profile_updates,
                "request": {
                    "method": "PUT",
                    "path": f"/locations/{loc}",
                    "payload": profile_updates,
                },
            }
            if profile_updates
            else None
        ),
        "custom_value_mutations": cv_mutations,
        "trigger_link_mutations": link_mutations,
        "calendar_mutations": calendar_mutations,
        "summary": {
            "profile_fields_changed": len(profile_updates),
            "custom_values_changed": len(cv_mutations),
            "trigger_links_changed": len(link_mutations),
            "calendars_changed": len(calendar_mutations),
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_subaccount_rebrand_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_location != client.location_id:
        raise HighLevelError("--confirm-location must equal GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    prof_up = plan.get("business_profile_update")
    if isinstance(prof_up, dict) and isinstance(prof_up.get("request"), dict):
        req = prof_up["request"]
        client.request(req["method"], req["path"], body=req["payload"])

    cv_results = []
    for item in plan.get("custom_value_mutations", []):
        req = item["request"]
        client.request(req["method"], req["path"], body=req["payload"])
        cv_results.append({"name": item["name"], "action": item["action"], "after_value": item["after_value"]})

    link_results = []
    for item in plan.get("trigger_link_mutations", []):
        req = item["request"]
        client.request(req["method"], req["path"], body=req["payload"])
        link_results.append({"id": item["id"], "after_name": item["after_name"], "after_redirect_to": item["after_redirect_to"]})

    cal_results = []
    for item in plan.get("calendar_mutations", []):
        req = item["request"]
        client.request(req["method"], req["path"], body=req["payload"])
        cal_results.append({"id": item["id"], "after_name": item["after_name"]})

    after_loc = location_snapshot(client)["location"]
    return {
        "mode": "applied",
        "action": "rebrand",
        "location_id": client.location_id,
        "business_profile": after_loc,
        "custom_values_applied": cv_results,
        "trigger_links_applied": link_results,
        "calendars_applied": cal_results,
        "verified": True,
        "rate_limits": client.last_rate_limits,
    }


def list_subaccount_users(client: Client) -> dict[str, Any]:
    """List users assigned to the sub-account via Official API v2 GET /users/?locationId=:locationId."""
    loc = client.location_id
    res = client.request("GET", "/users/", query={"locationId": loc})
    raw_users = res.get("users", []) if isinstance(res, dict) and isinstance(res.get("users"), list) else []
    users = [
        {
            "id": str(u.get("id") or ""),
            "name": u.get("name") or f"{u.get('firstName', '')} {u.get('lastName', '')}".strip(),
            "firstName": u.get("firstName"),
            "lastName": u.get("lastName"),
            "email": u.get("email"),
            "phone": u.get("phone"),
            "type": (u.get("roles") or {}).get("type") if isinstance(u.get("roles"), dict) else u.get("type"),
            "role": (u.get("roles") or {}).get("role") if isinstance(u.get("roles"), dict) else u.get("role"),
            "deleted": bool(u.get("deleted", False)),
        }
        for u in raw_users
        if isinstance(u, dict)
    ]
    return {
        "location_id": loc,
        "count": len(users),
        "users": users,
        "rate_limits": client.last_rate_limits,
    }


def list_contact_notes(client: Client, *, contact_id: str) -> dict[str, Any]:
    """List notes on a contact via GET /contacts/:contactId/notes."""
    cid = valid_id(contact_id)
    res = client.request("GET", f"/contacts/{cid}/notes")
    raw_notes = res.get("notes", []) if isinstance(res, dict) and isinstance(res.get("notes"), list) else []
    notes = [
        {
            "id": str(n.get("id") or ""),
            "body": n.get("body") or n.get("bodyText"),
            "userId": n.get("userId"),
            "dateAdded": n.get("dateAdded"),
        }
        for n in raw_notes
        if isinstance(n, dict)
    ]
    return {
        "location_id": client.location_id,
        "contact_id": cid,
        "count": len(notes),
        "notes": notes,
        "rate_limits": client.last_rate_limits,
    }


def list_contact_tasks(client: Client, *, contact_id: str) -> dict[str, Any]:
    """List tasks on a contact via GET /contacts/:contactId/tasks."""
    cid = valid_id(contact_id)
    res = client.request("GET", f"/contacts/{cid}/tasks")
    raw_tasks = res.get("tasks", []) if isinstance(res, dict) and isinstance(res.get("tasks"), list) else []
    tasks = [
        {
            "id": str(t.get("id") or ""),
            "title": t.get("title"),
            "body": t.get("body"),
            "dueDate": t.get("dueDate"),
            "completed": bool(t.get("completed", False)),
            "assignedTo": t.get("assignedTo"),
        }
        for t in raw_tasks
        if isinstance(t, dict)
    ]
    return {
        "location_id": client.location_id,
        "contact_id": cid,
        "count": len(tasks),
        "tasks": tasks,
        "rate_limits": client.last_rate_limits,
    }


def make_contact_task_plan(
    client: Client,
    *,
    contact_id: str,
    title: str,
    body: str | None = None,
    due_date: str | None = None,
    completed: bool = False,
    assigned_to: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    cid = valid_id(contact_id)
    clean_title = (title or "").strip()
    if not clean_title:
        raise HighLevelError("Task --title is required.")
    payload: dict[str, Any] = {
        "title": clean_title,
        "completed": bool(completed),
    }
    if body is not None:
        payload["body"] = body
    if due_date is not None and due_date.strip():
        payload["dueDate"] = due_date.strip()
    else:
        payload["dueDate"] = "2026-12-31T17:00:00Z"
    if assigned_to is not None and assigned_to.strip():
        payload["assignedTo"] = valid_id(assigned_to.strip())

    if task_id and task_id.strip():
        tid = valid_id(task_id.strip())
        action = "update"
        req = {
            "method": "PUT",
            "path": f"/contacts/{cid}/tasks/{tid}",
            "payload": payload,
        }
    else:
        action = "create"
        req = {
            "method": "POST",
            "path": f"/contacts/{cid}/tasks",
            "payload": payload,
        }

    plan_core = {
        "resource": "contact_task",
        "action": action,
        "location_id": loc,
        "contact_id": cid,
        "proposed_request": req,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_contact_task_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_location != client.location_id:
        raise HighLevelError("--confirm-location must equal GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = client.request(req["method"], req["path"], body=req["payload"])
    return {
        "mode": "applied",
        "action": plan["action"],
        "location_id": client.location_id,
        "contact_id": plan["contact_id"],
        "verified": True,
        "response": res,
        "rate_limits": client.last_rate_limits,
    }


def list_calendar_events(
    client: Client,
    *,
    calendar_id: str | None = None,
    user_id: str | None = None,
    group_id: str | None = None,
    start_time: str | int | None = None,
    end_time: str | int | None = None,
) -> dict[str, Any]:
    """List calendar events/appointments via GET /calendars/events."""
    loc = client.location_id
    cal_id = valid_id(calendar_id) if calendar_id and calendar_id.strip() else None
    uid = valid_id(user_id) if user_id and user_id.strip() else None
    gid = valid_id(group_id) if group_id and group_id.strip() else None

    if not any([cal_id, uid, gid]):
        cals = list_calendars(client)["calendars"]
        if not cals:
            return {
                "location_id": loc,
                "calendar_id": None,
                "count": 0,
                "events": [],
                "rate_limits": client.last_rate_limits,
            }
        cal_id = cals[0]["id"]

    now_ms = int(time.time() * 1000)
    s_ms = str(start_time) if start_time is not None else str(now_ms - 30 * 86400 * 1000)
    e_ms = str(end_time) if end_time is not None else str(now_ms + 60 * 86400 * 1000)

    query: dict[str, Any] = {
        "locationId": loc,
        "startTime": s_ms,
        "endTime": e_ms,
    }
    if cal_id:
        query["calendarId"] = cal_id
    if uid:
        query["userId"] = uid
    if gid:
        query["groupId"] = gid

    res = client.request("GET", "/calendars/events", query=query)
    raw_events = res.get("events", []) if isinstance(res, dict) and isinstance(res.get("events"), list) else []
    events = [
        {
            "id": str(ev.get("id") or ""),
            "title": ev.get("title"),
            "calendarId": ev.get("calendarId"),
            "contactId": ev.get("contactId"),
            "appointmentStatus": ev.get("appointmentStatus") or ev.get("status"),
            "startTime": ev.get("startTime"),
            "endTime": ev.get("endTime"),
            "assignedUserId": ev.get("assignedUserId"),
        }
        for ev in raw_events
        if isinstance(ev, dict)
    ]
    return {
        "location_id": loc,
        "calendar_id": cal_id,
        "count": len(events),
        "events": events,
        "rate_limits": client.last_rate_limits,
    }


def make_appointment_create_plan(
    client: Client,
    *,
    calendar_id: str,
    contact_id: str,
    start_time: str,
    end_time: str | None = None,
    title: str | None = None,
    appointment_status: str = "confirmed",
    assigned_user_id: str | None = None,
    address: str | None = None,
) -> dict[str, Any]:
    loc = client.location_id
    cal_id = valid_id(calendar_id)
    cid = valid_id(contact_id)
    if not start_time or not start_time.strip():
        raise HighLevelError("Appointment --start-time (ISO-8601) is required.")
    payload: dict[str, Any] = {
        "calendarId": cal_id,
        "locationId": loc,
        "contactId": cid,
        "startTime": start_time.strip(),
        "appointmentStatus": (appointment_status or "confirmed").strip(),
    }
    if end_time and end_time.strip():
        payload["endTime"] = end_time.strip()
    if title and title.strip():
        payload["title"] = title.strip()
    if assigned_user_id and assigned_user_id.strip():
        payload["assignedUserId"] = valid_id(assigned_user_id.strip())
    if address and address.strip():
        payload["address"] = address.strip()

    plan_core = {
        "resource": "calendar_appointment",
        "action": "create",
        "location_id": loc,
        "calendar_id": cal_id,
        "contact_id": cid,
        "proposed_request": {
            "method": "POST",
            "path": "/calendars/events/appointments",
            "payload": payload,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_appointment_create_plan(
    client: Client,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_location != client.location_id:
        raise HighLevelError("--confirm-location must equal GHL_LOCATION_ID.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = client.request(req["method"], req["path"], body=req["payload"])
    return {
        "mode": "applied",
        "action": "create",
        "location_id": client.location_id,
        "calendar_id": plan["calendar_id"],
        "contact_id": plan["contact_id"],
        "verified": True,
        "response": res,
        "rate_limits": client.last_rate_limits,
    }


def list_media_files(
    client: Client,
    *,
    limit: int = 50,
    query_str: str | None = None,
) -> dict[str, Any]:
    """List files in the sub-account Media Library via GET /medias/files."""
    loc = client.location_id
    query: dict[str, Any] = {
        "sortBy": "createdAt",
        "sortOrder": "desc",
        "type": "file",
        "altType": "location",
        "altId": loc,
        "limit": str(max(1, min(int(limit), 100))),
    }
    if query_str and query_str.strip():
        query["query"] = query_str.strip()
    res = client.request("GET", "/medias/files", query=query)
    raw_files = res.get("files", []) if isinstance(res, dict) and isinstance(res.get("files"), list) else []
    files = [
        {
            "id": str(f.get("id") or f.get("_id") or ""),
            "name": f.get("name"),
            "url": f.get("url"),
            "type": f.get("type"),
            "createdAt": f.get("createdAt"),
        }
        for f in raw_files
        if isinstance(f, dict)
    ]
    return {
        "location_id": loc,
        "count": len(files),
        "files": files,
        "rate_limits": client.last_rate_limits,
    }


def list_products(client: Client, *, limit: int = 50) -> dict[str, Any]:
    """List products in the sub-account via GET /products/."""
    loc = client.location_id
    res = client.request(
        "GET",
        "/products/",
        query={"locationId": loc, "limit": str(max(1, min(int(limit), 100)))},
    )
    raw = res.get("products", []) if isinstance(res, dict) and isinstance(res.get("products"), list) else []
    products = [
        {
            "id": str(p.get("_id") or p.get("id") or ""),
            "name": p.get("name"),
            "productType": p.get("productType"),
            "availableInStore": p.get("availableInStore"),
            "createdAt": p.get("createdAt"),
        }
        for p in raw
        if isinstance(p, dict)
    ]
    return {
        "location_id": loc,
        "count": len(products),
        "products": products,
        "rate_limits": client.last_rate_limits,
    }


def list_invoices(client: Client, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """List invoices in the sub-account via GET /invoices/."""
    loc = client.location_id
    res = client.request(
        "GET",
        "/invoices/",
        query={
            "altId": loc,
            "altType": "location",
            "limit": str(max(1, min(int(limit), 100))),
            "offset": str(max(0, int(offset))),
        },
    )
    raw = res.get("invoices", []) if isinstance(res, dict) and isinstance(res.get("invoices"), list) else []
    invoices = [
        {
            "id": str(inv.get("_id") or inv.get("id") or ""),
            "name": inv.get("name"),
            "invoiceNumber": inv.get("invoiceNumber"),
            "status": inv.get("status"),
            "total": inv.get("total"),
            "currency": inv.get("currency"),
            "createdAt": inv.get("createdAt"),
        }
        for inv in raw
        if isinstance(inv, dict)
    ]
    return {
        "location_id": loc,
        "count": len(invoices),
        "total": res.get("total", len(invoices)) if isinstance(res, dict) else len(invoices),
        "invoices": invoices,
        "rate_limits": client.last_rate_limits,
    }


def list_transactions(client: Client, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """List payment transactions in the sub-account via GET /payments/transactions."""
    loc = client.location_id
    res = client.request(
        "GET",
        "/payments/transactions",
        query={
            "altId": loc,
            "altType": "location",
            "limit": str(max(1, min(int(limit), 100))),
            "offset": str(max(0, int(offset))),
        },
    )
    raw = res.get("data", []) if isinstance(res, dict) and isinstance(res.get("data"), list) else []
    transactions = [
        {
            "id": str(tx.get("_id") or tx.get("id") or ""),
            "amount": tx.get("amount"),
            "currency": tx.get("currency"),
            "status": tx.get("status"),
            "contactName": tx.get("contactName"),
            "entitySourceType": tx.get("entitySourceType"),
            "createdAt": tx.get("createdAt"),
        }
        for tx in raw
        if isinstance(tx, dict)
    ]
    return {
        "location_id": loc,
        "count": len(transactions),
        "total": res.get("totalCount", len(transactions)) if isinstance(res, dict) else len(transactions),
        "transactions": transactions,
        "rate_limits": client.last_rate_limits,
    }


def list_blogs(client: Client, *, limit: int = 20, skip: int = 0) -> dict[str, Any]:
    """List blog sites in the sub-account via GET /blogs/site/all."""
    loc = client.location_id
    res = client.request(
        "GET",
        "/blogs/site/all",
        query={
            "locationId": loc,
            "limit": str(max(1, min(int(limit), 100))),
            "skip": str(max(0, int(skip))),
        },
    )
    raw = res.get("data", []) if isinstance(res, dict) and isinstance(res.get("data"), list) else []
    blogs = [
        {
            "id": str(b.get("_id") or b.get("id") or ""),
            "name": b.get("name"),
            "domain": b.get("domain"),
            "slug": b.get("slug"),
        }
        for b in raw
        if isinstance(b, dict)
    ]
    return {
        "location_id": loc,
        "count": len(blogs),
        "blogs": blogs,
        "rate_limits": client.last_rate_limits,
    }

