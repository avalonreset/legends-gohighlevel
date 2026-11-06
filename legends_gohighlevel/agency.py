"""Live agency, sub-account, user scope, Custom SMTP, and dashboard RBAC operations via HighLevel internal backend."""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .api import BackendClient, HighLevelError, _mask_token, save_subaccount_profile, valid_id
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
        for _ in range(4):
            if after.get("permissions_healthy"):
                break
            time.sleep(0.8)
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
    add_location_ids: list[str] | None = None,
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

    merged_locs = list(dict.fromkeys([*inspected["location_ids"], *[valid_id(x) for x in (add_location_ids or []) if x]]))
    proposed_payload = {
        "companyId": cid,
        "source": "agency_team",
        "type": utype,
        "role": urole,
        "locationIds": merged_locs,
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
    for _ in range(4):
        if after["healthy"]:
            break
        time.sleep(0.8)
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
    try:
        backend.request(
            "PUT",
            f"/email-isv/Setting/feature/company/{cid}",
            body={"emailIsvSettings": {"blockAddSmtp": False}},
        )
    except HighLevelError:
        pass
    results = []
    for target in plan.get("targets", []):
        lid = valid_id(target["location_id"])
        if not target.get("already_unlocked"):
            try:
                backend.request(
                    "PUT",
                    f"/email-isv/Setting/feature/location/{lid}",
                    body={"blockAddSmtp": False},
                )
            except HighLevelError:
                pass
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
            True
            if saas_mode == "not_activated" and not att_cfg
            else (
                att_phone.get("markup") == expected_markup
                and att_phone.get("enabled") is True
                and att_email.get("markup") == expected_markup
                and att_email.get("enabled") is True
            )
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
    enable_hold_if_needed: bool = True,
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
    stripe_connect_id = ""
    if enable_hold_if_needed and any(item.get("saas_mode") == "not_activated" for item in status["locations"]):
        try:
            comp_res = backend.request("GET", f"/companies/{cid}")
            comp = comp_res.get("company", comp_res) if isinstance(comp_res, dict) else {}
            stripe_connect_id = str(comp.get("stripeConnectId") or "").strip()
        except HighLevelError:
            stripe_connect_id = ""

    keys_csv = ",".join(SAAS_BILLING_V2_KEYS)
    targets = []
    for item in status["locations"]:
        lid = item["location_id"]
        loc_cid = item.get("company_id") or cid
        saas_mode = item.get("saas_mode") or "not_activated"
        will_enable_hold = bool(enable_hold_if_needed and saas_mode == "not_activated" and stripe_connect_id)
        effective_saas_mode = "setup_pending" if will_enable_hold else saas_mode
        active_flag = effective_saas_mode == "activated"
        v2_enabled_flag = effective_saas_mode in {"activated", "setup_pending"}
        loc_email = "support@rankyrank.com"
        if will_enable_hold:
            try:
                loc_doc = backend.request("GET", f"/locations/{lid}")
                loc_obj = loc_doc.get("location", loc_doc) if isinstance(loc_doc, dict) else {}
                loc_email = str(loc_obj.get("email") or "support@rankyrank.com").strip()
            except HighLevelError:
                pass
        targets.append(
            {
                "location_id": lid,
                "location_name": item.get("location_name"),
                "company_id": loc_cid,
                "saas_mode": saas_mode,
                "effective_saas_mode": effective_saas_mode,
                "already_healthy": bool(item.get("healthy", False) and not will_enable_hold),
                "before_summary": {
                    "location_twilio_rebilling": item.get("location_twilio_rebilling"),
                    "location_mailgun_rebilling": item.get("location_mailgun_rebilling"),
                    "saas_billing_v2_mismatch_count": len(item.get("saas_billing_v2_mismatches") or []),
                },
                "requests": {
                    "enable_saas": (
                        {
                            "method": "POST",
                            "path": f"/saas_service/saas-config/{lid}/enable-saas",
                            "payload": {
                                "stripeAccountId": stripe_connect_id,
                                "name": item.get("location_name") or lid,
                                "email": loc_email,
                                "companyId": loc_cid,
                                "description": "Stripe Customer Setup",
                            },
                        }
                        if will_enable_hold
                        else None
                    ),
                    "allow_attach_rebilling": (
                        {
                            "method": "PUT",
                            "path": f"/saas-api/saas-config/allow-attach-rebilling/{lid}",
                            "payload": {},
                        }
                        if will_enable_hold
                        else None
                    ),
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
        en_req = reqs.get("enable_saas")
        if isinstance(en_req, dict):
            backend.request(en_req["method"], en_req["path"], body=en_req["payload"])

        att_req = reqs.get("allow_attach_rebilling")
        if isinstance(att_req, dict):
            backend.request(att_req["method"], att_req["path"], body=att_req["payload"])

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
        for _ in range(4):
            if after.get("healthy"):
                break
            time.sleep(0.8)
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


INTEGRATION_RISK_WORKFLOW_KEYWORDS = (
    "capi",
    "webhook",
    "meta",
    "facebook",
    "stripe",
    "payment",
    "betaling",
    "slack",
    "zapier",
    "make",
)


def list_location_workflows_backend(
    backend: BackendClient,
    *,
    location_id: str,
) -> dict[str, Any]:
    """List workflows on a sub-account via backend.leadconnectorhq.com without requiring a per-location PIT token."""
    lid = valid_id(location_id)
    res = backend.request("GET", "/workflows/", query={"locationId": lid})
    raw_items = res.get("workflows", []) if isinstance(res, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []
    workflows = []
    published_ids = []
    draft_ids = []
    risk_items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        wid = str(item.get("id") or item.get("_id") or "")
        name = str(item.get("name") or "")
        status = str(item.get("status") or "").lower()
        has_risk = any(k in name.lower() for k in INTEGRATION_RISK_WORKFLOW_KEYWORDS)
        entry = {
            "id": wid,
            "name": name,
            "status": status,
            "version": item.get("version"),
            "updatedAt": item.get("updatedAt"),
            "integration_risk": has_risk,
        }
        workflows.append(entry)
        if status == "published":
            published_ids.append(wid)
        else:
            draft_ids.append(wid)
        if has_risk:
            risk_items.append({"id": wid, "name": name, "status": status})

    return {
        "location_id": lid,
        "count": len(workflows),
        "published_count": len(published_ids),
        "draft_count": len(draft_ids),
        "all_workflows_draft": len(published_ids) == 0,
        "integration_risk_count": len(risk_items),
        "integration_risk_workflows": risk_items,
        "workflows": workflows,
        "token_source": backend.token_source,
    }


def make_workflow_bulk_status_plan(
    backend: BackendClient,
    *,
    status: str,
    location_id: str | None = None,
    location_ids: list[str] | None = None,
    workflow_ids: list[str] | None = None,
    only_changed: bool = True,
) -> dict[str, Any]:
    """Build a preview plan to bulk-switch workflow status (draft/published) via PUT /workflow/:locationId/change-status."""
    clean_status = (status or "").strip().lower()
    if clean_status not in {"draft", "published"}:
        raise HighLevelError("Workflow status must be 'draft' or 'published'.")

    raw_locs: list[str] = []
    if location_ids:
        raw_locs.extend(x.strip() for x in location_ids if x and x.strip())
    if location_id and location_id.strip():
        if location_id.strip() not in raw_locs:
            raw_locs.append(location_id.strip())
    if not raw_locs:
        raise HighLevelError("Pass --location-id or --location-ids.")

    updated_by = backend.worker_user_id or "agency_operator"
    explicit_wids = [valid_id(w) for w in (workflow_ids or []) if w and w.strip()]

    targets = []
    for raw_lid in raw_locs:
        lid = valid_id(raw_lid)
        wf_info = list_location_workflows_backend(backend, location_id=lid)
        all_wfs = wf_info["workflows"]
        if explicit_wids:
            selected = [w for w in all_wfs if w["id"] in explicit_wids]
            missing = [wid for wid in explicit_wids if not any(w["id"] == wid for w in all_wfs)]
            if missing:
                raise HighLevelError(f"Workflow IDs not found in location {lid}: {missing}")
        else:
            selected = list(all_wfs)

        if only_changed:
            to_update = [w for w in selected if w["status"] != clean_status]
        else:
            to_update = list(selected)

        update_ids = [w["id"] for w in to_update]
        targets.append(
            {
                "location_id": lid,
                "total_workflows": len(all_wfs),
                "before_published_count": wf_info["published_count"],
                "before_draft_count": wf_info["draft_count"],
                "target_status": clean_status,
                "workflow_count_to_update": len(update_ids),
                "already_in_target_status": len(update_ids) == 0,
                "workflows_to_update": [{"id": w["id"], "name": w["name"], "before_status": w["status"]} for w in to_update],
                "proposed_request": (
                    {
                        "method": "PUT",
                        "path": f"/workflow/{lid}/change-status",
                        "payload": {
                            "workflowIds": update_ids,
                            "status": clean_status,
                            "updatedBy": updated_by,
                        },
                    }
                    if update_ids
                    else None
                ),
            }
        )

    plan_core = {
        "resource": "workflow_bulk_status",
        "action": f"bulk_set_{clean_status}",
        "target_status": clean_status,
        "location_count": len(targets),
        "targets": targets,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_workflow_bulk_status_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    target_status = str(plan.get("target_status") or "draft").lower()
    results = []
    for target in plan.get("targets", []):
        lid = valid_id(target["location_id"])
        req = target.get("proposed_request")
        expected_ids = [w["id"] for w in target.get("workflows_to_update", [])]
        if isinstance(req, dict) and expected_ids:
            backend.request(req["method"], req["path"], body=req["payload"])

        after = list_location_workflows_backend(backend, location_id=lid)
        after_map = {w["id"]: w["status"] for w in after["workflows"]}
        mismatched = [wid for wid in expected_ids if after_map.get(wid) != target_status]
        if mismatched:
            raise HighLevelError(
                f"Bulk workflow status readback failed on location {lid} for workflows: {mismatched}"
            )
        results.append(
            {
                "location_id": lid,
                "target_status": target_status,
                "updated_count": len(expected_ids),
                "after_published_count": after["published_count"],
                "after_draft_count": after["draft_count"],
                "all_workflows_draft": after["all_workflows_draft"],
                "verified": True,
            }
        )

    return {
        "mode": "applied",
        "action": plan.get("action"),
        "target_status": target_status,
        "location_count": len(results),
        "verified": True,
        "results": results,
    }


def list_agency_snapshots(
    backend: BackendClient,
    *,
    company_id: str | None = None,
    snapshot_type: str = "own",
    limit: int = 50,
) -> dict[str, Any]:
    """List agency snapshots via GET /snapshots/v2/:companyId."""
    cid = _require_company_id(backend, company_id)
    clean_type = (snapshot_type or "own").strip().lower()
    if clean_type not in {"own", "imported", "shared"}:
        raise HighLevelError("snapshot_type must be 'own', 'imported', or 'shared'.")

    res = backend.request(
        "GET",
        f"/snapshots/v2/{cid}",
        query={
            "companyId": cid,
            "skip": "0",
            "limit": str(max(1, min(int(limit), 100))),
            "type": clean_type,
        },
    )
    raw_snaps = res.get("snapshots") if isinstance(res, dict) and isinstance(res.get("snapshots"), list) else []
    snapshots = []
    for s in raw_snaps:
        if not isinstance(s, dict):
            continue
        dehyd = s.get("dehydrationStatus") if isinstance(s.get("dehydrationStatus"), dict) else {}
        snapshots.append(
            {
                "id": str(s.get("_id") or s.get("id") or ""),
                "name": s.get("name"),
                "location_id": s.get("locationId"),
                "type": s.get("type", clean_type),
                "version": s.get("version"),
                "snapshot_version": s.get("snapshotVersion"),
                "dehydration_state": dehyd.get("state"),
                "dehydration_completed": dehyd.get("completed"),
                "dehydration_total": dehyd.get("total"),
                "date_added": s.get("dateAdded"),
                "date_updated": s.get("dateUpdated"),
            }
        )
    return {
        "company_id": cid,
        "snapshot_type": clean_type,
        "count": len(snapshots),
        "total_count": res.get("totalCount", len(snapshots)) if isinstance(res, dict) else len(snapshots),
        "snapshots": snapshots,
        "token_source": backend.token_source,
    }


def inspect_agency_snapshot(
    backend: BackendClient,
    *,
    snapshot_id: str,
    company_id: str | None = None,
    snapshot_type: str = "own",
) -> dict[str, Any]:
    """Inspect a snapshot's metadata, 16-category asset inventory, push-in-progress status, and recent push batches."""
    sid = valid_id(snapshot_id)
    cid = _require_company_id(backend, company_id)
    clean_type = (snapshot_type or "own").strip().lower()

    details = backend.request(
        "GET",
        f"/snapshots/snapshotDetails/{sid}",
        query={"companyId": cid},
    )
    assets_raw = backend.request(
        "GET",
        f"/snapshots/{sid}/assets",
        query={"type": clean_type, "companyId": cid},
    )
    try:
        push_in_prog = backend.request(
            "GET",
            f"/snapshots/snapshot-push/{sid}/push-in-progress",
            query={"companyId": cid},
        )
    except HighLevelError:
        push_in_prog = {"inProgress": True}
    batches_raw = backend.request(
        "GET",
        f"/snapshots/push-batch/v2/{sid}/batches",
        query={"snapshotId": sid, "companyId": cid, "skip": "0", "limit": "10"},
    )

    category_counts: dict[str, int] = {}
    selected_snapshot_assets: dict[str, list[str]] = {}
    default_dashboard_id: str | None = None
    total_assets = 0

    if isinstance(assets_raw, dict):
        for cat, items in assets_raw.items():
            if not isinstance(items, list):
                continue
            ids = [str(x.get("id")) for x in items if isinstance(x, dict) and x.get("id")]
            if ids:
                category_counts[cat] = len(ids)
                selected_snapshot_assets[cat] = ids
                total_assets += len(ids)
                if cat == "dashboards":
                    for d_item in items:
                        if isinstance(d_item, dict) and d_item.get("id"):
                            if d_item.get("isDefault") or default_dashboard_id is None:
                                default_dashboard_id = str(d_item["id"])

    dehyd = details.get("dehydrationStatus") if isinstance(details, dict) and isinstance(details.get("dehydrationStatus"), dict) else {}
    batches = batches_raw.get("batches", []) if isinstance(batches_raw, dict) and isinstance(batches_raw.get("batches"), list) else []

    return {
        "company_id": cid,
        "snapshot_id": sid,
        "name": details.get("name") if isinstance(details, dict) else None,
        "source_location_id": details.get("locationId") if isinstance(details, dict) else None,
        "type": details.get("type", clean_type) if isinstance(details, dict) else clean_type,
        "version": details.get("version") if isinstance(details, dict) else None,
        "snapshot_version": details.get("snapshotVersion") if isinstance(details, dict) else None,
        "dehydration_status": {
            "state": dehyd.get("state"),
            "operation_type": dehyd.get("operationType"),
            "completed": dehyd.get("completed"),
            "total": dehyd.get("total"),
        },
        "total_asset_count": total_assets,
        "category_counts": category_counts,
        "default_dashboard_id": default_dashboard_id,
        "selected_snapshot_assets": selected_snapshot_assets,
        "assets": assets_raw if isinstance(assets_raw, dict) else {},
        "push_in_progress": push_in_prog,
        "recent_push_batches": batches,
        "token_source": backend.token_source,
    }


def make_snapshot_create_plan(
    backend: BackendClient,
    *,
    name: str,
    location_id: str,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Build a preview plan to create a new V2 agency snapshot from a source sub-account."""
    clean_name = (name or "").strip()
    if not clean_name or len(clean_name) > 120:
        raise HighLevelError("Snapshot --name is required (1..120 characters).")
    lid = valid_id(location_id)
    cid = _require_company_id(backend, company_id)

    loc_info = list_agency_locations(backend, location_id=lid)["location"]
    existing = list_agency_snapshots(backend, company_id=cid)["snapshots"]
    same_name = [s for s in existing if str(s.get("name") or "").strip().lower() == clean_name.lower()]

    proposed_payload = {
        "name": clean_name,
        "location_id": lid,
        "company_id": cid,
    }
    plan_core = {
        "resource": "agency_snapshot",
        "action": "create_snapshot_v2",
        "company_id": cid,
        "source_location_id": lid,
        "source_location_name": loc_info.get("name"),
        "snapshot_name": clean_name,
        "existing_same_name_count": len(same_name),
        "proposed_request": {
            "method": "POST",
            "path": "/snapshots/create",
            "query": {"companyId": cid},
            "payload": proposed_payload,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_snapshot_create_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
    wait: bool = False,
    timeout_seconds: int = 90,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    req = plan["proposed_request"]
    cid = valid_id(plan["company_id"])
    created_res = backend.request(req["method"], req["path"], body=req["payload"], query=req["query"])
    snap_id = str(
        created_res.get("_id")
        or created_res.get("id")
        or (created_res.get("snapshot") or {}).get("_id")
        or ""
    ).strip()

    if not snap_id:
        snaps = list_agency_snapshots(backend, company_id=cid)["snapshots"]
        matches = [
            s for s in snaps
            if s.get("name") == plan["snapshot_name"] and s.get("location_id") == plan["source_location_id"]
        ]
        if matches:
            snap_id = str(matches[0]["id"])

    dehydration_state = None
    if snap_id and wait:
        deadline = time.time() + max(5, int(timeout_seconds))
        while time.time() < deadline:
            det = backend.request("GET", f"/snapshots/snapshotDetails/{snap_id}", query={"companyId": cid})
            dehyd = det.get("dehydrationStatus") if isinstance(det, dict) and isinstance(det.get("dehydrationStatus"), dict) else {}
            dehydration_state = dehyd.get("state")
            if dehydration_state == "completed":
                break
            time.sleep(2.0)

    return {
        "mode": "applied",
        "action": "create_snapshot_v2",
        "company_id": cid,
        "snapshot_id": snap_id or None,
        "snapshot_name": plan["snapshot_name"],
        "source_location_id": plan["source_location_id"],
        "dehydration_state": dehydration_state,
        "verified": bool(snap_id),
        "response": created_res,
    }


def make_snapshot_refresh_plan(
    backend: BackendClient,
    *,
    snapshot_id: str,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Build a preview plan to refresh an existing V2 agency snapshot from its linked source sub-account."""
    sid = valid_id(snapshot_id)
    cid = _require_company_id(backend, company_id)
    inspected = inspect_agency_snapshot(backend, snapshot_id=sid, company_id=cid)

    plan_core = {
        "resource": "agency_snapshot",
        "action": "refresh_snapshot_v2",
        "company_id": cid,
        "snapshot_id": sid,
        "snapshot_name": inspected.get("name"),
        "source_location_id": inspected.get("source_location_id"),
        "before_snapshot_version": inspected.get("snapshot_version"),
        "before_total_asset_count": inspected.get("total_asset_count"),
        "proposed_request": {
            "method": "POST",
            "path": f"/snapshots/{sid}/refresh",
            "query": {"companyId": cid},
            "payload": {"extras": {}},
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_snapshot_refresh_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
    wait: bool = False,
    timeout_seconds: int = 90,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    sid = valid_id(plan["snapshot_id"])
    cid = valid_id(plan["company_id"])
    req = plan["proposed_request"]
    refresh_res = backend.request(req["method"], req["path"], body=req["payload"], query=req["query"])

    dehydration_state = None
    after_version = None
    if wait:
        deadline = time.time() + max(5, int(timeout_seconds))
        while time.time() < deadline:
            det = backend.request("GET", f"/snapshots/snapshotDetails/{sid}", query={"companyId": cid})
            dehyd = det.get("dehydrationStatus") if isinstance(det, dict) and isinstance(det.get("dehydrationStatus"), dict) else {}
            dehydration_state = dehyd.get("state")
            after_version = det.get("snapshotVersion") if isinstance(det, dict) else None
            if dehydration_state == "completed":
                break
            time.sleep(2.0)

    return {
        "mode": "applied",
        "action": "refresh_snapshot_v2",
        "company_id": cid,
        "snapshot_id": sid,
        "snapshot_name": plan.get("snapshot_name"),
        "after_snapshot_version": after_version,
        "dehydration_state": dehydration_state,
        "verified": True,
        "response": refresh_res,
    }


def make_snapshot_push_plan(
    backend: BackendClient,
    *,
    snapshot_id: str,
    location_ids: list[str],
    company_id: str | None = None,
    overwrite_conflicts: bool = True,
    draft_workflows: bool = True,
    unlock_dashboards: bool = True,
) -> dict[str, Any]:
    """Build a preview plan to push an agency V2 snapshot into one or more target sub-accounts."""
    sid = valid_id(snapshot_id)
    cid = _require_company_id(backend, company_id)
    clean_locs = []
    for raw_lid in location_ids or []:
        if raw_lid and raw_lid.strip():
            lid = valid_id(raw_lid.strip())
            if lid not in clean_locs:
                clean_locs.append(lid)
    if not clean_locs:
        raise HighLevelError("Provide at least one target sub-account via --location-id or --location-ids.")

    inspected = inspect_agency_snapshot(backend, snapshot_id=sid, company_id=cid)
    source_lid = inspected.get("source_location_id")
    if source_lid and source_lid in clean_locs:
        raise HighLevelError(
            f"Refusing to push snapshot {sid} onto its own source sub-account ({source_lid})."
        )

    selected_assets = inspected["selected_snapshot_assets"]
    if not selected_assets:
        raise HighLevelError(f"Snapshot {sid} returned 0 selectable assets; verify snapshot dehydration status.")

    target_locations_meta = []
    for lid in clean_locs:
        loc_res = backend.request("GET", f"/locations/{lid}")
        loc_obj = loc_res.get("location", loc_res) if isinstance(loc_res, dict) else {}
        target_locations_meta.append(
            {
                "location_id": lid,
                "name": loc_obj.get("name") if isinstance(loc_obj, dict) else None,
            }
        )

    skip_data = (
        {}
        if overwrite_conflicts
        else {lid: {"assets": {}, "skipAllConflicts": True} for lid in clean_locs}
    )
    push_payload: dict[str, Any] = {
        "selectedSnapshotAssets": selected_assets,
        "snapshotType": inspected.get("type") or "own",
        "autoIncludeDependentAssets": True,
        "selectedLocationIds": clean_locs,
        "selectedLocationsData": {
            "all": {
                "selectedLocationIds": clean_locs,
                "excludedLocationIds": [],
                "isGlobalSelectChecked": False,
                "selectedLocationsCount": len(clean_locs),
            },
            "available": {
                "selectedLocationIds": clean_locs,
                "excludedLocationIds": [],
                "isGlobalSelectChecked": False,
                "selectedLocationsCount": len(clean_locs),
            },
            "linked": {
                "selectedLocationIds": [],
                "excludedLocationIds": [],
                "isGlobalSelectChecked": False,
                "selectedLocationsCount": 0,
            },
        },
        "globalLocationConflictSelect": False,
        "shouldOverwriteAllConflicts": bool(overwrite_conflicts),
        "skipData": skip_data,
    }
    if inspected.get("default_dashboard_id"):
        push_payload["defaultDashboardId"] = inspected["default_dashboard_id"]

    plan_core = {
        "resource": "agency_snapshot_push",
        "action": "push_snapshot_v2",
        "company_id": cid,
        "snapshot_id": sid,
        "snapshot_name": inspected.get("name"),
        "snapshot_version": inspected.get("snapshot_version"),
        "source_location_id": source_lid,
        "total_asset_count": inspected.get("total_asset_count"),
        "category_counts": inspected.get("category_counts"),
        "target_location_count": len(clean_locs),
        "target_locations": target_locations_meta,
        "overwrite_conflicts": bool(overwrite_conflicts),
        "post_push_draft_workflows": bool(draft_workflows),
        "post_push_unlock_dashboards": bool(unlock_dashboards),
        "proposed_request": {
            "method": "POST",
            "path": f"/snapshots/snapshot-push/v2/{sid}/set_assets_to_locations",
            "query": {"companyId": cid},
            "payload": push_payload,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_snapshot_push_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
    wait: bool = True,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    sid = valid_id(plan["snapshot_id"])
    cid = valid_id(plan["company_id"])
    target_lids = [valid_id(t["location_id"]) for t in plan.get("target_locations", [])]
    req = plan["proposed_request"]

    push_res = backend.request(req["method"], req["path"], body=req["payload"], query=req["query"])

    batch_status = None
    if wait or plan.get("post_push_draft_workflows") or plan.get("post_push_unlock_dashboards"):
        deadline = time.time() + max(10, int(timeout_seconds))
        while time.time() < deadline:
            try:
                prog = backend.request(
                    "GET",
                    f"/snapshots/snapshot-push/{sid}/push-in-progress",
                    query={"companyId": cid},
                )
                in_prog = bool(prog.get("pushInProgress") or prog.get("inProgress")) if isinstance(prog, dict) else False
            except HighLevelError:
                in_prog = True
            batches_res = backend.request(
                "GET",
                f"/snapshots/push-batch/v2/{sid}/batches",
                query={"snapshotId": sid, "companyId": cid, "skip": "0", "limit": "5"},
            )
            batches = batches_res.get("batches", []) if isinstance(batches_res, dict) and isinstance(batches_res.get("batches"), list) else []
            latest_batch = batches[0] if batches and isinstance(batches[0], dict) else {}
            batch_status = latest_batch.get("status")
            if batch_status == "completed" or (not in_prog and batch_status == "completed"):
                break
            time.sleep(2.5)

    workflow_draft_results = []
    if plan.get("post_push_draft_workflows"):
        wf_plan = make_workflow_bulk_status_plan(
            backend,
            status="draft",
            location_ids=target_lids,
            only_changed=True,
        )
        wf_applied = apply_workflow_bulk_status_plan(
            backend,
            wf_plan,
            confirm_plan=wf_plan["sha256"],
        )
        workflow_draft_results = wf_applied["results"]

    dashboard_unlock_results = []
    if plan.get("post_push_unlock_dashboards"):
        for lid in target_lids:
            d_plan = make_unlock_dashboards_plan(backend, location_id=lid, company_id=cid)
            d_applied = apply_unlock_dashboards_plan(backend, d_plan, confirm_plan=d_plan["sha256"])
            dashboard_unlock_results.extend(d_applied["results"])

    location_histories = []
    for lid in target_lids:
        hist = backend.request(
            "GET",
            f"/snapshots/locations/{lid}/snapshot-history",
            query={"companyId": cid, "page": "1", "limit": "5"},
        )
        hist_items = hist.get("data", []) if isinstance(hist, dict) and isinstance(hist.get("data"), list) else []
        location_histories.append(
            {
                "location_id": lid,
                "latest_load": hist_items[0] if hist_items else None,
            }
        )

    return {
        "mode": "applied",
        "action": "push_snapshot_v2",
        "company_id": cid,
        "snapshot_id": sid,
        "snapshot_name": plan.get("snapshot_name"),
        "target_locations": target_lids,
        "batch_status": batch_status,
        "workflow_draft_results": workflow_draft_results,
        "dashboard_unlock_results": dashboard_unlock_results,
        "location_snapshot_histories": location_histories,
        "verified": True,
        "response": push_res,
    }


def make_location_full_unnerf_plan(
    backend: BackendClient,
    *,
    location_id: str | None = None,
    location_ids: list[str] | None = None,
    user_id: str | None = None,
    email: str | None = None,
    company_id: str | None = None,
    markup: int = 5,
) -> dict[str, Any]:
    """Build a single 5-layer governance un-nerf plan (location flags, user scopes + alias, dashboards RBAC, Custom SMTP, and 4-store rebilling)."""
    cid = _require_company_id(backend, company_id)
    clean_locs: list[str] = []
    if location_ids:
        for x in location_ids:
            if x and x.strip():
                lid = valid_id(x.strip())
                if lid not in clean_locs:
                    clean_locs.append(lid)
    if location_id and location_id.strip():
        lid = valid_id(location_id.strip())
        if lid not in clean_locs:
            clean_locs.append(lid)
    if not clean_locs:
        raise HighLevelError("Pass --location-id or --location-ids.")

    loc_plans = [
        make_location_unnerf_plan(backend, location_id=lid, company_id=cid)
        for lid in clean_locs
    ]
    dash_plans = [
        make_unlock_dashboards_plan(backend, location_id=lid, company_id=cid)
        for lid in clean_locs
    ]
    smtp_plans = [
        make_smtp_unlock_plan(backend, location_id=lid, company_id=cid)
        for lid in clean_locs
    ]
    rebill_plans = [
        make_rebilling_sync_plan(backend, location_id=lid, company_id=cid, markup=markup)
        for lid in clean_locs
    ]

    user_plans: list[dict[str, Any]] = []
    if user_id or email:
        primary_plan = make_user_unnerf_plan(
            backend,
            user_id=user_id,
            email=email,
            company_id=cid,
            add_location_ids=clean_locs,
        )
        user_plans.append(primary_plan)
        base_em = _canonical_base_email(primary_plan.get("email") or "")
        if base_em:
            all_users = list_agency_users(backend, company_id=cid)["users"]
            for u in all_users:
                if u.get("deleted"):
                    continue
                uid = str(u.get("id") or "")
                uem = str(u.get("email") or "").strip().lower()
                if uid != primary_plan["user_id"] and _canonical_base_email(uem) == base_em:
                    user_plans.append(
                        make_user_unnerf_plan(
                            backend,
                            user_id=uid,
                            company_id=cid,
                            add_location_ids=clean_locs,
                        )
                    )

    plan_core = {
        "resource": "location_full_unnerf",
        "action": "full_5_layer_unnerf",
        "company_id": cid,
        "location_ids": clean_locs,
        "markup": int(markup),
        "layers": {
            "layer_1_location_permissions": loc_plans,
            "layer_2_user_scopes": user_plans,
            "layer_3_dashboard_rbac": dash_plans,
            "layer_4_custom_smtp": smtp_plans,
            "layer_5_rebilling_sync": rebill_plans,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_location_full_unnerf_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    layers = plan.get("layers", {})
    loc_results = []
    for lp in layers.get("layer_1_location_permissions", []):
        res = apply_location_unnerf_plan(backend, lp, confirm_plan=lp["sha256"])
        loc_results.extend(res.get("results", []))

    user_results = []
    for up in layers.get("layer_2_user_scopes", []):
        res = apply_user_unnerf_plan(
            backend,
            up,
            confirm_user=up["user_id"],
            confirm_plan=up["sha256"],
        )
        user_results.append(res)

    dash_results = []
    for dp in layers.get("layer_3_dashboard_rbac", []):
        res = apply_unlock_dashboards_plan(backend, dp, confirm_plan=dp["sha256"])
        dash_results.extend(res.get("results", []))

    smtp_results = []
    for sp in layers.get("layer_4_custom_smtp", []):
        res = apply_smtp_unlock_plan(backend, sp, confirm_plan=sp["sha256"])
        smtp_results.extend(res.get("results", []))

    rebill_results = []
    for rp in layers.get("layer_5_rebilling_sync", []):
        res = apply_rebilling_sync_plan(backend, rp, confirm_plan=rp["sha256"])
        rebill_results.extend(res.get("results", []))

    return {
        "mode": "applied",
        "action": "full_5_layer_unnerf",
        "company_id": plan.get("company_id"),
        "location_ids": plan.get("location_ids"),
        "verified": True,
        "results": {
            "layer_1_location_permissions": loc_results,
            "layer_2_user_scopes": user_results,
            "layer_3_dashboard_rbac": dash_results,
            "layer_4_custom_smtp": smtp_results,
            "layer_5_rebilling_sync": rebill_results,
        },
    }


def _backend_brand_hits(text: str | None, terms: list[str]) -> list[str]:
    if not text or not terms:
        return []
    low = str(text).lower()
    return [t for t in terms if t and t.lower() in low]


def inspect_location_clone_audit(
    backend: BackendClient,
    *,
    location_id: str,
    company_id: str | None = None,
    brand_terms: list[str] | None = None,
) -> dict[str, Any]:
    """Deep-audit a cloned or existing sub-account via backend.leadconnectorhq.com for asset parity, workflow draft state, governance readiness, and brand-term leaks."""
    lid = valid_id(location_id)
    cid = _require_company_id(backend, company_id)
    clean_terms = [t.strip() for t in (brand_terms or []) if t and t.strip()]

    loc_info = list_agency_locations(backend, location_id=lid)["location"]
    wf_info = list_location_workflows_backend(backend, location_id=lid)

    pipes_res = backend.request("GET", "/opportunities/pipelines", query={"locationId": lid})
    raw_pipes = pipes_res.get("pipelines", []) if isinstance(pipes_res, dict) and isinstance(pipes_res.get("pipelines"), list) else []
    pipelines = [
        {
            "id": str(p.get("id") or ""),
            "name": str(p.get("name") or ""),
            "stage_count": len(p.get("stages") or []),
            "stages": [str(s.get("name") or "") for s in (p.get("stages") or []) if isinstance(s, dict)],
        }
        for p in raw_pipes
        if isinstance(p, dict)
    ]

    cals_res = backend.request("GET", "/calendars/", query={"locationId": lid})
    raw_cals = cals_res.get("calendars", []) if isinstance(cals_res, dict) and isinstance(cals_res.get("calendars"), list) else []
    calendars = [
        {
            "id": str(c.get("id") or ""),
            "name": str(c.get("name") or ""),
            "slug": c.get("slug"),
            "calendarType": c.get("calendarType"),
            "isActive": c.get("isActive"),
        }
        for c in raw_cals
        if isinstance(c, dict)
    ]

    forms_res = backend.request("GET", "/forms/", query={"locationId": lid, "limit": "50"})
    raw_forms = forms_res.get("forms", []) if isinstance(forms_res, dict) and isinstance(forms_res.get("forms"), list) else []
    forms = [{"id": str(f.get("id") or f.get("_id") or ""), "name": str(f.get("name") or "")} for f in raw_forms if isinstance(f, dict)]

    emails_res = backend.request("GET", "/emails/builder", query={"locationId": lid, "limit": "100"})
    raw_emails = emails_res.get("builders", []) if isinstance(emails_res, dict) and isinstance(emails_res.get("builders"), list) else []
    email_templates = [
        {"id": str(e.get("id") or e.get("_id") or ""), "name": str(e.get("name") or e.get("title") or "")}
        for e in raw_emails
        if isinstance(e, dict)
    ]

    links_res = backend.request("GET", "/links/", query={"locationId": lid})
    raw_links = links_res.get("links", []) if isinstance(links_res, dict) and isinstance(links_res.get("links"), list) else []
    trigger_links = [
        {"id": str(lk.get("id") or ""), "name": str(lk.get("name") or ""), "redirectTo": lk.get("redirectTo")}
        for lk in raw_links
        if isinstance(lk, dict)
    ]

    cv_res = backend.request("GET", f"/locations/{lid}/customValues")
    raw_cvs = cv_res.get("customValues", []) if isinstance(cv_res, dict) and isinstance(cv_res.get("customValues"), list) else []
    custom_values = [
        {
            "id": str(cv.get("id") or ""),
            "name": str(cv.get("name") or ""),
            "fieldKey": cv.get("fieldKey"),
            "value": cv.get("value"),
        }
        for cv in raw_cvs
        if isinstance(cv, dict)
    ]
    empty_custom_values = [cv for cv in custom_values if not str(cv.get("value") or "").strip()]

    cf_res = backend.request("GET", f"/locations/{lid}/customFields")
    raw_cfs = cf_res.get("customFields", []) if isinstance(cf_res, dict) and isinstance(cf_res.get("customFields"), list) else []

    tags_res = backend.request("GET", f"/locations/{lid}/tags")
    raw_tags = tags_res.get("tags", []) if isinstance(tags_res, dict) and isinstance(tags_res.get("tags"), list) else []

    hist_res = backend.request(
        "GET",
        f"/snapshots/locations/{lid}/snapshot-history",
        query={"companyId": cid, "page": "1", "limit": "10"},
    )
    snap_history = hist_res.get("data", []) if isinstance(hist_res, dict) and isinstance(hist_res.get("data"), list) else []

    dash_info = inspect_dashboard_permissions(backend, location_id=lid, company_id=cid)
    email_dom_info = inspect_email_domains(backend, location_id=lid, company_id=cid)
    pits_info = list_private_integrations(backend, location_id=lid)

    brand_matches: list[dict[str, Any]] = []
    if clean_terms:
        for field_name in ("name", "email", "website", "phone"):
            val = loc_info.get(field_name)
            hits = _backend_brand_hits(str(val or ""), clean_terms)
            if hits:
                brand_matches.append({"category": "business_profile", "field": field_name, "value": val, "matched_terms": hits})
        for cv in custom_values:
            hits = _backend_brand_hits(f"{cv.get('name', '')} {cv.get('value', '')}", clean_terms)
            if hits:
                brand_matches.append({"category": "custom_value", "id": cv["id"], "name": cv["name"], "value": cv.get("value"), "matched_terms": hits})
        for p in pipelines:
            hits = _backend_brand_hits(p.get("name"), clean_terms)
            if hits:
                brand_matches.append({"category": "pipeline", "id": p["id"], "name": p["name"], "matched_terms": hits})
        for c in calendars:
            hits = _backend_brand_hits(f"{c.get('name', '')} {c.get('slug', '')}", clean_terms)
            if hits:
                brand_matches.append({"category": "calendar", "id": c["id"], "name": c["name"], "slug": c.get("slug"), "matched_terms": hits})
        for f in forms:
            hits = _backend_brand_hits(f.get("name"), clean_terms)
            if hits:
                brand_matches.append({"category": "form", "id": f["id"], "name": f["name"], "matched_terms": hits})
        for em in email_templates:
            hits = _backend_brand_hits(em.get("name"), clean_terms)
            if hits:
                brand_matches.append({"category": "email_template", "id": em["id"], "name": em["name"], "matched_terms": hits})
        for lk in trigger_links:
            hits = _backend_brand_hits(f"{lk.get('name', '')} {lk.get('redirectTo', '')}", clean_terms)
            if hits:
                brand_matches.append({"category": "trigger_link", "id": lk["id"], "name": lk["name"], "redirectTo": lk.get("redirectTo"), "matched_terms": hits})
        for wf in wf_info["workflows"]:
            hits = _backend_brand_hits(wf.get("name"), clean_terms)
            if hits:
                brand_matches.append({"category": "workflow", "id": wf["id"], "name": wf["name"], "status": wf.get("status"), "matched_terms": hits})

    healthy_clone = (
        bool(loc_info.get("permissions_healthy"))
        and bool(dash_info.get("ok"))
        and email_dom_info.get("block_add_smtp") is False
        and wf_info["all_workflows_draft"]
    )

    return {
        "ok": healthy_clone,
        "company_id": cid,
        "location_id": lid,
        "location_name": loc_info.get("name"),
        "permissions_healthy": loc_info.get("permissions_healthy"),
        "dashboards_healthy": dash_info.get("ok"),
        "custom_smtp_unlocked": email_dom_info.get("block_add_smtp") is False,
        "all_workflows_draft": wf_info["all_workflows_draft"],
        "snapshot_history": snap_history,
        "asset_counts": {
            "workflows_total": wf_info["count"],
            "workflows_published": wf_info["published_count"],
            "workflows_draft": wf_info["draft_count"],
            "pipelines": len(pipelines),
            "calendars": len(calendars),
            "forms": len(forms),
            "email_templates": len(email_templates),
            "trigger_links": len(trigger_links),
            "custom_values": len(custom_values),
            "custom_fields": len(raw_cfs),
            "tags": len(raw_tags),
            "dashboards": dash_info["count"],
            "private_integrations": pits_info["count"],
            "dedicated_email_domains": len(email_dom_info.get("dedicated_domains") or []),
        },
        "integration_risk_workflows": wf_info["integration_risk_workflows"],
        "empty_custom_values": empty_custom_values,
        "pipelines": pipelines,
        "calendars": calendars,
        "forms": forms,
        "email_templates": email_templates,
        "private_integrations": pits_info["private_integrations"],
        "brand_terms_checked": clean_terms,
        "brand_match_count": len(brand_matches),
        "brand_matches": brand_matches,
        "token_source": backend.token_source,
    }


AGENCY_ONLY_PIT_SCOPES: tuple[str, ...] = (
    "wallet.readonly",
    "wallet.write",
    "companies.readonly",
    "locations.write",
    "oauth.write",
    "oauth.readonly",
    "saas/company.read",
    "saas/company.write",
    "snapshots.readonly",
    "snapshots.write",
    "custom-menu-link.readonly",
    "custom-menu-link.write",
    "marketplace-external-auth-migration.write",
)


def _fetch_location_pit_scopes(backend: BackendClient) -> list[str]:
    raw = backend.request("GET", "/oauth/static/scopes")
    items = raw.get("scopes", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return list(CRITICAL_ACCOUNT_ADMIN_V2_SCOPES)
    excluded = set(AGENCY_ONLY_PIT_SCOPES)
    return [str(s) for s in items if isinstance(s, str) and s not in excluded]


def make_pit_create_plan(
    backend: BackendClient,
    *,
    location_id: str,
    name: str,
    description: str = "",
    scopes: list[str] | None = None,
    save_profile: str | None = None,
    set_default_profile: bool = False,
) -> dict[str, Any]:
    lid = valid_id(location_id)
    clean_name = (name or "").strip()
    if not clean_name:
        raise HighLevelError("Private Integration --name is required.")
    resolved_scopes = scopes if scopes else _fetch_location_pit_scopes(backend)
    payload = {
        "locationId": lid,
        "name": clean_name,
        "description": (description or "").strip(),
        "scopes": resolved_scopes,
    }
    plan_core = {
        "resource": "private_integration",
        "action": "create_pit",
        "location_id": lid,
        "name": clean_name,
        "description": payload["description"],
        "scopes_count": len(resolved_scopes),
        "save_profile": (save_profile or "").strip() or None,
        "set_default_profile": bool(set_default_profile),
        "proposed_request": {
            "method": "POST",
            "path": f"/marketplace/private-integration/location/{lid}",
            "payload": payload,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_pit_create_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
    reveal_token: bool = False,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    lid = valid_id(plan["location_id"])
    req = plan["proposed_request"]
    res = backend.request(req["method"], req["path"], body=req["payload"])
    if not isinstance(res, dict):
        raise HighLevelError("Unexpected response from Private Integration creation.")
    raw_tok = str(res.get("activeToken") or res.get("token") or "").strip()
    pid = str(res.get("_id") or res.get("id") or "")

    profile_saved = None
    if plan.get("save_profile") and raw_tok:
        profile_saved = save_subaccount_profile(
            profile=str(plan["save_profile"]),
            location_id=lid,
            pit=raw_tok,
            name=plan["name"],
            set_default=bool(plan.get("set_default_profile")),
        )

    out: dict[str, Any] = {
        "mode": "applied",
        "action": "create_pit",
        "location_id": lid,
        "integration_id": pid,
        "name": res.get("name") or plan["name"],
        "scopes_count": len(res.get("scopes") or []),
        "token_masked": _mask_token(raw_tok),
        "profile_saved": profile_saved,
        "verified": bool(pid and raw_tok),
    }
    if reveal_token:
        out["token"] = raw_tok
    return out


def make_pit_delete_plan(
    backend: BackendClient,
    *,
    location_id: str,
    integration_id: str,
) -> dict[str, Any]:
    lid = valid_id(location_id)
    pid = valid_id(integration_id)
    existing = list_private_integrations(backend, location_id=lid)["private_integrations"]
    matched = next((item for item in existing if item["id"] == pid), None)
    plan_core = {
        "resource": "private_integration",
        "action": "delete_pit",
        "location_id": lid,
        "integration_id": pid,
        "before": matched,
        "proposed_request": {
            "method": "DELETE",
            "path": f"/marketplace/private-integration/location/{lid}/integration/{pid}",
            "payload": None,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_pit_delete_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = backend.request(req["method"], req["path"])
    return {
        "mode": "applied",
        "action": "delete_pit",
        "location_id": plan["location_id"],
        "integration_id": plan["integration_id"],
        "verified": True,
        "response": res,
    }


def make_location_create_plan(
    backend: BackendClient,
    *,
    name: str,
    email: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
    timezone: str | None = None,
    from_location_id: str | None = None,
    company_id: str | None = None,
) -> dict[str, Any]:
    cid = _require_company_id(backend, company_id)
    clean_name = (name or "").strip()
    if not clean_name:
        raise HighLevelError("Sub-account --name is required.")

    src_loc: dict[str, Any] = {}
    if from_location_id:
        src_lid = valid_id(from_location_id)
        src_res = backend.request("GET", f"/locations/{src_lid}")
        src_obj = src_res.get("location", src_res)
        if isinstance(src_obj, dict):
            src_loc = src_obj

    payload: dict[str, Any] = {
        "companyId": cid,
        "name": clean_name,
        "country": (country or src_loc.get("country") or "US").strip(),
        "timezone": (timezone or src_loc.get("timezone") or "America/New_York").strip(),
        "email": (email or src_loc.get("email") or "support@rankyrank.com").strip(),
        "phone": (phone or src_loc.get("phone") or "").strip(),
        "address": (address or src_loc.get("address") or "Main Street 1").strip(),
        "city": (city or src_loc.get("city") or "New York").strip(),
        "state": (state or src_loc.get("state") or "").strip(),
        "postalCode": (postal_code or src_loc.get("postalCode") or "10001").strip(),
        "website": (website or src_loc.get("website") or "").strip(),
        "settings": {
            "allowDuplicateContact": False,
            "allowDuplicateOpportunity": False,
            "allowFacebookNameMerge": True,
            "disableContactTimezone": False,
        },
    }
    plan_core = {
        "resource": "location",
        "action": "create_location",
        "company_id": cid,
        "from_location_id": valid_id(from_location_id) if from_location_id else None,
        "proposed_request": {
            "method": "POST",
            "path": "/locations/",
            "payload": payload,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_location_create_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = backend.request(req["method"], req["path"], body=req["payload"])
    loc = res.get("location", res) if isinstance(res, dict) else {}
    lid = str(loc.get("id") or loc.get("_id") or "")
    if not lid:
        raise HighLevelError("Sub-account creation did not return a valid location ID.")
    return {
        "mode": "applied",
        "action": "create_location",
        "company_id": plan["company_id"],
        "location_id": lid,
        "name": loc.get("name") or req["payload"]["name"],
        "country": loc.get("country"),
        "timezone": loc.get("timezone"),
        "verified": True,
    }


def make_location_batch_clone_plan(
    backend: BackendClient,
    *,
    source_location_id: str,
    names: list[str],
    snapshot_id: str | None = None,
    assign_email: str | None = None,
    assign_user_id: str | None = None,
    draft_workflows: bool = True,
    full_unnerf: bool = True,
    markup: int = 5,
    create_pits: bool = False,
    company_id: str | None = None,
) -> dict[str, Any]:
    """Build a 1-command multi-sub-account batch clone plan (create locations -> push V2 snapshot -> draft workflows -> 5-layer unnerf + Stripe hold -> audit)."""
    cid = _require_company_id(backend, company_id)
    src_lid = valid_id(source_location_id)
    clean_names = [n.strip() for n in names if n and n.strip()]
    if not clean_names:
        raise HighLevelError("Provide at least one target sub-account name in --names.")

    src_res = backend.request("GET", f"/locations/{src_lid}")
    src_loc = src_res.get("location", src_res)
    if not isinstance(src_loc, dict):
        raise HighLevelError(f"Could not inspect source location {src_lid}.")

    resolved_snapshot_id = valid_id(snapshot_id) if snapshot_id else None
    snapshot_name = None
    if resolved_snapshot_id:
        snap_info = inspect_agency_snapshot(backend, snapshot_id=resolved_snapshot_id, company_id=cid)
        snapshot_name = snap_info.get("name") or (snap_info.get("snapshot") or {}).get("name")

    create_plans = [
        make_location_create_plan(
            backend,
            name=target_name,
            from_location_id=src_lid,
            company_id=cid,
        )["proposed_request"]
        for target_name in clean_names
    ]

    plan_core = {
        "resource": "location_batch_clone",
        "action": "batch_clone_locations",
        "company_id": cid,
        "source_location_id": src_lid,
        "source_location_name": src_loc.get("name"),
        "snapshot_id": resolved_snapshot_id,
        "snapshot_name": snapshot_name,
        "target_names": clean_names,
        "target_count": len(clean_names),
        "assign_email": (assign_email or "").strip() or None,
        "assign_user_id": valid_id(assign_user_id) if assign_user_id else None,
        "draft_workflows": bool(draft_workflows),
        "full_unnerf": bool(full_unnerf),
        "markup": int(markup),
        "create_pits": bool(create_pits),
        "create_requests": create_plans,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_location_batch_clone_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    cid = valid_id(plan["company_id"])
    src_lid = valid_id(plan["source_location_id"])
    sid = plan.get("snapshot_id")

    if not sid:
        snap_plan = make_snapshot_create_plan(
            backend,
            name=f"{plan.get('source_location_name') or src_lid} Clone Snapshot",
            location_id=src_lid,
            company_id=cid,
        )
        snap_res = apply_snapshot_create_plan(
            backend,
            snap_plan,
            confirm_plan=snap_plan["sha256"],
            wait=True,
            timeout_seconds=timeout_seconds,
        )
        sid = snap_res["snapshot_id"]

    created_locations: list[dict[str, Any]] = []
    target_lids: list[str] = []
    for req in plan.get("create_requests", []):
        res = backend.request(req["method"], req["path"], body=req["payload"])
        loc = res.get("location", res) if isinstance(res, dict) else {}
        lid = str(loc.get("id") or loc.get("_id") or "")
        if not lid:
            raise HighLevelError("Batch clone failed to obtain location ID for created sub-account.")
        target_lids.append(lid)
        created_locations.append(
            {
                "location_id": lid,
                "name": loc.get("name") or req["payload"]["name"],
                "country": loc.get("country"),
                "timezone": loc.get("timezone"),
            }
        )

    push_plan = make_snapshot_push_plan(
        backend,
        snapshot_id=sid,
        location_ids=target_lids,
        company_id=cid,
        draft_workflows=bool(plan.get("draft_workflows", True)),
        unlock_dashboards=True,
    )
    push_applied = apply_snapshot_push_plan(
        backend,
        push_plan,
        confirm_plan=push_plan["sha256"],
        wait=True,
        timeout_seconds=timeout_seconds,
    )

    unnerf_applied = None
    if plan.get("full_unnerf", True):
        unnerf_plan = make_location_full_unnerf_plan(
            backend,
            location_ids=target_lids,
            user_id=plan.get("assign_user_id"),
            email=plan.get("assign_email"),
            company_id=cid,
            markup=int(plan.get("markup", 5)),
        )
        unnerf_applied = apply_location_full_unnerf_plan(
            backend,
            unnerf_plan,
            confirm_plan=unnerf_plan["sha256"],
        )

    created_pits: list[dict[str, Any]] = []
    if plan.get("create_pits"):
        for item in created_locations:
            lid = item["location_id"]
            pit_plan = make_pit_create_plan(
                backend,
                location_id=lid,
                name=f"{item['name']} Agent Integration",
                description="Auto-provisioned by legends-gohighlevel batch clone",
            )
            pit_res = apply_pit_create_plan(backend, pit_plan, confirm_plan=pit_plan["sha256"])
            created_pits.append(pit_res)

    audits = [
        inspect_location_clone_audit(backend, location_id=lid, company_id=cid)
        for lid in target_lids
    ]

    return {
        "mode": "applied",
        "action": "batch_clone_locations",
        "company_id": cid,
        "source_location_id": src_lid,
        "snapshot_id": sid,
        "created_locations": created_locations,
        "snapshot_push": {
            "batch_status": push_applied.get("batch_status"),
            "workflow_draft_results": push_applied.get("workflow_draft_results"),
        },
        "full_unnerf_verified": bool(unnerf_applied and unnerf_applied.get("verified")),
        "created_pits": created_pits,
        "clone_audits": [
            {
                "location_id": a["location_id"],
                "location_name": a["location_name"],
                "ok": a["ok"],
                "all_workflows_draft": a["all_workflows_draft"],
                "permissions_healthy": a["permissions_healthy"],
                "dashboards_healthy": a["dashboards_healthy"],
                "custom_smtp_unlocked": a["custom_smtp_unlocked"],
                "asset_counts": a["asset_counts"],
            }
            for a in audits
        ],
        "verified": all(a["ok"] for a in audits),
    }


def _apply_backend_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    out = text
    for old_val, new_val in replacements:
        if not old_val:
            continue
        pattern = re.compile(re.escape(old_val), re.IGNORECASE)
        out = pattern.sub(new_val, out)
    return out


def make_location_rebrand_plan(
    backend: BackendClient,
    *,
    location_id: str,
    company_id: str | None = None,
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
    include_workflow_steps: bool = False,
    workflow_from_name: str | None = None,
    workflow_from_email: str | None = None,
    workflow_pixel_id: str | None = None,
    workflow_capi_token: str | None = None,
) -> dict[str, Any]:
    """Build an agency-level sub-account rebrand plan via backend.leadconnectorhq.com across Business Profile, Custom Values, Trigger Links, Calendars, and optional internal Workflow Steps."""
    cid = _require_company_id(backend, company_id)
    lid = valid_id(location_id)
    loc_res = backend.request("GET", f"/locations/{lid}")
    before_loc = loc_res.get("location", loc_res)
    if not isinstance(before_loc, dict):
        before_loc = {}

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
            replaced = _apply_backend_replacements(str(before_loc[k]), clean_pairs)
            if replaced != before_loc.get(k):
                profile_updates[k] = replaced

    cvs_res = backend.request("GET", f"/locations/{lid}/customValues")
    raw_cvs = cvs_res.get("customValues", []) if isinstance(cvs_res, dict) and isinstance(cvs_res.get("customValues"), list) else []
    cv_mutations: list[dict[str, Any]] = []
    matched_override_keys: set[str] = set()
    for cv in raw_cvs:
        if not isinstance(cv, dict):
            continue
        cv_id = str(cv.get("id") or "")
        cv_name = str(cv.get("name") or "")
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
            new_val = _apply_backend_replacements(old_val, clean_pairs)
        if new_val != old_val and cv_id:
            cv_mutations.append(
                {
                    "action": "update",
                    "id": cv_id,
                    "name": cv_name,
                    "before_value": old_val,
                    "after_value": new_val,
                    "request": {
                        "method": "PUT",
                        "path": f"/locations/{lid}/customValues/{cv_id}",
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
                        "path": f"/locations/{lid}/customValues",
                        "payload": {"name": orig_name, "value": val},
                    },
                }
            )

    link_mutations: list[dict[str, Any]] = []
    if clean_pairs:
        try:
            links_res = backend.request("GET", "/links/", query={"locationId": lid})
            raw_links = links_res.get("links", []) if isinstance(links_res, dict) and isinstance(links_res.get("links"), list) else []
        except HighLevelError:
            raw_links = []
        for lk in raw_links:
            if not isinstance(lk, dict):
                continue
            link_id = str(lk.get("id") or lk.get("_id") or "")
            old_name = str(lk.get("name") or "")
            old_url = str(lk.get("redirectTo") or "")
            new_name = _apply_backend_replacements(old_name, clean_pairs)
            new_url = _apply_backend_replacements(old_url, clean_pairs)
            if (new_name != old_name or new_url != old_url) and link_id:
                link_mutations.append(
                    {
                        "id": link_id,
                        "before_name": old_name,
                        "after_name": new_name,
                        "before_redirect_to": old_url,
                        "after_redirect_to": new_url,
                        "request": {
                            "method": "PUT",
                            "path": f"/links/{link_id}",
                            "payload": {"name": new_name, "redirectTo": new_url},
                        },
                    }
                )

    calendar_mutations: list[dict[str, Any]] = []
    if clean_pairs:
        cals_res = backend.request("GET", "/calendars/", query={"locationId": lid})
        raw_cals = cals_res.get("calendars", []) if isinstance(cals_res, dict) and isinstance(cals_res.get("calendars"), list) else []
        for cal in raw_cals:
            if not isinstance(cal, dict):
                continue
            cal_id = str(cal.get("id") or "")
            old_name = str(cal.get("name") or "")
            new_name = _apply_backend_replacements(old_name, clean_pairs)
            if new_name != old_name and cal_id:
                calendar_mutations.append(
                    {
                        "id": cal_id,
                        "before_name": old_name,
                        "after_name": new_name,
                        "request": {
                            "method": "PUT",
                            "path": f"/calendars/{cal_id}",
                            "payload": {"name": new_name},
                        },
                    }
                )

    workflow_step_mutations: list[dict[str, Any]] = []
    if include_workflow_steps or workflow_from_name or workflow_from_email or workflow_pixel_id or workflow_capi_token:
        wf_step_plan = make_workflow_steps_rebrand_plan(
            backend,
            location_id=lid,
            replace_pairs=clean_pairs,
            from_name=workflow_from_name,
            from_email=workflow_from_email,
            pixel_id=workflow_pixel_id,
            capi_access_token=workflow_capi_token,
        )
        workflow_step_mutations = wf_step_plan.get("workflow_mutations", [])

    plan_core = {
        "resource": "location_rebrand",
        "action": "rebrand_location",
        "company_id": cid,
        "location_id": lid,
        "replace_pairs": [{"from": k, "to": v} for k, v in clean_pairs],
        "business_profile_update": (
            {
                "before": {k: before_loc.get(k) for k in profile_updates},
                "after": profile_updates,
                "request": {
                    "method": "PUT",
                    "path": f"/locations/{lid}",
                    "payload": {"companyId": cid, **profile_updates},
                },
            }
            if profile_updates
            else None
        ),
        "custom_value_mutations": cv_mutations,
        "trigger_link_mutations": link_mutations,
        "calendar_mutations": calendar_mutations,
        "workflow_step_mutations": workflow_step_mutations,
        "summary": {
            "profile_fields_changed": len(profile_updates),
            "custom_values_changed": len(cv_mutations),
            "trigger_links_changed": len(link_mutations),
            "calendars_changed": len(calendar_mutations),
            "workflows_changed": len(workflow_step_mutations),
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_location_rebrand_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    lid = valid_id(plan["location_id"])
    prof_up = plan.get("business_profile_update")
    if isinstance(prof_up, dict) and isinstance(prof_up.get("request"), dict):
        req = prof_up["request"]
        backend.request(req["method"], req["path"], body=req["payload"])

    cv_results = []
    for item in plan.get("custom_value_mutations", []):
        req = item["request"]
        backend.request(req["method"], req["path"], body=req["payload"])
        cv_results.append({"name": item["name"], "action": item["action"], "after_value": item["after_value"]})

    link_results = []
    for item in plan.get("trigger_link_mutations", []):
        req = item["request"]
        backend.request(req["method"], req["path"], body=req["payload"])
        link_results.append({"id": item["id"], "after_name": item["after_name"], "after_redirect_to": item["after_redirect_to"]})

    cal_results = []
    for item in plan.get("calendar_mutations", []):
        req = item["request"]
        backend.request(req["method"], req["path"], body=req["payload"])
        cal_results.append({"id": item["id"], "after_name": item["after_name"]})

    wf_results = []
    for item in plan.get("workflow_step_mutations", []):
        req = item["request"]
        backend.request(req["method"], req["path"], body=req["payload"])
        wf_results.append(
            {
                "workflow_id": item["workflow_id"],
                "workflow_name": item["workflow_name"],
                "changed_step_count": len(item.get("step_changes", [])),
            }
        )

    after_res = backend.request("GET", f"/locations/{lid}")
    after_loc = after_res.get("location", after_res) if isinstance(after_res, dict) else {}
    return {
        "mode": "applied",
        "action": "rebrand_location",
        "company_id": plan.get("company_id"),
        "location_id": lid,
        "location_name": after_loc.get("name"),
        "custom_values_applied": cv_results,
        "trigger_links_applied": link_results,
        "calendars_applied": cal_results,
        "workflows_applied": wf_results,
        "verified": True,
    }


def _mask_secret_value(val: str | None) -> str | None:
    if not val:
        return None
    s = str(val).strip()
    if len(s) <= 10:
        return "***"
    return f"{s[:6]}...{s[-4:]}"


def inspect_agency_workflows_xray(
    backend: BackendClient,
    *,
    location_id: str,
    workflow_id: str | None = None,
    brand_terms: list[str] | None = None,
) -> dict[str, Any]:
    """Deep-inspect internal workflow action steps (email senders/subjects/preheaders, Meta CAPI pixels, webhooks, SMS/notification copy) via GET /workflow/:locationId/:workflowId."""
    lid = valid_id(location_id)
    clean_terms = [t.strip() for t in (brand_terms or []) if t and t.strip()]

    if workflow_id and workflow_id.strip():
        target_wids = [valid_id(workflow_id.strip())]
        wf_list_meta = {target_wids[0]: {}}
    else:
        wf_summary = list_location_workflows_backend(backend, location_id=lid)
        target_wids = [w["id"] for w in wf_summary["workflows"] if w.get("id")]
        wf_list_meta = {w["id"]: w for w in wf_summary["workflows"] if w.get("id")}

    workflows_xray: list[dict[str, Any]] = []
    email_senders_set: set[tuple[str, str]] = set()
    capi_pixels_set: set[str] = set()
    webhook_urls_set: set[str] = set()
    brand_matches: list[dict[str, Any]] = []
    hardcoded_warnings: list[dict[str, Any]] = []
    total_steps = 0

    inspectable_fields = ("from_name", "from_email", "subject", "preHeader", "title", "body", "message", "url", "pixel_id", "event_name")

    for wid in target_wids:
        raw_wf = backend.request("GET", f"/workflow/{lid}/{wid}")
        if not isinstance(raw_wf, dict):
            continue
        wf_name = str(raw_wf.get("name") or wf_list_meta.get(wid, {}).get("name") or "")
        wf_status = str(raw_wf.get("status") or wf_list_meta.get(wid, {}).get("status") or "").lower()
        wf_data = raw_wf.get("workflowData") if isinstance(raw_wf.get("workflowData"), dict) else {}
        templates = wf_data.get("templates") if isinstance(wf_data.get("templates"), list) else []
        triggers = wf_data.get("triggers") if isinstance(wf_data.get("triggers"), list) else []

        if clean_terms:
            name_hits = [t for t in clean_terms if t.lower() in wf_name.lower()]
            if name_hits:
                brand_matches.append(
                    {
                        "workflow_id": wid,
                        "workflow_name": wf_name,
                        "step_id": None,
                        "step_name": None,
                        "step_type": "workflow_header",
                        "field": "name",
                        "value": wf_name,
                        "matched_terms": name_hits,
                    }
                )

        steps_summary: list[dict[str, Any]] = []
        for step in templates:
            if not isinstance(step, dict):
                continue
            total_steps += 1
            sid = str(step.get("id") or "")
            sname = str(step.get("name") or "")
            stype = str(step.get("type") or "")
            attrs = step.get("attributes") if isinstance(step.get("attributes"), dict) else {}

            extracted_attrs: dict[str, Any] = {}
            for k in ("from_name", "from_email", "subject", "preHeader", "template_id", "title", "url", "method", "pixel_id", "event_name", "value", "currency"):
                if attrs.get(k) not in (None, ""):
                    extracted_attrs[k] = attrs.get(k)
            if attrs.get("body") not in (None, ""):
                body_str = str(attrs.get("body"))
                extracted_attrs["body_preview"] = body_str[:160] + ("..." if len(body_str) > 160 else "")
            if attrs.get("access_token") not in (None, ""):
                extracted_attrs["has_access_token"] = True
                extracted_attrs["access_token_masked"] = _mask_secret_value(str(attrs.get("access_token")))

            fn = str(attrs.get("from_name") or "").strip()
            fe = str(attrs.get("from_email") or "").strip()
            if fn or fe:
                email_senders_set.add((fn, fe))
            if fn and "{{" not in fn:
                hardcoded_warnings.append(
                    {
                        "workflow_id": wid,
                        "workflow_name": wf_name,
                        "step_id": sid,
                        "step_name": sname,
                        "step_type": stype,
                        "field": "from_name",
                        "current_value": fn,
                        "recommended_merge_tag": "{{location.name}}",
                    }
                )
            if fe and "{{" not in fe:
                hardcoded_warnings.append(
                    {
                        "workflow_id": wid,
                        "workflow_name": wf_name,
                        "step_id": sid,
                        "step_name": sname,
                        "step_type": stype,
                        "field": "from_email",
                        "current_value": fe,
                        "recommended_merge_tag": "{{location.email}}",
                    }
                )
            if attrs.get("pixel_id"):
                pix_str = str(attrs["pixel_id"]).strip()
                capi_pixels_set.add(pix_str)
                if "{{" not in pix_str:
                    hardcoded_warnings.append(
                        {
                            "workflow_id": wid,
                            "workflow_name": wf_name,
                            "step_id": sid,
                            "step_name": sname,
                            "step_type": stype,
                            "field": "pixel_id",
                            "current_value": pix_str,
                            "recommended_merge_tag": "{{custom_values.meta_pixel_id}}",
                        }
                    )
            if attrs.get("url"):
                url_str = str(attrs["url"]).strip()
                webhook_urls_set.add(url_str)
                if "{{" not in url_str:
                    hardcoded_warnings.append(
                        {
                            "workflow_id": wid,
                            "workflow_name": wf_name,
                            "step_id": sid,
                            "step_name": sname,
                            "step_type": stype,
                            "field": "url",
                            "current_value": url_str,
                            "recommended_merge_tag": "{{custom_values.webhook_url}}",
                        }
                    )

            if clean_terms:
                for fname in inspectable_fields:
                    fval = attrs.get(fname)
                    if isinstance(fval, str) and fval.strip():
                        hits = [t for t in clean_terms if t.lower() in fval.lower()]
                        if hits:
                            brand_matches.append(
                                {
                                    "workflow_id": wid,
                                    "workflow_name": wf_name,
                                    "step_id": sid,
                                    "step_name": sname,
                                    "step_type": stype,
                                    "field": fname,
                                    "value": fval[:200],
                                    "matched_terms": hits,
                                }
                            )

            steps_summary.append(
                {
                    "id": sid,
                    "name": sname,
                    "type": stype,
                    "attributes": extracted_attrs,
                }
            )

        workflows_xray.append(
            {
                "id": wid,
                "name": wf_name,
                "status": wf_status,
                "version": raw_wf.get("version"),
                "trigger_count": len(triggers),
                "step_count": len(steps_summary),
                "triggers": [
                    {
                        "id": str(tr.get("id") or ""),
                        "name": str(tr.get("name") or ""),
                        "type": str(tr.get("type") or ""),
                    }
                    for tr in triggers
                    if isinstance(tr, dict)
                ],
                "steps": steps_summary,
            }
        )

    return {
        "location_id": lid,
        "workflow_count": len(workflows_xray),
        "total_step_count": total_steps,
        "snapshot_portable": len(hardcoded_warnings) == 0,
        "hardcoded_step_warning_count": len(hardcoded_warnings),
        "hardcoded_step_warnings": hardcoded_warnings,
        "email_senders": [{"from_name": fn, "from_email": fe} for fn, fe in sorted(email_senders_set)],
        "capi_pixel_ids": sorted(capi_pixels_set),
        "webhook_urls": sorted(webhook_urls_set),
        "brand_terms_checked": clean_terms,
        "brand_match_count": len(brand_matches),
        "brand_matches": brand_matches,
        "workflows": workflows_xray,
        "token_source": backend.token_source,
    }


def make_workflow_steps_rebrand_plan(
    backend: BackendClient,
    *,
    location_id: str,
    workflow_ids: list[str] | None = None,
    replace_pairs: list[tuple[str, str]] | None = None,
    from_name: str | None = None,
    from_email: str | None = None,
    pixel_id: str | None = None,
    capi_access_token: str | None = None,
    templatize_senders: bool = False,
) -> dict[str, Any]:
    """Build a preview plan to bulk-update internal workflow steps (email from_name/from_email/subject/preHeader, notification copy, webhook URLs, Meta CAPI pixel_id/access_token) via PUT /workflow/:locationId/:workflowId."""
    lid = valid_id(location_id)
    clean_pairs = [(str(k).strip(), str(v).strip()) for k, v in (replace_pairs or []) if str(k).strip()]
    clean_from_name = (
        "{{location.name}}"
        if templatize_senders and not (from_name and from_name.strip())
        else (from_name.strip() if from_name and from_name.strip() else None)
    )
    clean_from_email = (
        "{{location.email}}"
        if templatize_senders and not (from_email and from_email.strip())
        else (from_email.strip() if from_email and from_email.strip() else None)
    )
    clean_pixel_id = pixel_id.strip() if pixel_id and pixel_id.strip() else None
    clean_capi_token = capi_access_token.strip() if capi_access_token and capi_access_token.strip() else None

    if not any([clean_pairs, clean_from_name, clean_from_email, clean_pixel_id, clean_capi_token]):
        raise HighLevelError(
            "Provide at least one workflow step update (--replace OLD=NEW, --from-name, --from-email, --pixel-id, or --capi-access-token)."
        )

    if workflow_ids:
        target_wids = [valid_id(w.strip()) for w in workflow_ids if w and w.strip()]
    else:
        wf_summary = list_location_workflows_backend(backend, location_id=lid)
        target_wids = [w["id"] for w in wf_summary["workflows"] if w.get("id")]

    workflow_mutations: list[dict[str, Any]] = []
    replaceable_fields = ("from_name", "from_email", "subject", "preHeader", "title", "body", "message", "url")

    for wid in target_wids:
        raw_wf = backend.request("GET", f"/workflow/{lid}/{wid}")
        if not isinstance(raw_wf, dict):
            continue
        wf_copy = json.loads(json.dumps(raw_wf))
        wf_name = str(wf_copy.get("name") or "")
        wf_data = wf_copy.get("workflowData")
        if not isinstance(wf_data, dict):
            continue
        templates = wf_data.get("templates")
        if not isinstance(templates, list):
            continue

        step_changes: list[dict[str, Any]] = []
        for step in templates:
            if not isinstance(step, dict):
                continue
            sid = str(step.get("id") or "")
            sname = str(step.get("name") or "")
            stype = str(step.get("type") or "")
            attrs = step.get("attributes")
            if not isinstance(attrs, dict):
                continue

            if clean_from_name is not None and (stype == "email" or "from_name" in attrs):
                old_v = str(attrs.get("from_name") or "")
                if old_v != clean_from_name:
                    attrs["from_name"] = clean_from_name
                    step_changes.append(
                        {
                            "step_id": sid,
                            "step_name": sname,
                            "step_type": stype,
                            "field": "from_name",
                            "before": old_v,
                            "after": clean_from_name,
                        }
                    )

            if clean_from_email is not None and (stype == "email" or "from_email" in attrs):
                old_v = str(attrs.get("from_email") or "")
                if old_v != clean_from_email:
                    attrs["from_email"] = clean_from_email
                    step_changes.append(
                        {
                            "step_id": sid,
                            "step_name": sname,
                            "step_type": stype,
                            "field": "from_email",
                            "before": old_v,
                            "after": clean_from_email,
                        }
                    )

            if clean_pixel_id is not None and stype == "facebook_conversion_api":
                old_v = str(attrs.get("pixel_id") or "")
                if old_v != clean_pixel_id:
                    attrs["pixel_id"] = clean_pixel_id
                    step_changes.append(
                        {
                            "step_id": sid,
                            "step_name": sname,
                            "step_type": stype,
                            "field": "pixel_id",
                            "before": old_v,
                            "after": clean_pixel_id,
                        }
                    )

            if clean_capi_token is not None and stype == "facebook_conversion_api":
                old_v = str(attrs.get("access_token") or "")
                if old_v != clean_capi_token:
                    attrs["access_token"] = clean_capi_token
                    step_changes.append(
                        {
                            "step_id": sid,
                            "step_name": sname,
                            "step_type": stype,
                            "field": "access_token",
                            "before": _mask_secret_value(old_v),
                            "after": _mask_secret_value(clean_capi_token),
                        }
                    )

            if clean_pairs:
                for fname in replaceable_fields:
                    if fname == "from_name" and clean_from_name is not None:
                        continue
                    if fname == "from_email" and clean_from_email is not None:
                        continue
                    old_val = attrs.get(fname)
                    if isinstance(old_val, str) and old_val:
                        new_val = _apply_backend_replacements(old_val, clean_pairs)
                        if new_val != old_val:
                            attrs[fname] = new_val
                            step_changes.append(
                                {
                                    "step_id": sid,
                                    "step_name": sname,
                                    "step_type": stype,
                                    "field": fname,
                                    "before": old_val[:160],
                                    "after": new_val[:160],
                                }
                            )

        if step_changes:
            put_payload = {
                "name": wf_copy.get("name"),
                "status": wf_copy.get("status"),
                "workflowData": wf_copy.get("workflowData"),
                "settings": wf_copy.get("settings"),
                "updatedBy": backend.worker_user_id or wf_copy.get("updatedBy"),
            }
            workflow_mutations.append(
                {
                    "workflow_id": wid,
                    "workflow_name": wf_name,
                    "step_changes": step_changes,
                    "request": {
                        "method": "PUT",
                        "path": f"/workflow/{lid}/{wid}",
                        "payload": put_payload,
                    },
                }
            )

    plan_core = {
        "resource": "workflow_steps_rebrand",
        "action": "rebrand_workflow_steps",
        "location_id": lid,
        "workflows_inspected": len(target_wids),
        "workflows_to_update": len(workflow_mutations),
        "total_step_changes": sum(len(m["step_changes"]) for m in workflow_mutations),
        "workflow_mutations": workflow_mutations,
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_workflow_steps_rebrand_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")

    lid = valid_id(plan["location_id"])
    applied_workflows = []
    for item in plan.get("workflow_mutations", []):
        req = item["request"]
        res = backend.request(req["method"], req["path"], body=req["payload"])
        applied_workflows.append(
            {
                "workflow_id": item["workflow_id"],
                "workflow_name": item["workflow_name"],
                "step_change_count": len(item.get("step_changes", [])),
                "after_version": res.get("version") if isinstance(res, dict) else None,
            }
        )

    return {
        "mode": "applied",
        "action": "rebrand_workflow_steps",
        "location_id": lid,
        "workflows_updated": len(applied_workflows),
        "results": applied_workflows,
        "verified": True,
    }


def make_snapshot_share_link_plan(
    backend: BackendClient,
    *,
    snapshot_id: str,
    share_type: str = "link",
    company_id: str | None = None,
    relationship_number: str | None = None,
    share_location_id: str | None = None,
) -> dict[str, Any]:
    """Build a preview plan to generate a shareable snapshot link via POST /snapshots/share/v2/link."""
    sid = valid_id(snapshot_id)
    cid = _require_company_id(backend, company_id)
    clean_share_type = (share_type or "link").strip().lower()
    if clean_share_type not in {"link", "permanent_link", "agency_restricted", "location_restricted"}:
        raise HighLevelError(
            "Snapshot --share-type must be 'link', 'permanent_link', 'agency_restricted', or 'location_restricted'."
        )
    payload: dict[str, Any] = {
        "snapshot_id": sid,
        "share_type": clean_share_type,
        "company_id": cid,
    }
    if relationship_number and relationship_number.strip():
        payload["relationship_number"] = relationship_number.strip()
    if share_location_id and share_location_id.strip():
        payload["share_location_id"] = valid_id(share_location_id.strip())

    plan_core = {
        "resource": "agency_snapshot_share_link",
        "action": "create_share_link",
        "company_id": cid,
        "snapshot_id": sid,
        "share_type": clean_share_type,
        "proposed_request": {
            "method": "POST",
            "path": "/snapshots/share/v2/link",
            "query": {"companyId": cid},
            "payload": payload,
        },
    }
    return {**plan_core, "sha256": plan_digest(plan_core)}


def apply_snapshot_share_link_plan(
    backend: BackendClient,
    plan: dict[str, Any],
    *,
    confirm_plan: str,
) -> dict[str, Any]:
    if confirm_plan != plan.get("sha256"):
        raise HighLevelError("--confirm-plan hash does not match the current preview state; re-run preview.")
    req = plan["proposed_request"]
    res = backend.request(req["method"], req["path"], body=req["payload"], query=req["query"])
    return {
        "mode": "applied",
        "action": "create_share_link",
        "company_id": plan["company_id"],
        "snapshot_id": plan["snapshot_id"],
        "share_type": plan["share_type"],
        "share_link": res.get("shareLink") or res.get("link") if isinstance(res, dict) else None,
        "verified": True,
        "response": res,
    }

