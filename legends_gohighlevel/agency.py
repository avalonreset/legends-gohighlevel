"""Live agency, sub-account, user scope, Custom SMTP, and dashboard RBAC operations via HighLevel internal backend."""
from __future__ import annotations

import re
from typing import Any

from .api import BackendClient, HighLevelError, valid_id
from .crm import plan_digest
from .governance import (
    AGENCY_ONLY_V2_SCOPES,
    CRITICAL_ACCOUNT_ADMIN_V2_SCOPES,
    DEFAULT_DASHBOARD_PERMISSION_ACCESS,
    MUTUALLY_EXCLUSIVE_V2_SCOPES,
    SAAS_BILLING_V2_KEYS,
    UNNERFED_LOCATION_PERMISSIONS,
    UNNERFED_V1_PERMISSIONS,
    markup_to_multiplier,
)

PLUS_ALIAS_RE = re.compile(r"^([^+@]+)\+[^@]+@(.+)$")
SCOPE_EQUIVALENTS: dict[str, tuple[str, ...]] = {
    "funnels.readonly": ("funnels.write",),
    "websites.readonly": ("websites.write",),
    "custom-menu-link.write": ("custom-menu-link.readonly",),
    "socialplanner/Setting.write": ("socialplanner/setting.write", "socialplanner/post.write"),
    "reporting/facebook.readonly": ("reporting/facebookAds.readonly",),
}


def _require_company_id(backend: BackendClient, company_id: str | None = None) -> str:
    cid = company_id or backend.company_id
    if not cid:
        raise HighLevelError(
            "Pass --company-id or set company_id in ~/.config/legends-gohighlevel/agency.json (or GHL_COMPANY_ID)."
        )
    return valid_id(cid)


def _canonical_base_email(email: str) -> str:
    clean = (email or "").strip().lower()
    m = PLUS_ALIAS_RE.match(clean)
    if m:
        return f"{m.group(1)}@{m.group(2)}"
    return clean


def list_agency_locations(
    backend: BackendClient,
    *,
    company_id: str | None = None,
    location_id: str | None = None,
) -> dict[str, Any]:
    if location_id:
        lid = valid_id(location_id)
        res = backend.request("GET", f"/locations/{lid}")
        loc = res.get("location", res)
        if not isinstance(loc, dict):
            raise HighLevelError("Invalid location response from backend.")
        perms = loc.get("permissions") or {}
        disabled_perms = [k for k, v in perms.items() if v is False]
        missing_perms = [
            k for k, expected in UNNERFED_LOCATION_PERMISSIONS.items()
            if expected is True and perms.get(k) is not True
        ]
        return {
            "location": {
                "id": str(loc.get("id") or loc.get("_id") or lid),
                "name": loc.get("name"),
                "email": loc.get("email"),
                "phone": loc.get("phone"),
                "companyId": loc.get("companyId"),
                "timezone": loc.get("timezone"),
                "settings": loc.get("settings"),
                "reseller": loc.get("reseller"),
                "permissions_enabled_count": sum(1 for v in perms.values() if v is True),
                "permissions_expected_count": len(UNNERFED_LOCATION_PERMISSIONS),
                "permissions_disabled": disabled_perms,
                "permissions_missing": missing_perms,
                "permissions_healthy": len(disabled_perms) == 0 and len(missing_perms) == 0,
            },
            "token_source": backend.token_source,
        }

    cid = _require_company_id(backend, company_id)
    res = backend.request("GET", "/locations/search", query={"companyId": cid, "limit": 100})
    raw_locs = res.get("locations", [])
    if not isinstance(raw_locs, list):
        raise HighLevelError("Expected locations list from /locations/search.")
    locations = []
    for item in raw_locs:
        if not isinstance(item, dict):
            continue
        lid = str(item.get("_id") or item.get("id") or "")
        locations.append(
            {
                "id": lid,
                "name": item.get("name"),
                "email": item.get("email"),
                "phone": item.get("phone"),
                "timezone": item.get("timezone"),
            }
        )
    return {
        "company_id": cid,
        "count": len(locations),
        "locations": locations,
        "token_source": backend.token_source,
    }


def make_location_rename_plan(
    backend: BackendClient,
    *,
    location_id: str,
    name: str,
    company_id: str | None = None,
) -> dict[str, Any]:
    lid = valid_id(location_id)
    clean_name = (name or "").strip()
    if not clean_name or len(clean_name) > 120:
        raise HighLevelError("Provide a non-empty --name of at most 120 characters.")
    res = backend.request("GET", f"/locations/{lid}")
    loc = res.get("location", res)
    if not isinstance(loc, dict):
        raise HighLevelError("Invalid location response from backend.")
    cid = str(loc.get("companyId") or "") or _require_company_id(backend, company_id)
    before_name = str(loc.get("name") or "")
    proposed_payload = {
        "companyId": cid,
        "name": clean_name,
    }
    plan_core = {
        "resource": "location",
        "action": "rename_location",
        "location_id": lid,
        "company_id": cid,
        "before": {"name": before_name},
        "proposed": proposed_payload,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_location_rename_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_location: str,
    confirm_plan: str,
) -> dict[str, Any]:
    lid = valid_id(str(plan["location_id"]))
    if valid_id(confirm_location) != lid:
        raise HighLevelError("--confirm-location does not match the previewed location_id.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    put_res = backend.request("PUT", f"/locations/{lid}", body=plan["proposed"])
    put_loc = put_res.get("location", put_res) if isinstance(put_res, dict) else {}
    actual_name = put_loc.get("name") if isinstance(put_loc, dict) else None
    if actual_name != plan["proposed"]["name"]:
        readback_res = backend.request("GET", f"/locations/{lid}")
        loc = readback_res.get("location", readback_res)
        actual_name = loc.get("name") if isinstance(loc, dict) else None
    verified = actual_name == plan["proposed"]["name"]
    if not verified:
        raise HighLevelError(f"Location rename readback mismatch: expected '{plan['proposed']['name']}', got '{actual_name}'.")
    return {
        "mode": "applied",
        "action": "rename_location",
        "location_id": lid,
        "before": plan["before"],
        "after": {"name": actual_name},
        "verified": True,
        "token_source": backend.token_source,
    }


def make_location_unnerf_plan(
    backend: BackendClient,
    *,
    location_id: str | None = None,
    all_locations: bool = False,
    company_id: str | None = None,
) -> dict[str, Any]:
    cid = _require_company_id(backend, company_id)
    target_ids: list[str] = []
    if all_locations:
        loc_list = list_agency_locations(backend, company_id=cid)["locations"]
        target_ids = [valid_id(item["id"]) for item in loc_list]
    elif location_id:
        target_ids = [valid_id(location_id)]
    else:
        raise HighLevelError("Pass --location-id <id> or --all-locations.")

    targets = []
    for lid in target_ids:
        res = backend.request("GET", f"/locations/{lid}")
        loc = res.get("location", res)
        if not isinstance(loc, dict):
            raise HighLevelError(f"Invalid location response for {lid}.")
        loc_cid = str(loc.get("companyId") or "") or cid
        existing_perms = loc.get("permissions") if isinstance(loc.get("permissions"), dict) else {}
        disabled = [k for k, v in existing_perms.items() if v is False]
        missing = [
            k for k, expected in UNNERFED_LOCATION_PERMISSIONS.items()
            if expected is True and existing_perms.get(k) is not True
        ]
        merged_perms = {**existing_perms, **UNNERFED_LOCATION_PERMISSIONS}
        targets.append(
            {
                "location_id": lid,
                "location_name": loc.get("name"),
                "company_id": loc_cid,
                "already_healthy": len(disabled) == 0 and len(missing) == 0,
                "before_enabled_count": sum(1 for v in existing_perms.values() if v is True),
                "before_disabled": disabled,
                "before_missing_count": len(missing),
                "proposed_payload": {
                    "companyId": loc_cid,
                    "permissions": merged_perms,
                },
            }
        )
    plan_core = {
        "resource": "location_permissions",
        "action": "unnerf_locations",
        "company_id": cid,
        "target_count": len(targets),
        "targets": targets,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_location_unnerf_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    results = []
    for target in plan.get("targets", []):
        lid = valid_id(target["location_id"])
        backend.request("PUT", f"/locations/{lid}", body=target["proposed_payload"])
        after = list_agency_locations(backend, location_id=lid)["location"]
        if not after.get("permissions_healthy"):
            raise HighLevelError(f"Location permissions readback failed for location {lid}.")
        results.append(
            {
                "location_id": lid,
                "location_name": after.get("name"),
                "permissions_enabled_count": after.get("permissions_enabled_count"),
                "verified": True,
            }
        )
    return {
        "mode": "applied",
        "action": "unnerf_locations",
        "company_id": plan.get("company_id"),
        "count": len(results),
        "verified": True,
        "results": results,
    }


def list_agency_users(
    backend: BackendClient,
    *,
    company_id: str | None = None,
) -> dict[str, Any]:
    cid = _require_company_id(backend, company_id)
    res = backend.request("GET", "/users/search", query={"companyId": cid, "limit": 100})
    raw_users = res.get("users", [])
    if not isinstance(raw_users, list):
        raise HighLevelError("Expected users list from /users/search.")

    users = []
    by_base_email: dict[str, list[dict[str, Any]]] = {}
    for u in raw_users:
        if not isinstance(u, dict):
            continue
        uid = str(u.get("id") or u.get("_id") or "")
        email = str(u.get("email") or "")
        roles = u.get("roles") if isinstance(u.get("roles"), dict) else {}
        loc_ids = [str(x) for x in (roles.get("locationIds") or [])]
        scopes = u.get("scopes") if isinstance(u.get("scopes"), list) else []
        entry = {
            "id": uid,
            "name": u.get("name"),
            "email": email,
            "base_email": _canonical_base_email(email),
            "is_plus_alias": "+" in email,
            "type": roles.get("type"),
            "role": roles.get("role"),
            "location_count": len(loc_ids),
            "location_ids": loc_ids,
            "scopes_count": len(scopes),
            "deleted": bool(u.get("deleted", False)),
        }
        users.append(entry)
        if entry["base_email"] and not entry["deleted"]:
            by_base_email.setdefault(entry["base_email"], []).append(entry)

    alias_pairs = []
    for base_email, group in by_base_email.items():
        if len(group) > 1:
            loc_sets = [set(item["location_ids"]) for item in group if item["type"] == "account"]
            in_sync = len(loc_sets) <= 1 or all(s == loc_sets[0] for s in loc_sets[1:])
            union_locs = sorted({loc for item in group for loc in item["location_ids"]})
            alias_pairs.append(
                {
                    "base_email": base_email,
                    "location_ids_in_sync": in_sync,
                    "union_location_ids": union_locs,
                    "records": [
                        {
                            "id": item["id"],
                            "email": item["email"],
                            "type": item["type"],
                            "role": item["role"],
                            "location_ids": item["location_ids"],
                        }
                        for item in group
                    ],
                }
            )

    return {
        "company_id": cid,
        "count": len(users),
        "users": users,
        "alias_pairs": alias_pairs,
        "token_source": backend.token_source,
    }


def _resolve_user_id(
    backend: BackendClient,
    *,
    user_id: str | None = None,
    email: str | None = None,
    company_id: str | None = None,
) -> str:
    if user_id:
        return valid_id(user_id)
    if not email:
        raise HighLevelError("Provide --user-id or --email.")
    directory = list_agency_users(backend, company_id=company_id)["users"]
    clean_email = email.strip().lower()
    matches = [u for u in directory if u["email"].lower() == clean_email]
    if not matches:
        raise HighLevelError(f"No user found matching email '{email}'.")
    return valid_id(matches[0]["id"])


def inspect_user(
    backend: BackendClient,
    *,
    user_id: str | None = None,
    email: str | None = None,
    company_id: str | None = None,
) -> dict[str, Any]:
    uid = _resolve_user_id(backend, user_id=user_id, email=email, company_id=company_id)
    user_doc = backend.request("GET", f"/users/{uid}")
    roles = user_doc.get("roles") if isinstance(user_doc.get("roles"), dict) else {}
    utype = str(roles.get("type") or "account")
    urole = str(roles.get("role") or "admin")
    loc_ids = [str(x) for x in (roles.get("locationIds") or [])]
    v1_perms = user_doc.get("permissions") if isinstance(user_doc.get("permissions"), dict) else {}
    v2_scopes = [str(s) for s in (user_doc.get("scopes") or [])]

    catalog_res = backend.request(
        "GET",
        "/users/permissions",
        query={"userId": uid, "type": utype, "role": urole},
    )
    raw_catalog = catalog_res.get("permissions", {})
    catalog_entries: list[tuple[str, dict[str, Any]]] = []
    if isinstance(raw_catalog, dict):
        for k, v in raw_catalog.items():
            if isinstance(v, dict):
                catalog_entries.append((str(k), v))
    elif isinstance(raw_catalog, list):
        for item in raw_catalog:
            if isinstance(item, dict) and item.get("id"):
                catalog_entries.append((str(item["id"]), item))

    excluded_readonly = {pair[0] for pair in MUTUALLY_EXCLUSIVE_V2_SCOPES}
    excluded_optional = set(AGENCY_ONLY_V2_SCOPES) if utype == "agency" else set()
    enabled_catalog_ids = {
        cid for cid, meta in catalog_entries if meta.get("enabled") is True
    }
    disabled_catalog_items = [
        cid
        for cid, meta in catalog_entries
        if meta.get("enabled") is not True
        and cid not in excluded_readonly
        and cid not in excluded_optional
    ]
    assigned_data_only_items = [
        cid
        for cid, meta in catalog_entries
        if isinstance(meta.get("userConfig"), dict)
        and meta["userConfig"].get("assignedToSupported") is True
    ]

    v1_mismatches = {}
    if utype == "account" and urole == "admin":
        for k, expected in UNNERFED_V1_PERMISSIONS.items():
            actual = v1_perms.get(k)
            if actual != expected:
                v1_mismatches[k] = {"actual": actual, "expected": expected}

    expected_v2 = [s for s in CRITICAL_ACCOUNT_ADMIN_V2_SCOPES if s not in excluded_readonly]
    effective_scope_set = set(v2_scopes) | enabled_catalog_ids
    for canonical_scope, aliases in SCOPE_EQUIVALENTS.items():
        if any(a in effective_scope_set for a in aliases):
            effective_scope_set.add(canonical_scope)
    missing_critical_v2 = (
        [s for s in expected_v2 if s not in effective_scope_set]
        if (utype == "account" and urole == "admin")
        else []
    )

    return {
        "user": {
            "id": uid,
            "name": user_doc.get("name"),
            "email": user_doc.get("email"),
            "type": utype,
            "role": urole,
            "location_ids": loc_ids,
            "scopes_count": len(v2_scopes),
            "catalog_total": len(catalog_entries),
            "catalog_enabled_count": len(enabled_catalog_ids),
            "catalog_disabled_items": disabled_catalog_items,
            "assigned_data_only_restrictions": assigned_data_only_items,
            "v1_permission_mismatches": v1_mismatches,
            "missing_critical_v2_scopes": missing_critical_v2,
            "healthy": (
                len(disabled_catalog_items) == 0
                and len(assigned_data_only_items) == 0
                and len(missing_critical_v2) == 0
                and v1_perms.get("assignedDataOnly") is False
            ),
        },
        "token_source": backend.token_source,
    }


def make_user_sync_locations_plan(
    backend: BackendClient,
    *,
    user_id: str,
    location_ids: list[str] | None = None,
    from_user_id: str | None = None,
    company_id: str | None = None,
) -> dict[str, Any]:
    cid = _require_company_id(backend, company_id)
    uid = valid_id(user_id)
    user_doc = backend.request("GET", f"/users/{uid}")
    roles = user_doc.get("roles") if isinstance(user_doc.get("roles"), dict) else {}
    utype = str(roles.get("type") or "account")
    urole = str(roles.get("role") or "admin")
    before_locs = [str(x) for x in (roles.get("locationIds") or [])]

    if from_user_id:
        src_uid = valid_id(from_user_id)
        src_doc = backend.request("GET", f"/users/{src_uid}")
        src_roles = src_doc.get("roles") if isinstance(src_doc.get("roles"), dict) else {}
        target_locs = [valid_id(str(x)) for x in (src_roles.get("locationIds") or [])]
    elif location_ids:
        target_locs = [valid_id(x) for x in location_ids]
    else:
        raise HighLevelError("Provide --location-ids or --from-user-id to build a location sync plan.")

    deduped_locs = list(dict.fromkeys(target_locs))
    proposed_payload = {
        "companyId": cid,
        "source": "agency_team",
        "type": utype,
        "role": urole,
        "locationIds": deduped_locs,
    }
    plan_core = {
        "resource": "user_locations",
        "action": "sync_locations",
        "company_id": cid,
        "user_id": uid,
        "email": user_doc.get("email"),
        "before_location_ids": before_locs,
        "proposed_payload": proposed_payload,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_user_sync_locations_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_user: str,
    confirm_plan: str,
) -> dict[str, Any]:
    uid = valid_id(str(plan.get("user_id", "")))
    if confirm_user != uid:
        raise HighLevelError("--confirm-user does not match the target user_id.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    payload = plan["proposed_payload"]
    backend.request("PUT", f"/users/{uid}", body=payload)
    readback_doc = backend.request("GET", f"/users/{uid}")
    roles = readback_doc.get("roles") if isinstance(readback_doc.get("roles"), dict) else {}
    after_locs = [str(x) for x in (roles.get("locationIds") or [])]
    expected_set = set(payload["locationIds"])
    verified = set(after_locs) == expected_set
    if not verified:
        raise HighLevelError("User location sync readback did not match the requested locationIds.")
    return {
        "mode": "applied",
        "action": "sync_locations",
        "user_id": uid,
        "email": readback_doc.get("email"),
        "verified": True,
        "location_ids": after_locs,
    }


def make_user_unnerf_plan(
    backend: BackendClient,
    *,
    user_id: str | None = None,
    email: str | None = None,
    company_id: str | None = None,
) -> dict[str, Any]:
    cid = _require_company_id(backend, company_id)
    uid = _resolve_user_id(backend, user_id=user_id, email=email, company_id=cid)
    inspected = inspect_user(backend, user_id=uid, company_id=cid)["user"]
    utype = str(inspected["type"])
    urole = str(inspected["role"])

    catalog_res = backend.request(
        "GET",
        "/users/permissions",
        query={"userId": uid, "type": utype, "role": urole},
    )
    raw_catalog = catalog_res.get("permissions", {})
    excluded_readonly = {pair[0] for pair in MUTUALLY_EXCLUSIVE_V2_SCOPES}
    excluded_optional = set(AGENCY_ONLY_V2_SCOPES) if utype == "agency" else set()
    if isinstance(raw_catalog, dict) and raw_catalog:
        target_scopes = [
            str(k)
            for k, meta in raw_catalog.items()
            if str(k) not in excluded_readonly
            and (str(k) not in excluded_optional or (isinstance(meta, dict) and meta.get("enabled") is True))
        ]
    else:
        target_scopes = [s for s in CRITICAL_ACCOUNT_ADMIN_V2_SCOPES if s not in excluded_readonly]

    proposed_payload = {
        "companyId": cid,
        "source": "agency_team",
        "type": utype,
        "role": urole,
        "locationIds": inspected["location_ids"],
        "permissions": dict(UNNERFED_V1_PERMISSIONS),
        "scopes": target_scopes,
        "scopesAssignedToOnly": [],
    }
    plan_core = {
        "resource": "user_permissions",
        "action": "unnerf_user",
        "company_id": cid,
        "user_id": uid,
        "email": inspected["email"],
        "already_healthy": inspected["healthy"],
        "before_summary": {
            "catalog_disabled_items": inspected["catalog_disabled_items"],
            "assigned_data_only_restrictions": inspected["assigned_data_only_restrictions"],
            "v1_permission_mismatches": inspected["v1_permission_mismatches"],
            "missing_critical_v2_scopes": inspected["missing_critical_v2_scopes"],
        },
        "proposed_payload": proposed_payload,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_user_unnerf_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_user: str,
    confirm_plan: str,
) -> dict[str, Any]:
    uid = valid_id(str(plan.get("user_id", "")))
    if confirm_user != uid:
        raise HighLevelError("--confirm-user does not match the target user_id.")
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    backend.request("PUT", f"/users/{uid}", body=plan["proposed_payload"])
    after = inspect_user(backend, user_id=uid, company_id=plan["company_id"])["user"]
    if not after["healthy"]:
        raise HighLevelError("User unnerf readback still shows disabled scopes or restrictions.")
    return {
        "mode": "applied",
        "action": "unnerf_user",
        "user_id": uid,
        "email": after["email"],
        "verified": True,
        "scopes_count": after["scopes_count"],
        "catalog_enabled_count": after["catalog_enabled_count"],
    }


def inspect_smtp_status(
    backend: BackendClient,
    *,
    location_id: str | None = None,
    all_locations: bool = False,
    company_id: str | None = None,
) -> dict[str, Any]:
    target_locations: list[dict[str, Any]] = []
    if all_locations:
        loc_list = list_agency_locations(backend, company_id=company_id)["locations"]
        target_locations = [{"id": item["id"], "name": item.get("name")} for item in loc_list]
    elif location_id:
        lid = valid_id(location_id)
        target_locations = [{"id": lid, "name": None}]
    else:
        raise HighLevelError("Pass --location-id <id> or --all-locations.")

    items = []
    all_unlocked = True
    for loc in target_locations:
        lid = valid_id(loc["id"])
        onload = backend.request("GET", "/email-isv/onload", query={"locationId": lid})
        block_add = onload.get("blockAddSmtp")
        unlocked = block_add is False
        if not unlocked:
            all_unlocked = False
        items.append(
            {
                "location_id": lid,
                "location_name": loc.get("name"),
                "blockAddSmtp": block_add,
                "add_service_unlocked": unlocked,
                "hasLcEmail": onload.get("hasLcEmail"),
                "domain": onload.get("domain"),
            }
        )
    return {
        "ok": all_unlocked,
        "count": len(items),
        "locations": items,
        "token_source": backend.token_source,
    }


def make_smtp_unlock_plan(
    backend: BackendClient,
    *,
    location_id: str | None = None,
    all_locations: bool = False,
    company_id: str | None = None,
) -> dict[str, Any]:
    cid = _require_company_id(backend, company_id)
    status = inspect_smtp_status(
        backend,
        location_id=location_id,
        all_locations=all_locations,
        company_id=cid,
    )
    targets = [
        {
            "location_id": item["location_id"],
            "location_name": item.get("location_name"),
            "before_blockAddSmtp": item.get("blockAddSmtp"),
            "already_unlocked": item.get("add_service_unlocked"),
            "location_request": {
                "method": "PUT",
                "path": f"/email-isv/Setting/feature/location/{item['location_id']}",
                "payload": {"blockAddSmtp": False},
            },
        }
        for item in status["locations"]
    ]
    plan_core = {
        "resource": "custom_smtp_lock",
        "action": "unlock_custom_smtp",
        "company_id": cid,
        "agency_request": {
            "method": "PUT",
            "path": f"/email-isv/Setting/feature/company/{cid}",
            "payload": {"emailIsvSettings": {"blockAddSmtp": False}},
        },
        "target_count": len(targets),
        "targets": targets,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_smtp_unlock_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    cid = valid_id(str(plan["company_id"]))
    backend.request(
        "PUT",
        f"/email-isv/Setting/feature/company/{cid}",
        body={"emailIsvSettings": {"blockAddSmtp": False}},
    )
    results = []
    for target in plan.get("targets", []):
        lid = valid_id(target["location_id"])
        backend.request(
            "PUT",
            f"/email-isv/Setting/feature/location/{lid}",
            body={"blockAddSmtp": False},
        )
        onload = backend.request("GET", "/email-isv/onload", query={"locationId": lid})
        verified = onload.get("blockAddSmtp") is False
        if not verified:
            raise HighLevelError(f"Custom SMTP unlock readback failed for location {lid}.")
        results.append(
            {
                "location_id": lid,
                "location_name": target.get("location_name"),
                "blockAddSmtp": onload.get("blockAddSmtp"),
                "verified": True,
            }
        )
    return {
        "mode": "applied",
        "action": "unlock_custom_smtp",
        "company_id": cid,
        "count": len(results),
        "verified": True,
        "results": results,
    }


def _collect_location_dashboards(dash_res: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    data = dash_res.get("data") if isinstance(dash_res.get("data"), dict) else {}
    default_id = str(data.get("defaultDashboardId") or "")
    seen: dict[str, dict[str, Any]] = {}

    for list_key in ("sharedDashboards", "dashboard"):
        raw_list = data.get(list_key)
        if not isinstance(raw_list, list):
            continue
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            did = str(item.get("_id") or item.get("id") or "")
            if not did:
                continue
            seen[did] = {
                "id": did,
                "title": item.get("title") or "Dashboard",
                "is_default": bool(item.get("isDefault")) or (did == default_id),
            }

    if default_id and default_id not in seen:
        seen[default_id] = {
            "id": default_id,
            "title": "Default Dashboard",
            "is_default": True,
        }
    return default_id, list(seen.values())


def inspect_dashboard_permissions(
    backend: BackendClient,
    *,
    location_id: str | None = None,
    all_locations: bool = False,
    company_id: str | None = None,
) -> dict[str, Any]:
    target_locations: list[dict[str, Any]] = []
    if all_locations:
        loc_list = list_agency_locations(backend, company_id=company_id)["locations"]
        target_locations = [{"id": item["id"], "name": item.get("name")} for item in loc_list]
    elif location_id:
        lid = valid_id(location_id)
        target_locations = [{"id": lid, "name": None}]
    else:
        raise HighLevelError("Pass --location-id <id> or --all-locations.")

    results = []
    all_healthy = True
    for loc in target_locations:
        lid = valid_id(loc["id"])
        dash_res = backend.request("GET", "/reporting/dashboards", query={"locationId": lid})
        default_id, dash_items = _collect_location_dashboards(dash_res)

        if not dash_items:
            all_healthy = False
            results.append(
                {
                    "location_id": lid,
                    "location_name": loc.get("name"),
                    "default_dashboard_id": None,
                    "dashboard_id": None,
                    "dashboard_title": None,
                    "healthy": False,
                    "error": "No dashboards returned for location.",
                }
            )
            continue

        for d_item in dash_items:
            did = valid_id(d_item["id"])
            perm_res = backend.request(
                "GET",
                f"/reporting/dashboards/{did}/permissions",
                query={"locationId": lid},
            )
            perm_data = perm_res.get("data") if isinstance(perm_res.get("data"), dict) else {}
            perms = perm_data.get("permission") if isinstance(perm_data.get("permission"), list) else []
            perm_map = {
                str(p.get("role", "")): str(p.get("permission", ""))
                for p in perms
                if isinstance(p, dict)
            }
            admin_full = perm_map.get("account_admin") == "full"
            user_full = perm_map.get("account_user") == "full"
            agency_full = perm_map.get("agency_user") == "full"
            is_private = bool(perm_data.get("isPrivate", False))
            healthy = admin_full and user_full and agency_full and not is_private
            if not healthy:
                all_healthy = False

            results.append(
                {
                    "location_id": lid,
                    "location_name": loc.get("name"),
                    "default_dashboard_id": default_id,
                    "dashboard_id": did,
                    "dashboard_title": d_item.get("title"),
                    "is_default": d_item.get("is_default", did == default_id),
                    "dashboard_count": len(dash_items),
                    "is_private": is_private,
                    "permission_map": perm_map,
                    "account_admin_full": admin_full,
                    "account_user_full": user_full,
                    "agency_user_full": agency_full,
                    "healthy": healthy,
                }
            )

    return {
        "ok": all_healthy,
        "count": len(results),
        "dashboards": results,
        "token_source": backend.token_source,
    }


def make_unlock_dashboards_plan(
    backend: BackendClient,
    *,
    location_id: str | None = None,
    all_locations: bool = False,
    company_id: str | None = None,
) -> dict[str, Any]:
    inspected = inspect_dashboard_permissions(
        backend,
        location_id=location_id,
        all_locations=all_locations,
        company_id=company_id,
    )
    targets = []
    for item in inspected["dashboards"]:
        did = item.get("dashboard_id") or item.get("default_dashboard_id")
        if not did:
            continue
        lid = item["location_id"]
        targets.append(
            {
                "location_id": lid,
                "location_name": item.get("location_name"),
                "dashboard_id": did,
                "dashboard_title": item.get("dashboard_title"),
                "is_default": item.get("is_default", True),
                "before_permission_map": item.get("permission_map", {}),
                "already_healthy": item.get("healthy", False),
                "proposed_payload": {
                    "locationId": lid,
                    "isPrivate": False,
                    "permissionAccess": list(DEFAULT_DASHBOARD_PERMISSION_ACCESS),
                },
            }
        )
    plan_core = {
        "resource": "dashboard_permissions",
        "action": "unlock_default_dashboards",
        "target_count": len(targets),
        "targets": targets,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_unlock_dashboards_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    applied_results = []
    for target in plan.get("targets", []):
        lid = valid_id(target["location_id"])
        did = valid_id(target["dashboard_id"])
        payload = target["proposed_payload"]
        backend.request(
            "POST",
            f"/reporting/dashboards/{did}/permissions",
            body=payload,
            query={"locationId": lid},
        )
        readback = backend.request(
            "GET",
            f"/reporting/dashboards/{did}/permissions",
            query={"locationId": lid},
        )
        pdata = readback.get("data") if isinstance(readback.get("data"), dict) else {}
        perms = pdata.get("permission") if isinstance(pdata.get("permission"), list) else []
        perm_map = {
            str(p.get("role", "")): str(p.get("permission", ""))
            for p in perms
            if isinstance(p, dict)
        }
        verified = (
            perm_map.get("account_admin") == "full"
            and perm_map.get("account_user") == "full"
            and perm_map.get("agency_user") == "full"
        )
        if not verified:
            raise HighLevelError(
                f"Dashboard permission readback failed for location {lid} dashboard {did}."
            )
        applied_results.append(
            {
                "location_id": lid,
                "location_name": target.get("location_name"),
                "dashboard_id": did,
                "dashboard_title": target.get("dashboard_title"),
                "verified": True,
                "permission_map": perm_map,
            }
        )

    return {
        "mode": "applied",
        "action": "unlock_default_dashboards",
        "count": len(applied_results),
        "verified": True,
        "results": applied_results,
    }


def inspect_rebilling_status(
    backend: BackendClient,
    *,
    location_id: str | None = None,
    all_locations: bool = False,
    company_id: str | None = None,
    markup: int = 5,
) -> dict[str, Any]:
    target_locations: list[dict[str, Any]] = []
    if all_locations:
        loc_list = list_agency_locations(backend, company_id=company_id)["locations"]
        target_locations = [{"id": item["id"], "name": item.get("name")} for item in loc_list]
    elif location_id:
        lid = valid_id(location_id)
        target_locations = [{"id": lid, "name": None}]
    else:
        raise HighLevelError("Pass --location-id <id> or --all-locations.")

    expected_markup = int(markup)
    items = []
    all_healthy = True
    for loc_ref in target_locations:
        lid = valid_id(loc_ref["id"])
        loc_res = backend.request("GET", f"/locations/{lid}")
        loc = loc_res.get("location", loc_res)
        if not isinstance(loc, dict):
            raise HighLevelError(f"Invalid location response for {lid}.")
        loc_name = loc.get("name") or loc_ref.get("name")
        loc_cid = str(loc.get("companyId") or "") or _require_company_id(backend, company_id)
        settings = loc.get("settings") if isinstance(loc.get("settings"), dict) else {}
        saas_settings = settings.get("saasSettings") if isinstance(settings.get("saasSettings"), dict) else {}
        saas_mode = str(saas_settings.get("saasMode") or "not_activated")
        loc_tw = saas_settings.get("twilioRebilling") if isinstance(saas_settings.get("twilioRebilling"), dict) else {}
        loc_mg = saas_settings.get("mailgunRebilling") if isinstance(saas_settings.get("mailgunRebilling"), dict) else {}

        meta_res = backend.request("GET", f"/saas-api/location-metadata/{lid}")
        meta = meta_res.get("data", meta_res) if isinstance(meta_res, dict) else {}
        if not isinstance(meta, dict):
            meta = {}
        att_cfg = meta.get("attachedRebillingConfig") if isinstance(meta.get("attachedRebillingConfig"), dict) else {}
        att_phone = att_cfg.get("Phone") if isinstance(att_cfg.get("Phone"), dict) else {}
        att_email = att_cfg.get("Email") if isinstance(att_cfg.get("Email"), dict) else {}
        meta_tw = meta.get("twilioRebilling") if isinstance(meta.get("twilioRebilling"), dict) else {}
        meta_mg = meta.get("mailgunRebilling") if isinstance(meta.get("mailgunRebilling"), dict) else {}

        v2_res = backend.request("GET", f"/saas-billing-v2/billing-config/LOCATION/{lid}")
        v2_data = v2_res.get("data", []) if isinstance(v2_res, dict) else []
        v2_map: dict[str, dict[str, Any]] = {}
        if isinstance(v2_data, list):
            for p_item in v2_data:
                if isinstance(p_item, dict) and p_item.get("product"):
                    cfg = p_item.get("config") if isinstance(p_item.get("config"), dict) else {}
                    v2_map[str(p_item["product"])] = cfg

        expected_v2_enabled = saas_mode in {"activated", "setup_pending"}
        v2_mismatches = []
        for key in SAAS_BILLING_V2_KEYS:
            cfg = v2_map.get(key, {})
            if (
                cfg.get("markup") != expected_markup
                or bool(cfg.get("enabled")) is not expected_v2_enabled
                or cfg.get("optIn") is not True
            ):
                v2_mismatches.append(
                    {
                        "product": key,
                        "enabled": cfg.get("enabled"),
                        "optIn": cfg.get("optIn"),
                        "markup": cfg.get("markup"),
                    }
                )

        expected_active_flag = saas_mode == "activated"
        loc_tw_ok = loc_tw.get("markup") == expected_markup and bool(loc_tw.get("enabled")) is expected_active_flag
        loc_mg_ok = loc_mg.get("markup") == expected_markup and bool(loc_mg.get("enabled")) is expected_active_flag
        att_ok = (
            att_phone.get("markup") == expected_markup
            and att_phone.get("enabled") is True
            and att_email.get("markup") == expected_markup
            and att_email.get("enabled") is True
        )
        meta_tw_ok = meta_tw.get("markup") == expected_markup
        meta_mg_ok = meta_mg.get("markup") == expected_markup
        healthy = loc_tw_ok and loc_mg_ok and att_ok and meta_tw_ok and meta_mg_ok and len(v2_mismatches) == 0
        if not healthy:
            all_healthy = False

        items.append(
            {
                "location_id": lid,
                "location_name": loc_name,
                "company_id": loc_cid,
                "saas_mode": saas_mode,
                "stripe_customer_id": saas_settings.get("stripeCustomerId") or meta.get("stripeCustomerId"),
                "expected_markup": expected_markup,
                "expected_multiplier": markup_to_multiplier(expected_markup),
                "location_twilio_rebilling": loc_tw,
                "location_mailgun_rebilling": loc_mg,
                "metadata_attached_rebilling": att_cfg,
                "metadata_twilio_rebilling": meta_tw,
                "metadata_mailgun_rebilling": meta_mg,
                "saas_billing_v2_total": len(SAAS_BILLING_V2_KEYS),
                "saas_billing_v2_mismatches": v2_mismatches,
                "healthy": healthy,
            }
        )

    return {
        "ok": all_healthy,
        "count": len(items),
        "expected_markup": expected_markup,
        "expected_multiplier": markup_to_multiplier(expected_markup),
        "locations": items,
        "token_source": backend.token_source,
    }


def make_rebilling_sync_plan(
    backend: BackendClient,
    *,
    location_id: str | None = None,
    all_locations: bool = False,
    company_id: str | None = None,
    markup: int = 5,
) -> dict[str, Any]:
    cid = _require_company_id(backend, company_id)
    expected_markup = int(markup)
    multiplier = markup_to_multiplier(expected_markup)
    mailgun_price = round(0.000675 * multiplier, 8)
    status = inspect_rebilling_status(
        backend,
        location_id=location_id,
        all_locations=all_locations,
        company_id=cid,
        markup=expected_markup,
    )
    keys_csv = ",".join(SAAS_BILLING_V2_KEYS)
    targets = []
    for item in status["locations"]:
        lid = item["location_id"]
        loc_cid = item.get("company_id") or cid
        saas_mode = item.get("saas_mode") or "not_activated"
        active_flag = saas_mode == "activated"
        v2_enabled_flag = saas_mode in {"activated", "setup_pending"}
        targets.append(
            {
                "location_id": lid,
                "location_name": item.get("location_name"),
                "company_id": loc_cid,
                "saas_mode": saas_mode,
                "already_healthy": item.get("healthy", False),
                "before_summary": {
                    "location_twilio_rebilling": item.get("location_twilio_rebilling"),
                    "location_mailgun_rebilling": item.get("location_mailgun_rebilling"),
                    "saas_billing_v2_mismatch_count": len(item.get("saas_billing_v2_mismatches") or []),
                },
                "requests": {
                    "saas_billing_v2": {
                        "method": "PUT",
                        "path": f"/saas-billing-v2/billing-config/group/{lid}/{keys_csv}",
                        "payload": {
                            "entityType": "LOCATION",
                            "enabled": v2_enabled_flag,
                            "optIn": True,
                            "markups": {k: expected_markup for k in SAAS_BILLING_V2_KEYS},
                        },
                    },
                    "twilio_rebilling": (
                        {
                            "method": "POST",
                            "path": f"/saas_service/saas-config/{lid}/update-twilio-rebilling",
                            "payload": {"enabled": True, "markup": expected_markup},
                        }
                        if active_flag
                        else None
                    ),
                    "location_saas_settings": {
                        "method": "PUT",
                        "path": f"/locations/{lid}",
                        "payload": {
                            "companyId": loc_cid,
                            "settings": {
                                "saasSettings": {
                                    "twilioRebilling": {"enabled": active_flag, "markup": expected_markup},
                                    "mailgunRebilling": {
                                        "enabled": active_flag,
                                        "markup": expected_markup,
                                        "price": mailgun_price,
                                    },
                                },
                            },
                        },
                    },
                    "location_metadata": {
                        "method": "PUT",
                        "path": f"/saas-api/location-metadata/{lid}",
                        "payload": {
                            "attachedRebillingConfig": {
                                "Phone": {"enabled": True, "markup": expected_markup},
                                "Email": {
                                    "enabled": True,
                                    "markup": expected_markup,
                                    "price": mailgun_price,
                                },
                            },
                            "twilioRebilling": {"enabled": active_flag, "markup": expected_markup},
                            "mailgunRebilling": {
                                "enabled": active_flag,
                                "markup": expected_markup,
                                "price": mailgun_price,
                            },
                        },
                    },
                },
            }
        )
    plan_core = {
        "resource": "rebilling_config",
        "action": "sync_rebilling",
        "company_id": cid,
        "markup": expected_markup,
        "ui_multiplier": multiplier,
        "target_count": len(targets),
        "targets": targets,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_rebilling_sync_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    expected_markup = int(plan.get("markup", 5))
    results = []
    for target in plan.get("targets", []):
        lid = valid_id(target["location_id"])
        reqs = target["requests"]
        v2_req = reqs["saas_billing_v2"]
        backend.request(v2_req["method"], v2_req["path"], body=v2_req["payload"])

        tw_req = reqs.get("twilio_rebilling")
        if isinstance(tw_req, dict):
            backend.request(tw_req["method"], tw_req["path"], body=tw_req["payload"])

        loc_req = reqs["location_saas_settings"]
        backend.request(loc_req["method"], loc_req["path"], body=loc_req["payload"])

        meta_req = reqs["location_metadata"]
        backend.request(meta_req["method"], meta_req["path"], body=meta_req["payload"])

        after = inspect_rebilling_status(
            backend,
            location_id=lid,
            company_id=plan.get("company_id"),
            markup=expected_markup,
        )["locations"][0]
        if not after.get("healthy"):
            raise HighLevelError(f"Rebilling sync readback failed for location {lid}.")
        results.append(
            {
                "location_id": lid,
                "location_name": after.get("location_name"),
                "saas_mode": after.get("saas_mode"),
                "markup": expected_markup,
                "verified": True,
            }
        )

    return {
        "mode": "applied",
        "action": "sync_rebilling",
        "company_id": plan.get("company_id"),
        "markup": expected_markup,
        "ui_multiplier": plan.get("ui_multiplier"),
        "count": len(results),
        "verified": True,
        "results": results,
    }


def list_private_integrations(
    backend: BackendClient,
    *,
    location_id: str,
) -> dict[str, Any]:
    lid = valid_id(location_id)
    raw = backend.request("GET", f"/marketplace/private-integration/location/{lid}")
    records = raw if isinstance(raw, list) else (raw.get("integrations") or raw.get("data") or [])
    items = []
    if isinstance(records, list):
        for r in records:
            if not isinstance(r, dict):
                continue
            items.append(
                {
                    "id": str(r.get("_id") or r.get("id") or ""),
                    "name": r.get("name"),
                    "description": r.get("description"),
                    "active_token_masked": r.get("activeToken"),
                    "scopes": r.get("scopes") or [],
                    "scopes_count": len(r.get("scopes") or []),
                    "created_at": r.get("createdAt"),
                    "updated_at": r.get("updatedAt"),
                }
            )
    return {
        "location_id": lid,
        "count": len(items),
        "private_integrations": items,
        "token_source": backend.token_source,
    }


def inspect_email_domains(
    backend: BackendClient,
    *,
    location_id: str,
    company_id: str | None = None,
) -> dict[str, Any]:
    lid = valid_id(location_id)
    cid = _require_company_id(backend, company_id)
    onload = backend.request("GET", "/email-isv/onload", query={"locationId": lid})
    domains_raw = backend.request(
        "GET",
        "/email-isv/feature/domain/list",
        query={"locationId": lid, "companyId": cid},
    )
    mailgun_raw = backend.request(
        "GET",
        "/conversations/providers/mailgun/fetch",
        query={"locationId": lid},
    )
    domains = domains_raw if isinstance(domains_raw, list) else (domains_raw.get("domains") or domains_raw.get("data") or [])
    return {
        "location_id": lid,
        "company_id": cid,
        "has_lc_email": onload.get("hasLcEmail"),
        "block_add_smtp": onload.get("blockAddSmtp"),
        "default_domain": onload.get("domain"),
        "dedicated_domains": domains if isinstance(domains, list) else [],
        "mailgun_provider": mailgun_raw if isinstance(mailgun_raw, dict) else {},
        "token_source": backend.token_source,
    }


def live_agency_audit(
    backend: BackendClient,
    *,
    company_id: str | None = None,
    markup: int = 5,
) -> dict[str, Any]:
    """Run a complete 5-layer location permission, user scope/alias, dashboard RBAC, Custom SMTP, and rebilling audit across the live HighLevel agency."""
    cid = _require_company_id(backend, company_id)
    issues: list[dict[str, Any]] = []

    # Layer 1: Locations and location-level feature flags (all 40 boolean switches)
    loc_summary = list_agency_locations(backend, company_id=cid)
    locations_detail = []
    for item in loc_summary["locations"]:
        lid = item["id"]
        loc_info = list_agency_locations(backend, location_id=lid)["location"]
        locations_detail.append(loc_info)
        if not loc_info.get("permissions_healthy"):
            issues.append(
                {
                    "layer": "location_permissions",
                    "location_id": lid,
                    "location_name": loc_info.get("name"),
                    "permissions_enabled_count": loc_info.get("permissions_enabled_count"),
                    "permissions_disabled": loc_info.get("permissions_disabled"),
                    "permissions_missing_count": len(loc_info.get("permissions_missing") or []),
                    "detail": (
                        f"Location has {loc_info.get('permissions_enabled_count')}/{loc_info.get('permissions_expected_count')} "
                        f"enabled feature flags (disabled={loc_info.get('permissions_disabled')})."
                    ),
                }
            )

    # Layer 2: Users, V2 scopes, Only Assigned Data, and +hubpro alias location sync
    users_summary = list_agency_users(backend, company_id=cid)
    users_detail = []
    for u in users_summary["users"]:
        if u.get("deleted"):
            continue
        inspected = inspect_user(backend, user_id=u["id"])["user"]
        users_detail.append(inspected)
        if not inspected["healthy"]:
            issues.append(
                {
                    "layer": "user_scopes",
                    "user_id": inspected["id"],
                    "email": inspected["email"],
                    "type": inspected["type"],
                    "role": inspected["role"],
                    "disabled_catalog_items": inspected["catalog_disabled_items"],
                    "assigned_data_only_restrictions": inspected["assigned_data_only_restrictions"],
                    "missing_critical_v2_scopes": inspected["missing_critical_v2_scopes"],
                }
            )

    for pair in users_summary["alias_pairs"]:
        if not pair["location_ids_in_sync"]:
            issues.append(
                {
                    "layer": "user_alias_sync",
                    "base_email": pair["base_email"],
                    "detail": "Primary email and +hubpro alias have different locationIds.",
                    "records": pair["records"],
                    "union_location_ids": pair["union_location_ids"],
                }
            )

    # Layer 3: Reporting V2 per-dashboard RBAC across all dashboards in all sub-accounts
    dash_summary = inspect_dashboard_permissions(backend, all_locations=True, company_id=cid)
    for d in dash_summary["dashboards"]:
        if not d.get("healthy"):
            issues.append(
                {
                    "layer": "dashboard_rbac",
                    "location_id": d["location_id"],
                    "location_name": d.get("location_name"),
                    "dashboard_id": d.get("dashboard_id"),
                    "dashboard_title": d.get("dashboard_title"),
                    "permission_map": d.get("permission_map"),
                    "detail": "Dashboard is missing full RBAC for account_admin, account_user, or agency_user.",
                }
            )

    # Layer 4: Custom SMTP (Add Service) unlock status across all sub-accounts
    smtp_summary = inspect_smtp_status(backend, all_locations=True, company_id=cid)
    for s in smtp_summary["locations"]:
        if not s.get("add_service_unlocked"):
            issues.append(
                {
                    "layer": "custom_smtp_lock",
                    "location_id": s["location_id"],
                    "location_name": s.get("location_name"),
                    "blockAddSmtp": s.get("blockAddSmtp"),
                    "detail": "Custom SMTP (Add Service) is locked (blockAddSmtp != False).",
                }
            )

    # Layer 5: Live 4-store Rebilling markup & 14-product SaaS Billing v2 sync across all sub-accounts
    rebill_summary = inspect_rebilling_status(
        backend,
        all_locations=True,
        company_id=cid,
        markup=markup,
    )
    for r in rebill_summary["locations"]:
        if not r.get("healthy"):
            issues.append(
                {
                    "layer": "rebilling_config",
                    "location_id": r["location_id"],
                    "location_name": r.get("location_name"),
                    "saas_mode": r.get("saas_mode"),
                    "location_twilio_rebilling": r.get("location_twilio_rebilling"),
                    "location_mailgun_rebilling": r.get("location_mailgun_rebilling"),
                    "saas_billing_v2_mismatch_count": len(r.get("saas_billing_v2_mismatches") or []),
                    "detail": f"Location rebilling stores drifted from target markup={markup} ({markup_to_multiplier(markup)}x).",
                }
            )

    return {
        "ok": len(issues) == 0,
        "company_id": cid,
        "token_source": backend.token_source,
        "summary": {
            "locations_audited": len(locations_detail),
            "users_audited": len(users_detail),
            "alias_pairs_checked": len(users_summary["alias_pairs"]),
            "dashboards_audited": len(dash_summary["dashboards"]),
            "smtp_locations_audited": len(smtp_summary["locations"]),
            "rebilling_locations_audited": len(rebill_summary["locations"]),
            "issue_count": len(issues),
        },
        "issues": issues,
        "locations": locations_detail,
        "users": users_detail,
        "alias_pairs": users_summary["alias_pairs"],
        "dashboards": dash_summary["dashboards"],
        "smtp_locations": smtp_summary["locations"],
        "rebilling_locations": rebill_summary["locations"],
    }
