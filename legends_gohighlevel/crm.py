"""Sub-account CRM inspection and preview-first mutations with SHA-256 plan confirmation."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .api import API_VERSION_V3, Client, HighLevelError, valid_id, valid_object_key

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
