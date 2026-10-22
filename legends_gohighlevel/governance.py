"""Deterministic HighLevel agency and sub-account governance calculators and payload builders."""
from __future__ import annotations

from typing import Any

from .api import HighLevelError

SAAS_BILLING_V2_KEYS = (
    "workflow_premium_actions",
    "workflow_ai",
    "conversation_AI",
    "voiceAI",
    "contentAI",
    "reviewsAI",
    "agentStudio",
    "askai",
    "aiStudio",
    "EmailVerification",
    "domainPurchase",
)

MUTUALLY_EXCLUSIVE_V2_SCOPES = (
    ("workflows.readonly", "workflows.write"),
    ("campaigns.readonly", "campaigns.write"),
)

AGENCY_ONLY_V2_SCOPES = (
    "users/permission-template.write",
    "users/permission-template.readonly",
    "agency/launchpad.write",
)

CRITICAL_ACCOUNT_ADMIN_V2_SCOPES = (
    "contacts.readonly",
    "contacts.write",
    "contacts/bulkActions.write",
    "opportunities.readonly",
    "opportunities.write",
    "pipelines.readonly",
    "pipelines.write",
    "pipelines.create",
    "calendars.readonly",
    "calendars.write",
    "calendars/events.readonly",
    "calendars/events.write",
    "calendars/groups.readonly",
    "calendars/groups.write",
    "calendars/resources.readonly",
    "calendars/resources.write",
    "calendars/settings.write",
    "conversations.readonly",
    "conversations.write",
    "conversations/message.readonly",
    "conversations/message.write",
    "conversations/reports.readonly",
    "campaigns.write",
    "workflows.write",
    "forms.readonly",
    "forms.write",
    "surveys.readonly",
    "surveys.write",
    "funnels.readonly",
    "funnels.write",
    "websites.readonly",
    "websites.write",
    "funnelaiv2.writev2",
    "medias.readonly",
    "medias.write",
    "settings.write",
    "custom-menu-link.write",
    "private-integration-location.readonly",
    "native-integrations.readonly",
    "users/team-management.write",
    "users/team-management.readonly",
    "internaltools.billing-common.write",
    "locations.billing.manage",
    "locations.details.manage",
    "reputation/review.write",
    "reputation/listing.write",
    "reputation/gbp.write",
    "reputation/reviewsAIAgents.write",
    "marketing.write",
    "marketing/affiliate.write",
    "affiliate-manager.adminonly",
    "socialplanner/post.write",
    "socialplanner/account.write",
    "socialplanner/category.write",
    "socialplanner/csv.write",
    "socialplanner/hashtag.write",
    "socialplanner/Setting.write",
    "socialplanner/stat.readonly",
    "blogs.write",
    "payments.write",
    "payments/orders.readonly",
    "payments/orders.export",
    "payments/orders.import",
    "payments/orders.collectPayment",
    "payments/subscriptions.readonly",
    "payments/subscriptions.write",
    "payments/subscriptions.update",
    "payments/subscriptions.export",
    "payments/subscriptions.pauseResumeCancel",
    "payments/subscriptions.sharePaymentMethod",
    "payments/transactions.readonly",
    "payments/transactions.export",
    "payments/transactions.import",
    "payments/transactions.refund",
    "payments/transactions.viewReceipts",
    "payments/settings.readonly",
    "payments/settings.configureReceipt",
    "payments/settings.configureSubscription",
    "payments/taxesSettings.readonly",
    "payments/taxesSettings.updateInclusiveExclusive",
    "payments/taxesSettings.manageRates",
    "payments/taxesSettings.configureAutomatic",
    "payments/records.write",
    "invoices.write",
    "products.readonly",
    "products.write",
    "products.delete",
    "products.duplicate",
    "products.bulkActions",
    "qrcodes.write",
    "qrcodes/business-card.readonly",
    "qrcodes/business-card.write",
    "qrcodes/profile-card.readonly",
    "qrcodes/profile-card.write",
    "reporting/adwords.readonly",
    "reporting/facebook.readonly",
    "reporting/attributions.readonly",
    "reporting/phone.readonly",
    "reporting/agent.readonly",
    "reporting/reports.write",
    "reporting/stats.export",
    "prospecting.write",
    "prospecting/auditReport.write",
    "voice-ai-agents.write",
    "voice-ai-agent-goals.readonly",
    "voice-ai-agent-goals.write",
    "voice-ai-dashboard.readonly",
    "text-ai-agents.write",
    "text-ai-agent-goals.readonly",
    "text-ai-agent-goals.write",
    "text-ai-agent-training.write",
    "text-ai-agents-dashboard.readonly",
    "managed-agents.write",
    "knowledge-bases.write",
    "askai.write",
    "ai-studio.readonlyv2",
    "ai-studio.writev2",
    "ai-studio.manageCode",
    "creator-studio.readonly",
    "creator-studio.write",
    "launchpad/location.write",
    "audit-logs.readonly",
    "audit-logs.export",
    "lc.whatsapp.templates.write",
    "lc.whatsapp.templates.delete",
    "lc.whatsapp.flows.write",
    "lc.whatsapp.flows.delete",
    "lc.whatsapp.business-profile.write",
    "lc.whatsapp.phone-numbers.write",
    "lc.whatsapp.integration.disconnect",
)

UNNERFED_V1_PERMISSIONS: dict[str, bool] = {
    "adPublishingEnabled": True,
    "adPublishingReadOnly": False,
    "affiliateManagerEnabled": True,
    "agentReportingEnabled": True,
    "appointmentsEnabled": True,
    "assignedDataOnly": False,
    "attributionsReportingEnabled": True,
    "bloggingEnabled": True,
    "botService": True,
    "bulkRequestsEnabled": True,
    "campaignsEnabled": True,
    "campaignsReadOnly": False,
    "cancelSubscriptionEnabled": True,
    "certificatesEnabled": True,
    "communitiesEnabled": True,
    "contactsEnabled": True,
    "contentAiEnabled": True,
    "conversationsEnabled": True,
    "coursesEnabled": True,
    "customMenuLinkReadOnly": False,
    "dashboardStatsEnabled": True,
    "exportPaymentsEnabled": True,
    "facebookAdsReportingEnabled": True,
    "funnelsEnabled": True,
    "funnelsReadOnly": False,
    "goCollaborationEnabled": True,
    "invoiceEnabled": True,
    "leadValueEnabled": True,
    "marketingEnabled": True,
    "mediaStorageEnabled": True,
    "membershipEnabled": True,
    "NativeIntegrationsEnabled": True,
    "onlineListingsEnabled": True,
    "opportunitiesEnabled": True,
    "paymentsEnabled": True,
    "phoneCallEnabled": True,
    "PrivateIntegrationLocationEnabled": True,
    "prospectingEnabled": True,
    "qrCodesEnabled": True,
    "recordPaymentEnabled": True,
    "refundsEnabled": True,
    "reviewsEnabled": True,
    "settingsEnabled": True,
    "socialPlanner": True,
    "SubscriptionEnabled": True,
    "tagsEnabled": True,
    "triggersEnabled": True,
    "websitesEnabled": True,
    "websitesReadOnly": False,
    "workflowsEnabled": True,
    "workflowsReadOnly": False,
}


def markup_to_multiplier(markup: int) -> float:
    """Convert HighLevel DB integer markup (e.g. 5) to UI multiplier (e.g. 1.05)."""
    if markup < 0 or markup > 1000:
        raise HighLevelError("DB markup must be an integer between 0 and 1000.")
    return round((int(markup) + 100) / 100.0, 4)


def multiplier_to_markup(multiplier: float) -> int:
    """Convert UI multiplier (e.g. 1.05) to HighLevel DB integer markup (e.g. 5)."""
    if multiplier < 1.0 or multiplier > 11.0:
        raise HighLevelError("Multiplier must be between 1.00 and 11.00.")
    return int(round(multiplier * 100.0 - 100.0))


def rebilling_audit(
    *,
    wallet_topup_usd: float = 10.0,
    markup: int = 5,
    stripe_pct: float = 0.029,
    stripe_fixed_usd: float = 0.30,
    location_id: str | None = None,
) -> dict[str, Any]:
    if wallet_topup_usd <= 0:
        raise HighLevelError("wallet_topup_usd must be positive.")
    multiplier = markup_to_multiplier(markup)
    stripe_fee_usd = round(wallet_topup_usd * stripe_pct + stripe_fixed_usd, 4)
    agency_received_after_stripe_usd = round(wallet_topup_usd - stripe_fee_usd, 4)
    wholesale_usage_unlocked_usd = round(wallet_topup_usd / multiplier, 4)
    markup_buffer_usd = round(wallet_topup_usd - wholesale_usage_unlocked_usd, 4)
    agency_net_usd = round(agency_received_after_stripe_usd - wholesale_usage_unlocked_usd, 4)
    mailgun_base_price = 0.000675
    mailgun_rebill_price = round(mailgun_base_price * multiplier, 8)

    target_id = location_id or "<LOCATION_ID>"
    keys_csv = ",".join(SAAS_BILLING_V2_KEYS)
    stores = {
        "saas_billing_v2": {
            "method": "PUT",
            "path": f"/saas-billing-v2/billing-config/group/{target_id}/{keys_csv}",
            "payload": {
                "scope": "LOCATION",
                "configs": {
                    key: {"enabled": True, "markup": int(markup)}
                    for key in SAAS_BILLING_V2_KEYS
                },
            },
        },
        "twilio_rebilling": {
            "method": "POST",
            "path": f"/saas_service/saas-config/{target_id}/update-twilio-rebilling",
            "payload": {"isEnabled": True, "markup": int(markup)},
        },
        "mailgun_rebilling": {
            "method": "POST",
            "path": f"/saas_service/saas-config/{target_id}/update-mailgun-rebilling",
            "payload": {
                "isEnabled": True,
                "markup": int(markup),
                "price": mailgun_rebill_price,
            },
        },
        "location_metadata": {
            "method": "PUT",
            "path": f"/saas-api/location-metadata/{target_id}",
            "payload": {
                "twilioRebilling": {"isEnabled": True, "markup": int(markup)},
                "mailgunRebilling": {"isEnabled": True, "markup": int(markup)},
            },
        },
    }

    return {
        "formula": "ui_multiplier = (parseInt(db_markup) + 100) / 100",
        "db_markup": int(markup),
        "ui_multiplier": multiplier,
        "wallet_topup_usd": round(wallet_topup_usd, 2),
        "stripe_processing_fee_usd": stripe_fee_usd,
        "agency_received_after_stripe_usd": agency_received_after_stripe_usd,
        "wholesale_usage_unlocked_usd": wholesale_usage_unlocked_usd,
        "markup_buffer_usd": markup_buffer_usd,
        "agency_net_after_stripe_and_usage_usd": agency_net_usd,
        "agency_loss_risk": agency_net_usd < -0.15,
        "recommendation": (
            "Safe 1.05x (db_markup=5) default offsets Stripe processing fees on $10 wallet reloads."
            if markup == 5
            else (
                "WARNING: db_markup=0 (1.00x) leaves the agency absorbing the full Stripe processing fee on every wallet reload."
                if markup == 0
                else f"Custom multiplier {multiplier}x (db_markup={markup})."
            )
        ),
        "four_store_sync_blueprint": stores,
    }


def scope_audit(
    *,
    role: str = "admin",
    account_type: str = "account",
    current_scopes: list[str] | None = None,
    creator_scopes: list[str] | None = None,
) -> dict[str, Any]:
    if account_type not in {"account", "agency"}:
        raise HighLevelError("account_type must be 'account' or 'agency'.")
    if role not in {"admin", "user"}:
        raise HighLevelError("role must be 'admin' or 'user'.")

    excluded_readonly = {pair[0] for pair in MUTUALLY_EXCLUSIVE_V2_SCOPES}
    excluded_for_account = set(AGENCY_ONLY_V2_SCOPES) if account_type == "account" else set()
    recommended_scopes = [
        s for s in CRITICAL_ACCOUNT_ADMIN_V2_SCOPES
        if s not in excluded_readonly and s not in excluded_for_account
    ]

    missing_on_user: list[str] = []
    mutual_exclusion_conflicts: list[str] = []
    if current_scopes is not None:
        cur_set = set(current_scopes)
        missing_on_user = [s for s in recommended_scopes if s not in cur_set]
        for ro_scope, rw_scope in MUTUALLY_EXCLUSIVE_V2_SCOPES:
            if ro_scope in cur_set and rw_scope in cur_set:
                mutual_exclusion_conflicts.append(f"{ro_scope} + {rw_scope}")

    stripped_by_creator: list[str] = []
    if creator_scopes is not None:
        expanded_creator = set(creator_scopes)
        for s in list(creator_scopes):
            if s.endswith(".write"):
                expanded_creator.add(s[:-6] + ".readonly")
        stripped_by_creator = [s for s in recommended_scopes if s not in expanded_creator]

    return {
        "account_type": account_type,
        "role": role,
        "required_update_source": "agency_team",
        "mutually_exclusive_pairs": [list(p) for p in MUTUALLY_EXCLUSIVE_V2_SCOPES],
        "recommended_v2_scope_count": len(recommended_scopes),
        "missing_v2_scopes_on_user": missing_on_user,
        "mutual_exclusion_conflicts": mutual_exclusion_conflicts,
        "worker_inheritance_stripped_scopes": stripped_by_creator,
        "worker_inheritance_warning": (
            "Creator lacks V2 scopes; HighLevel usersApp w(l) will silently disable those scopes when creating a new user in the browser."
            if stripped_by_creator
            else "Creator holds all required V2 scopes; zero inheritance stripping."
            if creator_scopes is not None
            else "Pass --creator-scopes-json to check Agency Admin worker scope-inheritance stripping."
        ),
        "unnerfed_v1_permissions": UNNERFED_V1_PERMISSIONS,
        "recommended_v2_scopes": recommended_scopes,
    }


def smtp_audit(
    *,
    company_id: str | None = None,
    location_id: str | None = None,
    company_block_add_smtp: bool | None = None,
    location_block_add_smtp: bool | None = None,
) -> dict[str, Any]:
    cid = company_id or "<COMPANY_ID>"
    lid = location_id or "<LOCATION_ID>"
    button_enabled = (company_block_add_smtp is False) and (location_block_add_smtp is False)
    return {
        "add_service_button_unlocked": button_enabled if (company_block_add_smtp is not None and location_block_add_smtp is not None) else "unverified",
        "explanation": (
            "HighLevel enforces two independent locks on the sub-account 'Add Service' (Custom SMTP) button: "
            "an agency-wide default (emailIsvSettings.blockAddSmtp) AND a per-location flag stamped at sub-account creation (blockAddSmtp). "
            "Both must be false for existing sub-accounts to add custom SMTP providers (Brevo, SendGrid, Mailgun, Amazon SES)."
        ),
        "agency_unlock_request": {
            "method": "PUT",
            "path": f"/email-isv/Setting/feature/company/{cid}",
            "payload": {"emailIsvSettings": {"blockAddSmtp": False}},
        },
        "location_unlock_request": {
            "method": "PUT",
            "path": f"/email-isv/Setting/feature/location/{lid}",
            "payload": {"blockAddSmtp": False},
        },
        "readback_verification": {
            "method": "GET",
            "path": f"/email-isv/onload?locationId={lid}",
            "expected_fields": {"blockAddSmtp": False},
        },
    }
