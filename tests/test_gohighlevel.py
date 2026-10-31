"""Offline unit test suite for legends-gohighlevel."""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legends_gohighlevel.agency import (
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
    make_location_unnerf_plan,
    make_rebilling_sync_plan,
    make_smtp_unlock_plan,
    make_unlock_dashboards_plan,
    make_user_sync_locations_plan,
    make_user_unnerf_plan,
)
from legends_gohighlevel.api import API_VERSION, API_VERSION_V3, BackendClient, Client, HighLevelError, NoRedirect, valid_id
from legends_gohighlevel.cli import execute, main, parser
from legends_gohighlevel.crm import (
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
    list_conversation_ai_agents,
    list_funnels,
    list_objects,
    list_tags,
    list_voice_ai_agents,
    list_voice_ai_calls,
    list_workflow_logs,
    list_workflow_step_types,
    make_contact_note_plan,
    make_contact_tag_plan,
    make_contact_upsert_plan,
    make_custom_value_plan,
    make_opportunity_update_plan,
    make_tag_plan,
    make_workflow_status_plan,
    search_contacts,
    search_object_records,
    subaccount_audit,
    validate_workflow_definition,
)
from legends_gohighlevel.governance import (
    CRITICAL_ACCOUNT_ADMIN_V2_SCOPES,
    DEFAULT_DASHBOARD_PERMISSION_ACCESS,
    MUTUALLY_EXCLUSIVE_V2_SCOPES,
    SAAS_BILLING_V2_KEYS,
    UNNERFED_LOCATION_PERMISSIONS,
    UNNERFED_V1_PERMISSIONS,
    dashboard_permission_audit,
    markup_to_multiplier,
    multiplier_to_markup,
    rebilling_audit,
    scope_audit,
    smtp_audit,
)


class FakeClient:
    """In-memory mock client for deterministic CRM and mutation tests."""

    def __init__(self, location_id: str = "loc_test_12345678"):
        self.location_id = location_id
        self.auth_kind = "pit"
        self.last_rate_limits = {"burst_remaining": 99, "daily_remaining": 199990}
        self.custom_values: list[dict] = [
            {
                "id": "cv_existing_01",
                "name": "Support Email",
                "fieldKey": "{{ custom_values.support_email }}",
                "value": "old@example.com",
            }
        ]
        self.tags_store: list[dict] = [{"id": "tag_01____", "name": "vip"}]
        self.contact_tags: list[str] = ["vip"]
        self.opp_store = {
            "id": "opp_12345678",
            "name": "Deal A",
            "status": "open",
            "pipelineId": "pip_01____",
            "pipelineStageId": "stg_01____",
            "monetaryValue": 1000.0,
        }
        self.calls: list[tuple[str, str, dict | None, dict | None]] = []

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
        version: str = API_VERSION,
    ) -> dict:
        self.calls.append((method, path, body, query))
        if method == "GET" and path == f"/locations/{self.location_id}/customValues":
            return {"customValues": [dict(item) for item in self.custom_values]}
        if method == "POST" and path == f"/locations/{self.location_id}/customValues":
            assert body is not None
            created = {
                "id": "cv_created_99",
                "name": body["name"],
                "fieldKey": "{{ custom_values.created_99 }}",
                "value": body["value"],
            }
            self.custom_values.append(created)
            return {"customValue": created}
        if method == "PUT" and path.startswith(f"/locations/{self.location_id}/customValues/"):
            assert body is not None
            cid = path.rsplit("/", 1)[-1]
            for item in self.custom_values:
                if item["id"] == cid:
                    item["name"] = body["name"]
                    item["value"] = body["value"]
                    return {"customValue": dict(item)}
            raise HighLevelError("Not found")
        if method == "DELETE" and path.startswith(f"/locations/{self.location_id}/customValues/"):
            cid = path.rsplit("/", 1)[-1]
            self.custom_values = [item for item in self.custom_values if item["id"] != cid]
            return {"succeeded": True}
        if method == "GET" and path == "/contacts/":
            return {
                "contacts": [
                    {
                        "id": "cnt_12345678",
                        "type": "lead",
                        "tags": ["vip"],
                        "dateAdded": "2026-10-22T00:00:00Z",
                        "contactName": "Jane Doe",
                        "firstName": "Jane",
                        "lastName": "Doe",
                        "email": "jane@example.com",
                        "phone": "+15550109999",
                    }
                ]
            }
        if method == "GET" and path == f"/locations/{self.location_id}":
            return {
                "location": {
                    "id": self.location_id,
                    "name": "Test Subaccount",
                    "email": "hello@example.com",
                    "website": "https://example.com",
                    "address": "123 Main St",
                    "city": "Austin",
                    "state": "TX",
                    "postalCode": "78701",
                    "timezone": "America/Chicago",
                }
            }
        if method == "GET" and path == f"/locations/{self.location_id}/customFields":
            return {"customFields": []}
        if method == "GET" and path == "/opportunities/pipelines":
            return {"pipelines": [{"id": "pip_01____", "name": "Main", "stages": []}]}
        if method == "GET" and path == "/opportunities/search":
            return {"opportunities": [dict(self.opp_store)]}
        if method == "GET" and path == "/opportunities/opp_12345678":
            return {"opportunity": dict(self.opp_store)}
        if method == "PUT" and path == "/opportunities/opp_12345678":
            assert body is not None
            self.opp_store.update(body)
            return {"opportunity": dict(self.opp_store)}
        if method == "GET" and path == "/calendars/":
            return {"calendars": [{"id": "cal_12345678", "name": "Booking", "calendarType": "round_robin", "isActive": True}]}
        if method == "GET" and path == "/calendars/cal_12345678/free-slots":
            return {"2026-11-01": {"slots": ["2026-11-01T14:00:00Z"]}}
        if method == "GET" and path == "/forms/":
            return {"forms": []}
        if method == "GET" and path == "/surveys/":
            return {"surveys": []}
        if method == "GET" and path == f"/locations/{self.location_id}/tags":
            return {"tags": [dict(t) for t in self.tags_store]}
        if method == "POST" and path == f"/locations/{self.location_id}/tags":
            assert body is not None
            new_t = {"id": "tag_created_99", "name": body["name"]}
            self.tags_store.append(new_t)
            return {"tag": new_t}
        if method == "GET" and path == f"/locations/{self.location_id}/tags/tag_created_99":
            return {"tag": {"id": "tag_created_99", "name": self.tags_store[-1]["name"]}}
        if method == "DELETE" and path == f"/locations/{self.location_id}/tags/tag_created_99":
            self.tags_store = [t for t in self.tags_store if t["id"] != "tag_created_99"]
            return {"succeeded": True}
        if method == "POST" and path == "/contacts/upsert":
            return {"contact": {"id": "cnt_12345678", "tags": list(self.contact_tags)}, "new": False}
        if method == "GET" and path == "/contacts/cnt_12345678":
            return {"contact": {"id": "cnt_12345678", "tags": list(self.contact_tags), "dateUpdated": "2026-10-31T00:00:00Z"}}
        if method == "POST" and path == "/contacts/cnt_12345678/tags":
            assert body is not None
            for t in body.get("tags", []):
                if t not in self.contact_tags:
                    self.contact_tags.append(t)
            return {"tags": list(self.contact_tags)}
        if method == "DELETE" and path == "/contacts/cnt_12345678/tags":
            assert body is not None
            rem = {t.lower() for t in body.get("tags", [])}
            self.contact_tags = [t for t in self.contact_tags if t.lower() not in rem]
            return {"tags": list(self.contact_tags)}
        if method == "POST" and path == "/contacts/cnt_12345678/notes":
            return {"note": {"id": "note_12345678", "body": (body or {}).get("body")}}
        if method == "GET" and path == "/funnels/funnel/list":
            return {"funnels": [{"_id": "fnl_01", "name": "Main Funnel", "type": "funnel", "steps": [{}]}]}
        if method == "GET" and path == "/funnels/lookup/redirect/list":
            return {"data": [{"id": "red_01", "domain": "example.com", "path": "/go", "target": "https://example.com/offer", "action": "funnel"}]}
        if method == "GET" and path == "/objects/":
            return {"objects": [{"id": "obj_01", "key": "custom_objects.vehicles", "labels": {"singular": "Vehicle", "plural": "Vehicles"}, "standard": False}]}
        if method == "POST" and path == "/objects/custom_objects.vehicles/records/search":
            return {"records": [{"id": "rec_01", "objectKey": "custom_objects.vehicles", "properties": {"vin": "12345"}}], "total": 1}
        if method == "GET" and path == "/associations/":
            return {"associations": [{"id": "asc_01", "key": "contact_vehicle", "associationType": "USER_DEFINED", "firstObjectKey": "contact", "secondObjectKey": "custom_objects.vehicles"}]}
        if method == "GET" and path == "/voice-ai/agents":
            return {"agents": [{"id": "vai_01", "name": "Receptionist", "status": "active", "voiceId": "v_1"}], "total": 1}
        if method == "GET" and path == "/voice-ai/dashboard/call-logs":
            return {"callLogs": [{"id": "call_01", "agentId": "vai_01", "contactId": "cnt_12345678", "status": "completed", "duration": 42}], "totalRecords": 1}
        if method == "GET" and path == "/conversation-ai/agents/search":
            return {"agents": [{"id": "cai_01", "name": "Support Bot", "status": "published", "mode": "autopilot"}], "totalCount": 1}
        if method == "GET" and path == "/workflows/":
            return {"workflows": [{"id": "wf_12345678", "name": "Lead Nurture", "status": "draft", "version": 2}]}
        if version == API_VERSION_V3 and method == "GET" and path == "/workflows/step-types":
            return {"stepTypes": [{"type": "send_sms", "category": "action"}]}
        if version == API_VERSION_V3 and method == "GET" and path == "/workflows/wf_12345678/definition":
            return {"definition": {"id": "wf_12345678", "name": "Lead Nurture", "steps": []}}
        if version == API_VERSION_V3 and method == "GET" and path == "/workflows/wf_12345678/logs":
            return {"logs": [{"id": "log_01", "status": "completed"}]}
        if version == API_VERSION_V3 and method == "POST" and path == "/workflows/definition/validate":
            return {"valid": True, "errors": []}
        if version == API_VERSION_V3 and method == "PUT" and path == "/workflows/wf_12345678/status":
            return {"id": "wf_12345678", "status": (body or {}).get("status", "published")}
        return {}


class FakeBackendClient:
    """In-memory mock client for HighLevel internal backend (backend.leadconnectorhq.com)."""

    def __init__(self, company_id: str | None = "cmp_test_12345678"):
        self.company_id = company_id or "cmp_test_12345678"
        self.token_source = "mock:test"
        self.locations = {
            "loc_alpha_1234": {
                "id": "loc_alpha_1234",
                "_id": "loc_alpha_1234",
                "name": "Alpha Subaccount",
                "email": "alpha@example.com",
                "phone": "+15550001111",
                "companyId": self.company_id,
                "timezone": "America/New_York",
                "settings": {
                    "allowDuplicateContact": False,
                    "saasSettings": {
                        "saasMode": "setup_pending",
                        "stripeCustomerId": "cus_test_123",
                        "twilioRebilling": {"enabled": False, "markup": 10},
                    },
                },
                "reseller": {},
                "permissions": {"workflowsEnabled": True, "dashboardStatsEnabled": True},
            }
        }
        self.location_metadata = {
            "loc_alpha_1234": {
                "locationId": "loc_alpha_1234",
                "companyId": self.company_id,
                "saasMode": "setup_pending",
                "stripeCustomerId": "cus_test_123",
                "twilioRebilling": {"enabled": False, "markup": 10},
            }
        }
        self.saas_billing_v2 = {
            "loc_alpha_1234": {
                k: {"enabled": False, "optIn": False, "markup": 5}
                for k in SAAS_BILLING_V2_KEYS
            }
        }
        excluded = {pair[0] for pair in MUTUALLY_EXCLUSIVE_V2_SCOPES}
        full_scopes = [s for s in CRITICAL_ACCOUNT_ADMIN_V2_SCOPES if s not in excluded]
        self.users = {
            "usr_primary_1234": {
                "id": "usr_primary_1234",
                "name": "Member One",
                "email": "member@example.com",
                "roles": {"type": "account", "role": "admin", "locationIds": ["loc_alpha_1234"]},
                "permissions": dict(UNNERFED_V1_PERMISSIONS),
                "scopes": list(full_scopes),
            },
            "usr_alias_1234": {
                "id": "usr_alias_1234",
                "name": "Member One Alias",
                "email": "member+hubpro@example.com",
                "roles": {
                    "type": "account",
                    "role": "admin",
                    "locationIds": ["loc_alpha_1234", "loc_beta_5678"],
                },
                "permissions": dict(UNNERFED_V1_PERMISSIONS),
                "scopes": list(full_scopes),
            },
        }
        self.dashboard_perms = {
            "dash_default_1234": [
                {"role": "agency_user", "permission": "full"},
                {"role": "account_user", "permission": "read"},
            ]
        }
        self.smtp_blocked = {"loc_alpha_1234": True}

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
    ) -> dict:
        if method == "GET" and path == "/locations/search":
            return {"locations": list(self.locations.values())}
        if method == "GET" and path.startswith("/locations/"):
            lid = path.rsplit("/", 1)[-1]
            return {"location": dict(self.locations[lid])}
        if method == "PUT" and path.startswith("/locations/"):
            assert body is not None
            lid = path.rsplit("/", 1)[-1]
            if "name" in body:
                self.locations[lid]["name"] = body["name"]
            if "permissions" in body:
                self.locations[lid]["permissions"] = dict(body["permissions"])
                if not self.locations[lid].get("reseller"):
                    self.locations[lid]["reseller"] = {"active": True}
            if "settings" in body and isinstance(body["settings"], dict):
                cur_set = dict(self.locations[lid].get("settings") or {})
                if "saasSettings" in body["settings"]:
                    cur_saas = dict(cur_set.get("saasSettings") or {})
                    cur_saas.update(body["settings"]["saasSettings"])
                    cur_set["saasSettings"] = cur_saas
                self.locations[lid]["settings"] = cur_set
            return {"location": dict(self.locations[lid])}
        if method == "GET" and path.startswith("/saas-api/location-metadata/"):
            lid = path.rsplit("/", 1)[-1]
            return {"data": dict(self.location_metadata[lid])}
        if method == "PUT" and path.startswith("/saas-api/location-metadata/"):
            assert body is not None
            lid = path.rsplit("/", 1)[-1]
            self.location_metadata[lid].update(body)
            return {"data": dict(self.location_metadata[lid])}
        if method == "GET" and path.startswith("/saas-billing-v2/billing-config/LOCATION/"):
            lid = path.rsplit("/", 1)[-1]
            cfg_map = self.saas_billing_v2.get(lid, {})
            return {
                "data": [
                    {"product": k, "config": dict(v)}
                    for k, v in cfg_map.items()
                ]
            }
        if method == "PUT" and path.startswith("/saas-billing-v2/billing-config/group/"):
            assert body is not None
            parts = path.split("/")
            lid = parts[4]
            markups = body.get("markups") or {}
            enabled = bool(body.get("enabled", True))
            opt_in = bool(body.get("optIn", True))
            for k, mk in markups.items():
                self.saas_billing_v2[lid][k] = {"enabled": enabled, "optIn": opt_in, "markup": int(mk)}
            return {"message": "Config updated successfully"}
        if method == "POST" and path.endswith("/update-twilio-rebilling"):
            return {"ok": True, "message": "OK"}
        if method == "GET" and path.startswith("/marketplace/private-integration/location/"):
            return [{"_id": "pit_01", "name": "CRM Sync", "activeToken": "pit-****1234", "scopes": ["contacts.write"]}]
        if method == "GET" and path == "/email-isv/feature/domain/list":
            return [{"domain": "mail.example.com", "status": "verified"}]
        if method == "GET" and path == "/conversations/providers/mailgun/fetch":
            return {"domain": "mail.example.com"}
        if method == "GET" and path == "/users/search":
            return {"users": list(self.users.values())}
        if method == "GET" and path == "/users/permissions":
            excluded = {pair[0] for pair in MUTUALLY_EXCLUSIVE_V2_SCOPES}
            uid = (query or {}).get("userId", "usr_primary_1234")
            cur_scopes = set(self.users[uid]["scopes"])
            catalog = {}
            for s in CRITICAL_ACCOUNT_ADMIN_V2_SCOPES:
                catalog[s] = {
                    "enabled": (s not in excluded) and (s in cur_scopes),
                    "userConfig": {"assignedToSupported": False},
                }
            return {"permissions": catalog}
        if method == "GET" and path.startswith("/users/"):
            uid = path.rsplit("/", 1)[-1]
            return dict(self.users[uid])
        if method == "PUT" and path.startswith("/users/"):
            assert body is not None
            uid = path.rsplit("/", 1)[-1]
            if "locationIds" in body:
                self.users[uid]["roles"]["locationIds"] = list(body["locationIds"])
            if "permissions" in body:
                self.users[uid]["permissions"] = dict(body["permissions"])
            if "scopes" in body:
                self.users[uid]["scopes"] = list(body["scopes"])
            return dict(self.users[uid])
        if method == "GET" and path == "/email-isv/onload":
            lid = (query or {}).get("locationId", "loc_alpha_1234")
            return {"blockAddSmtp": self.smtp_blocked.get(lid, False), "hasLcEmail": True}
        if method == "PUT" and path.startswith("/email-isv/Setting/feature/company/"):
            return {"ok": True}
        if method == "PUT" and path.startswith("/email-isv/Setting/feature/location/"):
            assert body is not None
            lid = path.rsplit("/", 1)[-1]
            self.smtp_blocked[lid] = bool(body.get("blockAddSmtp", False))
            return {"ok": True}
        if method == "GET" and path == "/reporting/dashboards":
            return {
                "data": {
                    "defaultDashboardId": "dash_default_1234",
                    "sharedDashboards": [{"_id": "dash_default_1234", "title": "Default", "isDefault": True}],
                }
            }
        if method == "GET" and path == "/reporting/dashboards/dash_default_1234/permissions":
            return {
                "data": {
                    "isPrivate": False,
                    "permission": [dict(x) for x in self.dashboard_perms["dash_default_1234"]],
                }
            }
        if method == "POST" and path == "/reporting/dashboards/dash_default_1234/permissions":
            assert body is not None
            self.dashboard_perms["dash_default_1234"] = [
                dict(x) for x in body.get("permissionAccess", [])
            ]
            return {"data": {"permission": self.dashboard_perms["dash_default_1234"]}}
        raise HighLevelError(f"Unhandled mock backend route: {method} {path}")


class GovernanceTests(unittest.TestCase):
    def test_rebilling_multiplier_math_and_stripe_shield(self) -> None:
        self.assertEqual(markup_to_multiplier(5), 1.05)
        self.assertEqual(markup_to_multiplier(0), 1.0)
        self.assertEqual(multiplier_to_markup(1.05), 5)
        self.assertEqual(multiplier_to_markup(1.0), 0)

        res_safe = rebilling_audit(wallet_topup_usd=10.0, markup=5, location_id="loc_12345678")
        self.assertEqual(res_safe["ui_multiplier"], 1.05)
        self.assertEqual(res_safe["stripe_processing_fee_usd"], 0.59)
        self.assertEqual(res_safe["agency_received_after_stripe_usd"], 9.41)
        self.assertEqual(res_safe["wholesale_usage_unlocked_usd"], 9.5238)
        self.assertEqual(res_safe["agency_net_after_stripe_and_usage_usd"], -0.1138)
        self.assertFalse(res_safe["agency_loss_risk"])
        self.assertIn("saas_billing_v2", res_safe["four_store_sync_blueprint"])
        self.assertIn("twilio_rebilling", res_safe["four_store_sync_blueprint"])
        self.assertIn("mailgun_rebilling", res_safe["four_store_sync_blueprint"])
        self.assertIn("location_metadata", res_safe["four_store_sync_blueprint"])

        res_zero = rebilling_audit(wallet_topup_usd=10.0, markup=0, location_id="loc_12345678")
        self.assertEqual(res_zero["ui_multiplier"], 1.0)
        self.assertEqual(res_zero["agency_net_after_stripe_and_usage_usd"], -0.59)
        self.assertTrue(res_zero["agency_loss_risk"])
        self.assertIn("WARNING", res_zero["recommendation"])

    def test_scope_audit_mutual_exclusions_and_worker_inheritance(self) -> None:
        audit = scope_audit(
            role="admin",
            account_type="account",
            current_scopes=["contacts.write", "workflows.readonly", "workflows.write"],
            creator_scopes=["contacts.write", "opportunities.write"],
        )
        self.assertEqual(audit["required_update_source"], "agency_team")
        self.assertEqual(audit["recommended_v2_scope_count"], 130)
        self.assertNotIn("workflows.readonly", audit["recommended_v2_scopes"])
        self.assertNotIn("campaigns.readonly", audit["recommended_v2_scopes"])
        self.assertIn("workflows.readonly + workflows.write", audit["mutual_exclusion_conflicts"])
        self.assertIn("campaigns.write", audit["missing_v2_scopes_on_user"])
        self.assertIn("workflows.write", audit["worker_inheritance_stripped_scopes"])
        self.assertTrue(audit["unnerfed_v1_permissions"]["botService"])
        self.assertFalse(audit["unnerfed_v1_permissions"]["adPublishingReadOnly"])

    def test_smtp_audit_two_level_unlock(self) -> None:
        res = smtp_audit(
            company_id="cmp_12345678",
            location_id="loc_12345678",
            company_block_add_smtp=False,
            location_block_add_smtp=False,
        )
        self.assertIs(res["add_service_button_unlocked"], True)
        self.assertEqual(
            res["agency_unlock_request"]["path"],
            "/email-isv/Setting/feature/company/cmp_12345678",
        )
        self.assertEqual(
            res["location_unlock_request"]["path"],
            "/email-isv/Setting/feature/location/loc_12345678",
        )

    def test_dashboard_permission_audit(self) -> None:
        res_locked = dashboard_permission_audit(
            location_id="loc_12345678",
            dashboard_id="dash_12345678",
            current_permissions=[
                {"role": "agency_user", "permission": "full"},
                {"role": "account_user", "permission": "read"},
            ],
        )
        self.assertFalse(res_locked["account_admin_full_verified"])
        self.assertFalse(res_locked["account_user_full_verified"])
        self.assertEqual(
            res_locked["unlock_request"]["payload"]["permissionAccess"],
            list(DEFAULT_DASHBOARD_PERMISSION_ACCESS),
        )

        res_unlocked = dashboard_permission_audit(
            location_id="loc_12345678",
            dashboard_id="dash_12345678",
            current_permissions=list(DEFAULT_DASHBOARD_PERMISSION_ACCESS),
        )
        self.assertTrue(res_unlocked["account_admin_full_verified"])
        self.assertTrue(res_unlocked["account_user_full_verified"])


class TransportAndSafetyTests(unittest.TestCase):
    def test_valid_id_and_client_bounds(self) -> None:
        self.assertEqual(valid_id("loc_12345678"), "loc_12345678")
        with self.assertRaises(HighLevelError):
            valid_id("bad/id")
        with self.assertRaises(HighLevelError):
            Client(token="short", location_id="loc_12345678")
        with self.assertRaises(HighLevelError):
            Client(token="pit-valid-token-value-12345", location_id="")

        client = Client(token="pit-valid-token-value-12345", location_id="loc_12345678")
        self.assertEqual(client.auth_kind, "pit")
        with self.assertRaises(HighLevelError):
            client.request("GET", "/arbitrary/endpoint")
        with self.assertRaises(HighLevelError):
            client.request("POST", "/workflows/", body={})

    def test_backend_client_bounds(self) -> None:
        bclient = BackendClient(token_id="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.valid.token", company_id="cmp_12345678")
        self.assertEqual(bclient.token_source, "env:GHL_TOKEN_ID")
        with self.assertRaises(HighLevelError):
            bclient.request("GET", "/arbitrary/internal/path")
        with self.assertRaises(HighLevelError):
            bclient.request("POST", "/locations/search", body={})

    def test_no_redirect_refuses_forwarding(self) -> None:
        handler = NoRedirect()
        with self.assertRaises(HighLevelError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://example.com")

    def test_http_error_sanitizes_provider_body(self) -> None:
        client = Client(token="pit-valid-token-value-12345", location_id="loc_12345678")
        err = urllib.error.HTTPError(
            url="https://services.leadconnectorhq.com/locations/loc_12345678",
            code=401,
            msg="Unauthorized",
            hdrs={"x-ratelimit-remaining": "95"},
            fp=io.BytesIO(b'{"secret":"should-never-appear"}'),
        )
        with patch.object(client.opener, "open", side_effect=err):
            with self.assertRaises(HighLevelError) as ctx:
                client.request("GET", "/locations/loc_12345678")
        self.assertNotIn("should-never-appear", str(ctx.exception))
        self.assertEqual(client.last_rate_limits.get("burst_remaining"), 95)


class AgencyBackendControlTests(unittest.TestCase):
    def test_agency_audit_and_unlock_dashboards_and_sync_locations(self) -> None:
        fb = FakeBackendClient()
        # Simulate a nerfed user missing forms.write
        fb.users["usr_primary_1234"]["scopes"] = [
            s for s in fb.users["usr_primary_1234"]["scopes"] if s != "forms.write"
        ]

        # Initial audit should detect nerfed location flags, nerfed user, out-of-sync +hubpro alias, locked dashboard, locked SMTP, and rebilling drift
        audit_before = live_agency_audit(fb)
        self.assertFalse(audit_before["ok"])
        layers = [issue["layer"] for issue in audit_before["issues"]]
        self.assertIn("location_permissions", layers)
        self.assertIn("user_scopes", layers)
        self.assertIn("user_alias_sync", layers)
        self.assertIn("dashboard_rbac", layers)
        self.assertIn("custom_smtp_lock", layers)
        self.assertIn("rebilling_config", layers)

        # Unnerf location feature flags via preview + apply
        loc_plan = make_location_unnerf_plan(fb, all_locations=True)
        self.assertEqual(loc_plan["target_count"], 1)
        self.assertFalse(loc_plan["targets"][0]["already_healthy"])
        loc_applied = apply_location_unnerf_plan(fb, loc_plan, confirm_plan=loc_plan["sha256"])
        self.assertTrue(loc_applied["verified"])

        # Sync 4-store rebilling via preview + apply
        reb_plan = make_rebilling_sync_plan(fb, all_locations=True, markup=5)
        self.assertEqual(reb_plan["target_count"], 1)
        self.assertFalse(reb_plan["targets"][0]["already_healthy"])
        reb_applied = apply_rebilling_sync_plan(fb, reb_plan, confirm_plan=reb_plan["sha256"])
        self.assertTrue(reb_applied["verified"])

        # Unnerf user via preview + apply
        unnerf_plan = make_user_unnerf_plan(fb, user_id="usr_primary_1234")
        self.assertFalse(unnerf_plan["already_healthy"])
        unnerf_applied = apply_user_unnerf_plan(
            fb,
            unnerf_plan,
            confirm_user="usr_primary_1234",
            confirm_plan=unnerf_plan["sha256"],
        )
        self.assertTrue(unnerf_applied["verified"])

        # Unlock Custom SMTP via preview + apply
        smtp_plan = make_smtp_unlock_plan(fb, all_locations=True)
        self.assertEqual(smtp_plan["target_count"], 1)
        smtp_applied = apply_smtp_unlock_plan(fb, smtp_plan, confirm_plan=smtp_plan["sha256"])
        self.assertTrue(smtp_applied["verified"])

        # Unlock default dashboards via preview + apply
        dash_plan = make_unlock_dashboards_plan(fb, all_locations=True)
        self.assertEqual(dash_plan["target_count"], 1)
        self.assertFalse(dash_plan["targets"][0]["already_healthy"])
        dash_applied = apply_unlock_dashboards_plan(fb, dash_plan, confirm_plan=dash_plan["sha256"])
        self.assertTrue(dash_applied["verified"])

        # Sync primary user locationIds from +hubpro alias via preview + apply
        sync_plan = make_user_sync_locations_plan(
            fb,
            user_id="usr_primary_1234",
            from_user_id="usr_alias_1234",
        )
        self.assertEqual(
            sync_plan["proposed_payload"]["locationIds"],
            ["loc_alpha_1234", "loc_beta_5678"],
        )
        sync_applied = apply_user_sync_locations_plan(
            fb,
            sync_plan,
            confirm_user="usr_primary_1234",
            confirm_plan=sync_plan["sha256"],
        )
        self.assertTrue(sync_applied["verified"])

        # Re-run live agency audit: all 5 layers now pass with 0 issues
        audit_after = live_agency_audit(fb)
        self.assertTrue(audit_after["ok"])
        self.assertEqual(audit_after["summary"]["issue_count"], 0)

        # Verify pit-list, email-domains, and rebilling-status
        pits = list_private_integrations(fb, location_id="loc_alpha_1234")
        self.assertEqual(pits["count"], 1)
        self.assertEqual(pits["private_integrations"][0]["id"], "pit_01")

        domains = inspect_email_domains(fb, location_id="loc_alpha_1234")
        self.assertEqual(len(domains["dedicated_domains"]), 1)
        self.assertFalse(domains["block_add_smtp"])

        reb_status = inspect_rebilling_status(fb, location_id="loc_alpha_1234")
        self.assertTrue(reb_status["ok"])


class CrmAndMutationTests(unittest.TestCase):
    def test_contacts_pii_lean_default_vs_full(self) -> None:
        fake = FakeClient()
        lean = search_contacts(fake, full=False)
        self.assertEqual(lean["pii_mode"], "lean")
        self.assertNotIn("email", lean["contacts"][0])
        self.assertNotIn("phone", lean["contacts"][0])

        full = search_contacts(fake, full=True)
        self.assertEqual(full["pii_mode"], "full")
        self.assertEqual(full["contacts"][0]["email"], "jane@example.com")

    def test_custom_value_create_update_delete_lifecycle(self) -> None:
        fake = FakeClient()

        # 1. Create preview + apply
        create_plan = make_custom_value_plan(fake, name="Booking Link", value="https://example.com/book")
        self.assertEqual(create_plan["action"], "create")
        self.assertIsNone(create_plan["before"])

        with self.assertRaises(HighLevelError):
            apply_custom_value_plan(
                fake,
                create_plan,
                confirm_location="wrong_location_id",
                confirm_plan=create_plan["sha256"],
            )
        with self.assertRaises(HighLevelError):
            apply_custom_value_plan(
                fake,
                create_plan,
                confirm_location=fake.location_id,
                confirm_plan="0" * 64,
            )

        created = apply_custom_value_plan(
            fake,
            create_plan,
            confirm_location=fake.location_id,
            confirm_plan=create_plan["sha256"],
        )
        self.assertTrue(created["verified"])
        self.assertEqual(created["custom_value_id"], "cv_created_99")

        # 2. Update preview + apply
        update_plan = make_custom_value_plan(
            fake,
            name="Booking Link",
            value="https://example.com/book-v2",
        )
        self.assertEqual(update_plan["action"], "update")
        self.assertEqual(update_plan["custom_value_id"], "cv_created_99")
        updated = apply_custom_value_plan(
            fake,
            update_plan,
            confirm_location=fake.location_id,
            confirm_plan=update_plan["sha256"],
        )
        self.assertTrue(updated["verified"])
        self.assertEqual(updated["readback"]["value"], "https://example.com/book-v2")

        # 3. Delete preview + apply
        delete_plan = make_custom_value_plan(
            fake,
            name="Booking Link",
            custom_value_id="cv_created_99",
            delete=True,
        )
        self.assertEqual(delete_plan["action"], "delete")
        deleted = apply_custom_value_plan(
            fake,
            delete_plan,
            confirm_location=fake.location_id,
            confirm_plan=delete_plan["sha256"],
        )
        self.assertTrue(deleted["verified"])

    def test_v2_and_v3_crm_ai_objects_funnels_workflows(self) -> None:
        fake = FakeClient()

        tags = list_tags(fake)
        self.assertEqual(tags["count"], 1)
        self.assertEqual(tags["tags"][0]["name"], "vip")

        funnels = list_funnels(fake, include_redirects=True)
        self.assertEqual(funnels["count"], 1)
        self.assertEqual(len(funnels["redirects"]), 1)

        objs = list_objects(fake)
        self.assertEqual(objs["count"], 1)
        self.assertEqual(objs["objects"][0]["key"], "custom_objects.vehicles")

        recs = search_object_records(fake, object_key="custom_objects.vehicles")
        self.assertEqual(recs["count"], 1)

        assocs = list_associations(fake)
        self.assertEqual(assocs["count"], 1)

        v_agents = list_voice_ai_agents(fake)
        self.assertEqual(v_agents["count"], 1)
        self.assertEqual(v_agents["agents"][0]["name"], "Receptionist")

        v_calls = list_voice_ai_calls(fake)
        self.assertEqual(v_calls["count"], 1)

        c_agents = list_conversation_ai_agents(fake)
        self.assertEqual(c_agents["count"], 1)
        self.assertEqual(c_agents["agents"][0]["name"], "Support Bot")

        steps = list_workflow_step_types(fake)
        self.assertEqual(len(steps["step_types"]), 1)

        wf_def = inspect_workflow_definition(fake, workflow_id="wf_12345678")
        self.assertEqual(wf_def["workflow_id"], "wf_12345678")

        wf_logs = list_workflow_logs(fake, workflow_id="wf_12345678")
        self.assertEqual(len(wf_logs["logs"]), 1)

        wf_val = validate_workflow_definition(fake, definition={"steps": []})
        self.assertTrue(wf_val["validation"]["valid"])

        wf_plan = make_workflow_status_plan(fake, workflow_id="wf_12345678", status="published")
        self.assertEqual(wf_plan["proposed"]["status"], "published")
        wf_applied = apply_workflow_status_plan(
            fake,
            wf_plan,
            confirm_location=fake.location_id,
            confirm_plan=wf_plan["sha256"],
        )
        self.assertTrue(wf_applied["verified"])

        # Subaccount audit, calendar slots, tag CRUD, contact upsert/tag/note, opportunity update
        sub_aud = subaccount_audit(fake)
        self.assertTrue(sub_aud["ok"])
        self.assertEqual(sub_aud["summary"]["pipelines"], 1)

        slots = list_calendar_free_slots(fake, calendar_id="cal_12345678", start_date="2026-11-01", end_date="2026-11-02")
        self.assertIn("2026-11-01", slots["slots"])

        t_plan = make_tag_plan(fake, name="new-lead")
        self.assertEqual(t_plan["action"], "create")
        t_app = apply_tag_plan(fake, t_plan, confirm_location=fake.location_id, confirm_plan=t_plan["sha256"])
        self.assertTrue(t_app["verified"])
        td_plan = make_tag_plan(fake, name="new-lead", tag_id="tag_created_99", delete=True)
        td_app = apply_tag_plan(fake, td_plan, confirm_location=fake.location_id, confirm_plan=td_plan["sha256"])
        self.assertTrue(td_app["verified"])

        cu_plan = make_contact_upsert_plan(fake, email="jane@example.com", first_name="Jane", tags=["vip"])
        cu_app = apply_contact_upsert_plan(fake, cu_plan, confirm_location=fake.location_id, confirm_plan=cu_plan["sha256"])
        self.assertTrue(cu_app["verified"])

        ct_plan = make_contact_tag_plan(fake, contact_id="cnt_12345678", tags=["hot-lead"])
        ct_app = apply_contact_tag_plan(fake, ct_plan, confirm_location=fake.location_id, confirm_plan=ct_plan["sha256"])
        self.assertTrue(ct_app["verified"])
        self.assertIn("hot-lead", ct_app["tags"])

        cn_plan = make_contact_note_plan(fake, contact_id="cnt_12345678", body="Spoke on discovery call.")
        cn_app = apply_contact_note_plan(fake, cn_plan, confirm_location=fake.location_id, confirm_plan=cn_plan["sha256"])
        self.assertTrue(cn_app["verified"])

        ou_plan = make_opportunity_update_plan(fake, opportunity_id="opp_12345678", status="won", monetary_value=2500.0)
        ou_app = apply_opportunity_update_plan(fake, ou_plan, confirm_location=fake.location_id, confirm_plan=ou_plan["sha256"])
        self.assertTrue(ou_app["verified"])
        self.assertEqual(ou_app["readback"]["status"], "won")
        self.assertEqual(ou_app["readback"]["monetaryValue"], 2500.0)

    def test_cli_offline_doctor_and_confirmation_guards(self) -> None:
        args = parser().parse_args(["doctor"])
        res = execute(args)
        self.assertTrue(res["ok"])
        self.assertEqual(res["mode"], "offline")

        args_bad = parser().parse_args(["custom-value-upsert", "--name", "X", "--value", "Y", "--apply"])
        with self.assertRaises(HighLevelError):
            execute(args_bad, client_factory=FakeClient)

        args_bad_dash = parser().parse_args(["unlock-dashboards", "--all-locations", "--apply"])
        with self.assertRaises(HighLevelError):
            execute(args_bad_dash, backend_factory=FakeBackendClient)

        args_live = parser().parse_args(["live-audit"])
        res_live = execute(args_live, backend_factory=FakeBackendClient)
        self.assertFalse(res_live["ok"])

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["rebilling-audit", "--markup", "5"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["ui_multiplier"], 1.05)


if __name__ == "__main__":
    unittest.main()
