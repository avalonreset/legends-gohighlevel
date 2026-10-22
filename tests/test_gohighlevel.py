"""Offline unit test suite for legends-gohighlevel."""
from __future__ import annotations

import io
import json
import os
import unittest
from unittest.mock import patch
import urllib.error

from legends_gohighlevel.api import Client, HighLevelError, NoRedirect, valid_id
from legends_gohighlevel.cli import execute, main, parser
from legends_gohighlevel.crm import (
    apply_custom_value_plan,
    make_custom_value_plan,
    plan_digest,
    probe_live_lanes,
    search_contacts,
)
from legends_gohighlevel.governance import (
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
        self.calls: list[tuple[str, str, dict | None, dict | None]] = []

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
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
        return {}


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

    def test_cli_offline_doctor_and_confirmation_guards(self) -> None:
        args = parser().parse_args(["doctor"])
        res = execute(args)
        self.assertTrue(res["ok"])
        self.assertEqual(res["mode"], "offline")

        args_bad = parser().parse_args(["custom-value-upsert", "--name", "X", "--value", "Y", "--apply"])
        with self.assertRaises(HighLevelError):
            execute(args_bad, client_factory=FakeClient)

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["rebilling-audit", "--markup", "5"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["ui_multiplier"], 1.05)


if __name__ == "__main__":
    unittest.main()
