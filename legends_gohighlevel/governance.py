"""Deterministic HighLevel agency and sub-account governance calculators, A2P 10DLC preflight auditors, and payload builders."""
from __future__ import annotations

import html
from html.parser import HTMLParser
import http.client
import ipaddress
import re
import socket
import ssl
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

from . import __version__
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
    "whatsApp",
    "emailWarmup",
    "creatorStudio",
)

UNNERFED_LOCATION_PERMISSIONS: dict[str, bool] = {
    "adManagerEnabled": True,
    "adwordsReportingEnabled": True,
    "affiliateManagerEnabled": True,
    "agentReportingEnabled": True,
    "appointmentsEnabled": True,
    "attributionsReportingEnabled": True,
    "bloggingEnabled": True,
    "botServiceEnabled": True,
    "bulkRequestsEnabled": True,
    "campaignsEnabled": True,
    "contactsEnabled": True,
    "conversationsEnabled": True,
    "dashboardStatsEnabled": True,
    "emailBuilderEnabled": True,
    "facebookAdsReportingEnabled": True,
    "facebookMessengerEnabled": True,
    "formsEnabled": True,
    "funnelsEnabled": True,
    "gmbCallTrackingEnabled": True,
    "gmbMessagingEnabled": True,
    "htmlBuilderEnabled": True,
    "launchpadEnabled": True,
    "marketingEnabled": True,
    "membershipEnabled": True,
    "opportunitiesEnabled": True,
    "phoneCallEnabled": True,
    "proposalsEnabled": True,
    "qrCodesEnabled": True,
    "quizzesEnabled": True,
    "reviewsEnabled": True,
    "settingsEnabled": True,
    "smsEmailTemplatesEnabled": True,
    "surveysEnabled": True,
    "tagsEnabled": True,
    "textToPayEnabled": True,
    "triggerLinksEnabled": True,
    "triggersEnabled": True,
    "webChatEnabled": True,
    "websitesEnabled": True,
    "workflowsEnabled": True,
}

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
    "campaigns.write",
    "calendars.readonly",
    "calendars.write",
    "calendars/events.write",
    "calendars/groups.write",
    "calendars/resources.write",
    "calendars/settings.write",
    "contacts.write",
    "contacts/bulkActions.write",
    "workflows.write",
    "triggers.write",
    "funnels.write",
    "forms.write",
    "surveys.write",
    "websites.write",
    "funnelaiv2.writev2",
    "medias.write",
    "opportunities.write",
    "opportunities/leadValue.readonly",
    "opportunities/bulkActions.write",
    "pipelines.create",
    "reporting/phone.readonly",
    "reporting/adwords.readonly",
    "reporting/facebookAds.readonly",
    "reporting/attributions.readonly",
    "prospecting/auditReport.write",
    "reporting/agent.readonly",
    "reporting/reports.write",
    "reporting/stats.export",
    "payments.write",
    "payments/records.write",
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
    "payments/taxesSettings.readonly",
    "payments/taxesSettings.updateInclusiveExclusive",
    "payments/taxesSettings.manageRates",
    "payments/taxesSettings.configureAutomatic",
    "products.readonly",
    "products.write",
    "products.delete",
    "products.duplicate",
    "products.bulkActions",
    "payments/settings.readonly",
    "payments/settings.configureReceipt",
    "payments/settings.configureSubscription",
    "payments/gift-cards.orders.readonly",
    "payments/gift-cards.orders-detail.readonly",
    "payments/gift-cards.orders-code.readonly",
    "payments/gift-cards.products.readonly",
    "payments/gift-cards.products.write",
    "payments/gift-cards.products.sell",
    "payments/gift-cards.products.send",
    "payments/gift-cards.products.action",
    "invoices.write",
    "reputation/review.write",
    "reputation/listing.write",
    "reputation/reviewsAIAgents.write",
    "reputation/gbp.write",
    "conversations.write",
    "contentAI.write",
    "ai-studio.readonlyv2",
    "ai-studio.writev2",
    "ai-studio.manageCode",
    "creator-studio.readonly",
    "creator-studio.write",
    "dashboard/stats.readonly",
    "locations/tags.write",
    "marketing.write",
    "eliza.write",
    "settings.write",
    "socialplanner/post.write",
    "marketing/affiliate.write",
    "affiliate-manager.adminonly",
    "loyalty.write",
    "loyalty/scanner.write",
    "blogs.write",
    "membership.write",
    "communities.write",
    "gokollab.write",
    "certificates.write",
    "adPublishing.write",
    "prospecting.write",
    "private-integration-location.readonly",
    "native-integrations.readonly",
    "wordpress.write",
    "qrcodes.write",
    "qrcodes/business-card.readonly",
    "qrcodes/business-card.write",
    "qrcodes/profile-card.readonly",
    "qrcodes/profile-card.write",
    "users/team-management.write",
    "users/team-management.readonly",
    "internaltools.billing-common.write",
    "managed-agents.write",
    "voice-ai-agents.write",
    "voice-ai-agent-goals.readonly",
    "voice-ai-agent-goals.write",
    "voice-ai-dashboard.readonly",
    "launchpad/location.write",
    "text-ai-agents.write",
    "text-ai-agent-goals.readonly",
    "text-ai-agent-goals.write",
    "text-ai-agent-training.write",
    "text-ai-agents-dashboard.readonly",
    "askai.write",
    "knowledge-bases.write",
    "locations.billing.manage",
    "locations.details.manage",
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
    "adwordsReportingEnabled": True,
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
    "customMenuLinkWrite": True,
    "dashboardStatsEnabled": True,
    "exportPaymentsEnabled": True,
    "facebookAdsReportingEnabled": True,
    "funnelsEnabled": True,
    "funnelsReadOnly": False,
    "goCollaborationEnabled": True,
    "gokollabEnabled": True,
    "invoiceEnabled": True,
    "leadValueEnabled": True,
    "marketingEnabled": True,
    "mediaStorageEnabled": True,
    "membershipEnabled": True,
    "nativeIntegrationsEnabled": True,
    "onlineListingsEnabled": True,
    "opportunitiesBulkActionsEnabled": True,
    "opportunitiesEnabled": True,
    "paymentsEnabled": True,
    "phoneCallEnabled": True,
    "privateIntegrationLocationEnabled": True,
    "prospectingEnabled": True,
    "qrCodesEnabled": True,
    "recordPaymentEnabled": True,
    "refundsEnabled": True,
    "reportingEnabled": True,
    "reviewsEnabled": True,
    "settingsEnabled": True,
    "socialPlanner": True,
    "subscriptionEnabled": True,
    "tagsEnabled": True,
    "triggersEnabled": True,
    "websitesEnabled": True,
    "websitesReadOnly": False,
    "wordpressEnabled": True,
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
                "entityType": "LOCATION",
                "enabled": True,
                "optIn": True,
                "markups": {
                    key: int(markup)
                    for key in SAAS_BILLING_V2_KEYS
                },
            },
        },
        "twilio_rebilling": {
            "method": "POST",
            "path": f"/saas_service/saas-config/{target_id}/update-twilio-rebilling",
            "payload": {"enabled": True, "markup": int(markup)},
        },
        "mailgun_rebilling": {
            "method": "PUT",
            "path": f"/locations/{target_id}",
            "payload": {
                "companyId": "<COMPANY_ID>",
                "settings": {
                    "saasSettings": {
                        "twilioRebilling": {"enabled": True, "markup": int(markup)},
                        "mailgunRebilling": {
                            "enabled": True,
                            "markup": int(markup),
                            "price": mailgun_rebill_price,
                        },
                    },
                },
            },
        },
        "location_metadata": {
            "method": "PUT",
            "path": f"/saas-api/location-metadata/{target_id}",
            "payload": {
                "attachedRebillingConfig": {
                    "Phone": {"enabled": True, "markup": int(markup)},
                    "Email": {"enabled": True, "markup": int(markup), "price": mailgun_rebill_price},
                },
                "twilioRebilling": {"enabled": True, "markup": int(markup)},
                "mailgunRebilling": {
                    "enabled": True,
                    "markup": int(markup),
                    "price": mailgun_rebill_price,
                },
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
        "default_dashboard_rbac": DEFAULT_DASHBOARD_PERMISSION_ACCESS,
    }


DEFAULT_DASHBOARD_PERMISSION_ACCESS: tuple[dict[str, str], ...] = (
    {"role": "agency_user", "permission": "full"},
    {"role": "account_admin", "permission": "full"},
    {"role": "account_user", "permission": "full"},
)


def dashboard_permission_audit(
    *,
    location_id: str | None = None,
    dashboard_id: str | None = None,
    current_permissions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    lid = location_id or "<LOCATION_ID>"
    did = dashboard_id or "<DEFAULT_DASHBOARD_ID>"
    perm_map = {
        str(item.get("role", "")): str(item.get("permission", ""))
        for item in (current_permissions or [])
        if isinstance(item, dict)
    }
    admin_full = perm_map.get("account_admin") == "full"
    user_full = perm_map.get("account_user") == "full"
    return {
        "location_id": lid,
        "dashboard_id": did,
        "account_admin_full_verified": admin_full if current_permissions is not None else "unverified",
        "account_user_full_verified": user_full if current_permissions is not None else "unverified",
        "explanation": (
            "HighLevel seeds newly provisioned sub-account default dashboards with only "
            "[{'role': 'agency_user', 'permission': 'full'}, {'role': 'account_user', 'permission': 'read'}], "
            "omitting 'account_admin'. Without 'account_admin: full', sub-account admins receive "
            "errorType='permission_error' when attempting to edit or clone the default dashboard."
        ),
        "unlock_request": {
            "method": "POST",
            "path": f"/reporting/dashboards/{did}/permissions?locationId={lid}",
            "payload": {
                "locationId": lid,
                "isPrivate": False,
                "permissionAccess": list(DEFAULT_DASHBOARD_PERMISSION_ACCESS),
            },
        },
        "readback_verification": {
            "method": "GET",
            "path": f"/reporting/dashboards/{did}/permissions?locationId={lid}",
            "expected_permission": list(DEFAULT_DASHBOARD_PERMISSION_ACCESS),
        },
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


MAX_A2P_DOM_BYTES = 2 * 1024 * 1024
_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
_PRIVATE_HOST_PREFIXES = ("127.", "10.", "192.168.", "169.254.", "0.", "localhost")
_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")


def _validate_public_ip(ip_text: str) -> str:
    try:
        addr = ipaddress.ip_address(ip_text)
    except ValueError as exc:
        raise HighLevelError(f"Invalid IP address resolved for website probe: {ip_text}") from exc
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if (
        addr.is_private
        or not addr.is_global
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or (isinstance(addr, ipaddress.IPv4Address) and addr in _CGNAT_NET)
    ):
        raise HighLevelError(f"Refusing to probe non-public IP address ({ip_text}).")
    return str(addr)


def _resolve_and_validate_public_host(host: str, port: int = 443) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HighLevelError(f"DNS resolution failed for {host}: {exc}") from exc
    if not infos:
        raise HighLevelError(f"DNS resolution returned no addresses for {host}.")
    ips: list[str] = []
    for info in infos:
        raw_ip = str(info[4][0]).split("%", 1)[0]
        clean_ip = _validate_public_ip(raw_ip)
        if clean_ip not in ips:
            ips.append(clean_ip)
    return ips


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *, connect_ip: str, sni_hostname: str, **kwargs: Any) -> None:
        super().__init__(host, **kwargs)
        self._connect_ip = connect_ip
        self._sni_hostname = sni_hostname

    def connect(self) -> None:
        raw_sock = socket.create_connection((self._connect_ip, self.port), self.timeout, self.source_address)
        if self._tunnel_host:
            self.sock = raw_sock
            self._tunnel()
        server_hostname = self._sni_hostname if ssl.HAS_SNI else None
        self.sock = self._context.wrap_socket(raw_sock, server_hostname=server_hostname)


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, *, connect_ip: str, sni_hostname: str, context: ssl.SSLContext | None = None) -> None:
        super().__init__(context=context)
        self._connect_ip = connect_ip
        self._sni_hostname = sni_hostname

    def https_open(self, req: urllib.request.Request):
        return self.do_open(
            lambda host, **kwargs: _PinnedHTTPSConnection(
                host,
                connect_ip=self._connect_ip,
                sni_hostname=self._sni_hostname,
                **kwargs,
            ),
            req,
            context=self._context,
        )


class _NoFollowRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Capture HTTP 3xx responses without automatically following cross-domain redirect pipes."""

    def http_error_301(self, req, fp, code, msg, headers):
        return fp

    def http_error_302(self, req, fp, code, msg, headers):
        return fp

    def http_error_303(self, req, fp, code, msg, headers):
        return fp

    def http_error_307(self, req, fp, code, msg, headers):
        return fp

    def http_error_308(self, req, fp, code, msg, headers):
        return fp


class _A2PDomParser(HTMLParser):
    """Lightweight HTML parser extracting forms, checkboxes, labels, links, and visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict[str, Any]] = []
        self.checkboxes: list[dict[str, Any]] = []
        self.links: list[dict[str, str]] = []
        self._text_chunks: list[str] = []
        self._in_ignored_tag = 0
        self._in_label = False
        self._current_label_for: str | None = None
        self._current_label_chunks: list[str] = []
        self._current_label_checkbox_idx: int | None = None
        self._current_a_href: str | None = None
        self._current_a_chunks: list[str] = []
        self._labels_by_for: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        attr_map = {k.lower(): (v if v is not None else "") for k, v in attrs if k}
        if t in {"script", "style", "noscript"}:
            self._in_ignored_tag += 1
            return
        if t == "form":
            self.forms.append(
                {
                    "id": attr_map.get("id", ""),
                    "action": attr_map.get("action", ""),
                    "method": attr_map.get("method", ""),
                }
            )
        elif t == "label":
            self._in_label = True
            self._current_label_for = attr_map.get("for") or None
            self._current_label_chunks = []
            self._current_label_checkbox_idx = None
        elif t == "input":
            itype = (attr_map.get("type") or "text").strip().lower()
            if itype == "checkbox":
                raw_keys = {k.lower() for k, _ in attrs if k}
                cb = {
                    "id": attr_map.get("id", ""),
                    "name": attr_map.get("name", ""),
                    "value": attr_map.get("value", ""),
                    "checked": "checked" in raw_keys,
                    "required": "required" in raw_keys,
                    "label_text": "",
                }
                self.checkboxes.append(cb)
                if self._in_label:
                    self._current_label_checkbox_idx = len(self.checkboxes) - 1
        elif t == "a":
            self._current_a_href = attr_map.get("href", "")
            self._current_a_chunks = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript"} and self._in_ignored_tag > 0:
            self._in_ignored_tag -= 1
            return
        if t == "label" and self._in_label:
            label_text = re.sub(r"\s+", " ", " ".join(self._current_label_chunks)).strip()
            if self._current_label_checkbox_idx is not None and 0 <= self._current_label_checkbox_idx < len(self.checkboxes):
                self.checkboxes[self._current_label_checkbox_idx]["label_text"] = label_text
            if self._current_label_for and label_text:
                self._labels_by_for[self._current_label_for] = label_text
            self._in_label = False
            self._current_label_for = None
            self._current_label_chunks = []
            self._current_label_checkbox_idx = None
        elif t == "a" and self._current_a_href is not None:
            anchor_text = re.sub(r"\s+", " ", " ".join(self._current_a_chunks)).strip()
            self.links.append({"href": self._current_a_href, "text": anchor_text})
            self._current_a_href = None
            self._current_a_chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_ignored_tag > 0:
            return
        cleaned = data.strip()
        if not cleaned:
            return
        self._text_chunks.append(cleaned)
        if self._in_label:
            self._current_label_chunks.append(cleaned)
        if self._current_a_href is not None:
            self._current_a_chunks.append(cleaned)

    def finalize(self) -> dict[str, Any]:
        for cb in self.checkboxes:
            if not cb["label_text"] and cb["id"] and cb["id"] in self._labels_by_for:
                cb["label_text"] = self._labels_by_for[cb["id"]]
        full_text = re.sub(r"\s+", " ", " ".join(self._text_chunks)).strip()
        return {
            "forms": self.forms,
            "checkboxes": self.checkboxes,
            "links": self.links,
            "text": full_text,
        }


def _normalize_domain(url_or_domain: str | None) -> str:
    raw = (url_or_domain or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urllib.parse.urlparse(raw)
    host = (parsed.hostname or "").strip().lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _normalize_root_url(website: str) -> str:
    raw = (website or "").strip()
    if not raw:
        raise HighLevelError("Provide a valid --website URL (e.g. https://example.com).")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise HighLevelError("Provide a valid https:// --website URL (cleartext http:// is refused).")
    host = parsed.hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
        raise HighLevelError("Website hostname must be a public DNS domain name, not an IP literal.")
    except ValueError:
        pass
    if (
        any(host.startswith(p) or host == p for p in _PRIVATE_HOST_PREFIXES)
        or host.endswith((".local", ".internal", ".localhost"))
        or not _HOST_RE.match(host)
    ):
        raise HighLevelError("Website hostname must be a public domain name.")
    return f"https://{host}"


def _email_domain(email: str | None) -> str:
    raw = (email or "").strip().lower()
    if "@" not in raw:
        return ""
    domain = raw.rsplit("@", 1)[-1].strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def inspect_a2p_phone(phone: str | None) -> dict[str, Any]:
    """Validate whether a business phone number is E.164/NANP compliant and not a 555 placeholder."""
    raw = (phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        nanp = digits[1:]
    elif len(digits) == 10:
        nanp = digits
    else:
        nanp = ""

    if not nanp:
        return {
            "raw": raw,
            "normalized_e164": None,
            "area_code": None,
            "exchange": None,
            "subscriber": None,
            "is_555_placeholder": False,
            "ok": False,
            "reason": "Missing or non-10-digit US NANP phone number.",
        }

    area_code = nanp[:3]
    exchange = nanp[3:6]
    subscriber = nanp[6:]
    is_555 = exchange == "555"
    is_zero_placeholder = subscriber == "0000" or area_code == "000"
    ok = not is_555 and not is_zero_placeholder and area_code[0] not in {"0", "1"} and exchange[0] not in {"0", "1"}
    reason = (
        "Valid NANP business phone number."
        if ok
        else (
            f"Phone number {raw} uses the 555 fictional/placeholder exchange ({area_code}-555-{subscriber}); TCR/Twilio rejects 555 placeholders."
            if is_555
            else f"Phone number {raw} is not a valid dialable US NANP number."
        )
    )
    return {
        "raw": raw,
        "normalized_e164": f"+1{nanp}",
        "area_code": area_code,
        "exchange": exchange,
        "subscriber": subscriber,
        "is_555_placeholder": is_555,
        "ok": ok,
        "reason": reason,
    }


def _probe_public_url(url: str, timeout: int = 12) -> dict[str, Any]:
    """Perform an unauthenticated single-hop HTTPS GET with DNS-rebinding IP pinning to inspect status code, redirect target, and HTML body."""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme.lower() != "https"
        or not host
        or any(host.startswith(p) or host == p for p in _PRIVATE_HOST_PREFIXES)
        or host.endswith((".local", ".internal", ".localhost"))
        or not _HOST_RE.match(host)
    ):
        raise HighLevelError(f"Refusing to probe non-public or non-HTTPS URL: {url}")

    port = parsed.port or 443
    resolved_ips = _resolve_and_validate_public_host(host, port)
    ssl_ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _PinnedHTTPSHandler(connect_ip=resolved_ips[0], sni_hostname=host, context=ssl_ctx),
        _NoFollowRedirectHandler(),
    )
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": f"legends-gohighlevel-a2p-auditor/{__version__}",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            headers = resp.headers
            loc = headers.get("Location") if headers else None
            raw_bytes = resp.read(MAX_A2P_DOM_BYTES)
            body = raw_bytes.decode("utf-8", errors="replace") if status == 200 else ""
            return {
                "url": url,
                "status": status,
                "is_redirect": status in {301, 302, 303, 307, 308},
                "redirect_location": loc,
                "html": body,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        loc = exc.headers.get("Location") if getattr(exc, "headers", None) else None
        return {
            "url": url,
            "status": int(exc.code),
            "is_redirect": int(exc.code) in {301, 302, 303, 307, 308},
            "redirect_location": loc,
            "html": "",
            "error": f"HTTP {exc.code}",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "status": None,
            "is_redirect": False,
            "redirect_location": None,
            "html": "",
            "error": str(exc),
        }


def _parse_html_doc(raw_html: str) -> dict[str, Any]:
    parser = _A2PDomParser()
    parser.feed(html.unescape(raw_html or ""))
    return parser.finalize()


def _audit_a2p_dom(
    *,
    root_probe: dict[str, Any],
    privacy_probe: dict[str, Any],
    terms_probe: dict[str, Any],
    brand_name: str,
    website_root: str,
    legal_name: str | None = None,
) -> dict[str, Any]:
    root_doc = _parse_html_doc(root_probe.get("html") or "")
    privacy_doc = _parse_html_doc(privacy_probe.get("html") or "")
    terms_doc = _parse_html_doc(terms_probe.get("html") or "")

    # Identify SMS / TCPA consent checkbox vs channel preference checkboxes
    checkboxes = root_doc["checkboxes"]
    consent_candidates = [
        cb
        for cb in checkboxes
        if any(
            kw in f"{cb.get('id', '')} {cb.get('name', '')} {cb.get('label_text', '')}".lower()
            for kw in ("tcpa", "consent", "optin", "opt-in", "agree to receive", "text messages", "sms")
        )
        and cb.get("name", "") != "preferredChannels"
    ]
    primary_cb = consent_candidates[0] if consent_candidates else (checkboxes[-1] if checkboxes else None)
    cb_label = (primary_cb.get("label_text") or "") if primary_cb else ""
    disclosure_haystack = cb_label if cb_label else root_doc["text"]
    disclosure_low = disclosure_haystack.lower()

    cb_found = primary_cb is not None
    is_pre_checked = bool(primary_cb.get("checked")) if primary_cb else False
    is_required = bool(primary_cb.get("required")) if primary_cb else False
    bundles_channels = bool(
        re.search(r"calls\s*,?\s*text\s+messages\s*,?\s*(?:and\s+)?emails", disclosure_low)
    )
    unbundled_ok = cb_found and (not is_pre_checked) and (not is_required) and (not bundles_channels)

    brand_clean = (brand_name or "").strip()
    brand_norm = re.sub(r"\s+", " ", brand_clean.lower().replace("&", "and"))
    disc_norm = re.sub(r"\s+", " ", disclosure_low.replace("&", "and"))
    page_norm = re.sub(r"\s+", " ", root_doc["text"].lower().replace("&", "and"))
    program_name_in_disclosure = bool(brand_norm and brand_norm in disc_norm)
    program_name_in_page = bool(brand_norm and brand_norm in page_norm)

    msg_rates_ok = bool(
        re.search(r"(?:msg|message)\s*(?:&|and)\s*data\s+rates\s+may\s+apply", disclosure_low)
    )
    msg_freq_ok = bool(
        re.search(
            r"(?:(?:msg|message)\s+frequency\s+varies|frequency\s+varies|messages?\s+per\s+(?:month|week|request|inquiry)|recurring\s+messages)",
            disclosure_low,
        )
    )
    stop_ok = bool(re.search(r"\bstop\b", disclosure_low) and re.search(r"opt\s*-?\s*out", disclosure_low))
    help_ok = bool(re.search(r"\bhelp\s+for\s+help\b|\breply\s+help\b", disclosure_low))
    stop_and_help_ok = stop_ok and help_ok

    links = root_doc["links"]
    privacy_link_ok = any(
        "/privacy-policy" in (lk.get("href") or "").lower() or "privacy" in (lk.get("text") or "").lower()
        for lk in links
    )
    terms_link_ok = any(
        "/terms-of-service" in (lk.get("href") or "").lower() or "terms" in (lk.get("text") or "").lower()
        for lk in links
    )
    legal_links_ok = privacy_link_ok and terms_link_ok

    privacy_text_low = privacy_doc["text"].lower()
    has_mobile_sms_term = any(t in privacy_text_low for t in ("mobile", "sms", "text message", "opt-in", "telephone"))
    has_no_share_term = bool(
        re.search(
            r"(?:no\s+mobile|never\s+(?:sold|shared)|not\s+(?:be\s+)?(?:sold|shared)|will\s+not\s+be\s+(?:sold|shared)|do\s+not\s+(?:sell|share))",
            privacy_text_low,
        )
        and ("third part" in privacy_text_low or "affiliat" in privacy_text_low)
    )
    privacy_non_sharing_ok = (privacy_probe.get("status") == 200) and has_mobile_sms_term and has_no_share_term

    terms_text_low = terms_doc["text"].lower()
    terms_has_sms_program = bool(
        (terms_probe.get("status") == 200)
        and ("stop" in terms_text_low or "sms" in terms_text_low or "text message" in terms_text_low)
    )

    legal_clean = (legal_name or "").strip()
    legal_norm = re.sub(r"\s+", " ", legal_clean.lower().replace("&", "and"))
    has_umbrella_legal = bool(legal_norm and legal_norm != brand_norm)
    priv_norm = re.sub(r"\s+", " ", privacy_text_low.replace("&", "and"))
    trm_norm = re.sub(r"\s+", " ", terms_text_low.replace("&", "and"))
    legal_in_privacy = (not has_umbrella_legal) or (legal_norm in priv_norm)
    legal_in_terms = (not has_umbrella_legal) or (legal_norm in trm_norm)
    legal_bridge_ok = legal_in_privacy and legal_in_terms
    homepage_opsec_clean = (not has_umbrella_legal) or (legal_norm not in page_norm)

    routes_200_ok = (
        root_probe.get("status") == 200
        and privacy_probe.get("status") == 200
        and terms_probe.get("status") == 200
    )

    dom_issues: list[dict[str, str]] = []
    for route_label, probe in (
        ("/", root_probe),
        ("/privacy-policy", privacy_probe),
        ("/terms-of-service", terms_probe),
    ):
        if probe.get("status") != 200:
            dom_issues.append(
                {
                    "code": "ROUTE_NOT_200_OK",
                    "route": route_label,
                    "severity": "critical",
                    "detail": f"Route {route_label} returned status={probe.get('status')} (error={probe.get('error')}); TCR requires live 200 OK pages.",
                }
            )
    if not cb_found:
        dom_issues.append(
            {
                "code": "MISSING_SMS_OPTIN_CHECKBOX",
                "route": "/",
                "severity": "critical",
                "detail": "No SMS/TCPA consent checkbox found on the root lead form.",
            }
        )
    else:
        if is_pre_checked:
            dom_issues.append(
                {
                    "code": "SMS_CHECKBOX_PRECHECKED",
                    "route": "/",
                    "severity": "high",
                    "detail": f"Checkbox #{primary_cb.get('id') or primary_cb.get('name')} has the 'checked' attribute; TCR/Twilio requires opt-in checkboxes to be unchecked by default.",
                }
            )
        if is_required:
            dom_issues.append(
                {
                    "code": "SMS_CHECKBOX_REQUIRED",
                    "route": "/",
                    "severity": "high",
                    "detail": f"Checkbox #{primary_cb.get('id') or primary_cb.get('name')} has the 'required' attribute; TCR/Twilio requires SMS consent to be optional and not a forced condition of service.",
                }
            )
        if bundles_channels:
            dom_issues.append(
                {
                    "code": "SMS_CONSENT_BUNDLED_CHANNELS",
                    "route": "/",
                    "severity": "high",
                    "detail": "Consent checkbox bundles 'calls, text messages, and emails' into one clause; TCR requires an unbundled SMS-specific opt-in disclosure.",
                }
            )
    if not program_name_in_disclosure:
        dom_issues.append(
            {
                "code": "MISSING_PROGRAM_NAME_IN_OPTIN",
                "route": "/",
                "severity": "high",
                "detail": f"Opt-in checkbox label does not explicitly name '{brand_clean}' as the SMS sender/program.",
            }
        )
    if not msg_rates_ok:
        dom_issues.append(
            {
                "code": "MISSING_MSG_DATA_RATES_DISCLOSURE",
                "route": "/",
                "severity": "high",
                "detail": "Opt-in disclosure is missing 'Msg & data rates may apply' (or 'Message and data rates may apply').",
            }
        )
    if not msg_freq_ok:
        dom_issues.append(
            {
                "code": "MISSING_MSG_FREQUENCY_DISCLOSURE",
                "route": "/",
                "severity": "high",
                "detail": "Opt-in disclosure is missing 'Msg frequency varies' (or 'Message frequency varies').",
            }
        )
    if not stop_and_help_ok:
        dom_issues.append(
            {
                "code": "MISSING_STOP_OR_HELP_DISCLOSURE",
                "route": "/",
                "severity": "high",
                "detail": f"Opt-in disclosure must include both STOP and HELP instructions ('Reply STOP to opt out, HELP for help'); found stop={stop_ok}, help={help_ok}.",
            }
        )
    if not legal_links_ok:
        dom_issues.append(
            {
                "code": "MISSING_LEGAL_LINKS",
                "route": "/",
                "severity": "critical",
                "detail": f"Form/page must include clickable links to /privacy-policy ({privacy_link_ok}) and /terms-of-service ({terms_link_ok}).",
            }
        )
    if not privacy_non_sharing_ok:
        dom_issues.append(
            {
                "code": "MISSING_PRIVACY_NON_SHARING_CLAUSE",
                "route": "/privacy-policy",
                "severity": "critical",
                "detail": "Privacy Policy (/privacy-policy) must explicitly state that mobile phone numbers and SMS opt-in data are never sold or shared with third parties/affiliates for marketing purposes.",
            }
        )
    if has_umbrella_legal and not legal_bridge_ok:
        dom_issues.append(
            {
                "code": "MISSING_UMBRELLA_LEGAL_ENTITY_BRIDGE",
                "route": "/privacy-policy",
                "severity": "high",
                "detail": (
                    f"Umbrella legal entity '{legal_clean}' (d/b/a '{brand_clean}') must be identified in both "
                    f"/privacy-policy ({legal_in_privacy}) and /terms-of-service ({legal_in_terms}) to prevent TCR Error 30909 Brand/Entity mismatch."
                ),
            }
        )

    recommended_optin_html = (
        '<div class="tcpa-box" id="tcpaBoxWrap">\n'
        '  <label class="tcpa-label" for="tcpaConsent">\n'
        '    <input type="checkbox" id="tcpaConsent" name="tcpaConsent" value="accepted_a2p_v1" />\n'
        '    <span id="tcpaTextSpan">\n'
        f"      By checking this box, I consent to receive quote-related and project coordination SMS text messages from <strong>{brand_clean}</strong> at the mobile number provided. Consent is optional and not a condition of purchase or quote submission. Msg &amp; data rates may apply. Msg frequency varies. Reply <code>STOP</code> to opt out, <code>HELP</code> for help. View our <a href=\"/privacy-policy\" target=\"_blank\" rel=\"noopener\">Privacy Policy</a> &amp; <a href=\"/terms-of-service\" target=\"_blank\" rel=\"noopener\">Terms of Service</a>.\n"
        "    </span>\n"
        "  </label>\n"
        "</div>"
    )

    all_checks_ok = (
        routes_200_ok
        and unbundled_ok
        and program_name_in_disclosure
        and msg_rates_ok
        and msg_freq_ok
        and stop_and_help_ok
        and legal_links_ok
        and privacy_non_sharing_ok
        and legal_bridge_ok
    )

    return {
        "ok": all_checks_ok,
        "website_root": website_root,
        "routes": {
            "/": {
                "url": root_probe.get("url"),
                "status": root_probe.get("status"),
                "is_redirect": root_probe.get("is_redirect"),
                "redirect_location": root_probe.get("redirect_location"),
            },
            "/privacy-policy": {
                "url": privacy_probe.get("url"),
                "status": privacy_probe.get("status"),
                "is_redirect": privacy_probe.get("is_redirect"),
                "redirect_location": privacy_probe.get("redirect_location"),
            },
            "/terms-of-service": {
                "url": terms_probe.get("url"),
                "status": terms_probe.get("status"),
                "is_redirect": terms_probe.get("is_redirect"),
                "redirect_location": terms_probe.get("redirect_location"),
            },
        },
        "checks": {
            "routes_200_ok": routes_200_ok,
            "sms_optin_checkbox": {
                "checkbox_found": cb_found,
                "checkbox_id": primary_cb.get("id") if primary_cb else None,
                "checkbox_name": primary_cb.get("name") if primary_cb else None,
                "is_pre_checked": is_pre_checked,
                "is_required": is_required,
                "bundles_multiple_channels": bundles_channels,
                "observed_label_text": cb_label,
                "unbundled_and_optional_ok": unbundled_ok,
            },
            "program_name_in_disclosure": {
                "expected_brand_name": brand_clean,
                "in_checkbox_disclosure": program_name_in_disclosure,
                "in_root_page": program_name_in_page,
                "ok": program_name_in_disclosure,
            },
            "msg_and_data_rates_disclosure": msg_rates_ok,
            "msg_frequency_disclosure": msg_freq_ok,
            "stop_and_help_disclosure": {
                "stop_present": stop_ok,
                "help_present": help_ok,
                "ok": stop_and_help_ok,
            },
            "clickable_legal_links": {
                "privacy_policy_link": privacy_link_ok,
                "terms_of_service_link": terms_link_ok,
                "ok": legal_links_ok,
            },
            "privacy_policy_non_sharing_clause": privacy_non_sharing_ok,
            "terms_of_service_sms_clause_present": terms_has_sms_program,
            "umbrella_legal_entity_bridge": {
                "legal_name": legal_clean or brand_clean,
                "is_umbrella_dba": has_umbrella_legal,
                "in_privacy_policy": legal_in_privacy,
                "in_terms_of_service": legal_in_terms,
                "homepage_opsec_clean": homepage_opsec_clean,
                "ok": legal_bridge_ok,
            },
        },
        "issue_count": len(dom_issues),
        "issues": dom_issues,
        "recommended_optin_html": recommended_optin_html,
    }


def a2p_preflight(
    *,
    brand_name: str,
    website: str,
    email: str | None = None,
    phone: str | None = None,
    location_id: str | None = None,
    legal_name: str | None = None,
    current_profile: dict[str, Any] | None = None,
    dom_fixtures: dict[str, Any] | None = None,
    skip_http: bool = False,
    http_fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Audit (a) GHL location profile vs. target brand and (b) live website DOM for TCR/Twilio A2P 10DLC compliance."""
    clean_brand = (brand_name or "").strip()
    if not clean_brand:
        raise HighLevelError("Provide --brand-name for the canonical A2P 10DLC brand.")
    canonical_root = _normalize_root_url(website)
    canonical_domain = _normalize_domain(canonical_root)
    target_email = (email or f"dispatch@{canonical_domain}").strip()
    target_email_domain = _email_domain(target_email)

    prof = dict(current_profile or {})
    lid = str(location_id or prof.get("location_id") or prof.get("id") or "<LOCATION_ID>").strip()
    cur_name = str(prof.get("name") or prof.get("location_name") or clean_brand).strip()
    cur_website = str(prof.get("website") or prof.get("domain") or canonical_root).strip()
    if cur_website:
        cur_website = _normalize_root_url(cur_website)
    cur_website_domain = _normalize_domain(cur_website)
    cur_email = str(prof.get("email") or target_email).strip()
    cur_email_domain = _email_domain(cur_email)
    cur_phone = str(prof.get("phone") or phone or "").strip()

    fetcher = http_fetcher or _probe_public_url

    # Probe current profile website if it differs from canonical_root or if HTTP is enabled
    cur_website_probe: dict[str, Any] | None = None
    if dom_fixtures and cur_website in dom_fixtures:
        raw_fx = dom_fixtures[cur_website]
        cur_website_probe = (
            raw_fx
            if isinstance(raw_fx, dict)
            else {"url": cur_website, "status": 200, "is_redirect": False, "redirect_location": None, "html": str(raw_fx)}
        )
    elif not skip_http and cur_website:
        cur_website_probe = fetcher(cur_website)

    # Probe canonical website routes (/, /privacy-policy, /terms-of-service)
    route_probes: dict[str, dict[str, Any]] = {}
    for route_path in ("/", "/privacy-policy", "/terms-of-service"):
        full_url = canonical_root + ("" if route_path == "/" else route_path)
        if dom_fixtures and (route_path in dom_fixtures or full_url in dom_fixtures):
            fx = dom_fixtures.get(route_path) if route_path in dom_fixtures else dom_fixtures.get(full_url)
            if isinstance(fx, dict):
                route_probes[route_path] = {
                    "url": full_url,
                    "status": int(fx.get("status", 200)),
                    "is_redirect": bool(fx.get("is_redirect", int(fx.get("status", 200)) in {301, 302, 303, 307, 308})),
                    "redirect_location": fx.get("redirect_location"),
                    "html": str(fx.get("html") or ""),
                    "error": fx.get("error"),
                }
            else:
                route_probes[route_path] = {
                    "url": full_url,
                    "status": 200,
                    "is_redirect": False,
                    "redirect_location": None,
                    "html": str(fx or ""),
                    "error": None,
                }
        elif not skip_http:
            if route_path == "/" and cur_website.rstrip("/") == canonical_root.rstrip("/") and cur_website_probe is not None:
                route_probes[route_path] = cur_website_probe
            else:
                route_probes[route_path] = fetcher(full_url)
        else:
            route_probes[route_path] = {
                "url": full_url,
                "status": None,
                "is_redirect": False,
                "redirect_location": None,
                "html": "",
                "error": "skipped_http",
            }

    brand_name_match = cur_name.lower() == clean_brand.lower()
    website_domain_match = cur_website_domain == canonical_domain
    cur_website_is_redirect = bool(cur_website_probe and cur_website_probe.get("is_redirect"))
    canonical_root_is_200 = (
        route_probes["/"].get("status") == 200 and not route_probes["/"].get("is_redirect")
        if route_probes["/"].get("status") is not None
        else True
    )
    website_canonical_ok = website_domain_match and (not cur_website_is_redirect) and canonical_root_is_200
    email_domain_match = bool(cur_email_domain and cur_email_domain == canonical_domain and target_email_domain == canonical_domain)
    phone_check = inspect_a2p_phone(cur_phone)

    profile_issues: list[dict[str, str]] = []
    if not brand_name_match:
        profile_issues.append(
            {
                "code": "BRAND_NAME_MISMATCH",
                "severity": "critical",
                "detail": f"GHL Business Profile name '{cur_name}' does not match canonical website brand '{clean_brand}'.",
            }
        )
    if not website_domain_match:
        profile_issues.append(
            {
                "code": "WEBSITE_DOMAIN_MISMATCH",
                "severity": "critical",
                "detail": f"GHL Business Profile website '{cur_website}' ({cur_website_domain}) does not match canonical website '{canonical_root}' ({canonical_domain}).",
            }
        )
    if cur_website_is_redirect:
        profile_issues.append(
            {
                "code": "WEBSITE_IS_REDIRECT_PIPE",
                "severity": "critical",
                "detail": (
                    f"GHL Business Profile website '{cur_website}' returned HTTP {cur_website_probe.get('status')} "
                    f"redirecting to '{cur_website_probe.get('redirect_location')}'. TCR/Twilio auto-rejects A2P 10DLC "
                    "registrations when the Business Profile website is a 301/302 redirect pipe."
                ),
            }
        )
    if not canonical_root_is_200:
        profile_issues.append(
            {
                "code": "CANONICAL_WEBSITE_NOT_200_OK",
                "severity": "critical",
                "detail": f"Target canonical website '{canonical_root}' did not return HTTP 200 OK (status={route_probes['/'].get('status')}).",
            }
        )
    if not email_domain_match:
        profile_issues.append(
            {
                "code": "EMAIL_DOMAIN_MISMATCH",
                "severity": "critical",
                "detail": f"GHL Business Profile email '{cur_email}' (domain '{cur_email_domain}') does not match canonical website domain '{canonical_domain}'.",
            }
        )
    if not phone_check["ok"]:
        profile_issues.append(
            {
                "code": "PHONE_555_PLACEHOLDER" if phone_check["is_555_placeholder"] else "PHONE_INVALID_OR_MISSING",
                "severity": "critical",
                "detail": phone_check["reason"],
            }
        )

    old_terms = []
    if not brand_name_match and cur_name:
        old_terms.append(cur_name)
    if not website_domain_match and cur_website_domain:
        old_terms.append(cur_website_domain)
    new_terms = []
    if not brand_name_match and cur_name:
        new_terms.append(clean_brand)
    if not website_domain_match and cur_website_domain:
        new_terms.append(canonical_domain)

    replace_flags = (
        f' --replace-from "{",".join(old_terms)}" --replace-to "{",".join(new_terms)}" --include-workflow-steps'
        if old_terms
        else ""
    )
    remediation_commands = {
        "agency_location_rebrand_preview": (
            f'legends-gohighlevel location-rebrand --location-id {lid} '
            f'--name "{clean_brand}" --website "{canonical_root}" --email "{target_email}"{replace_flags}'
        ),
        "subaccount_update_preview": (
            f'legends-gohighlevel subaccount-update --name "{clean_brand}" '
            f'--website "{canonical_root}" --email "{target_email}"'
        ),
    }

    profile_audit = {
        "ok": len(profile_issues) == 0,
        "location_id": lid,
        "current_profile": {
            "name": cur_name,
            "website": cur_website,
            "website_probe": (
                {
                    "status": cur_website_probe.get("status"),
                    "is_redirect": cur_website_probe.get("is_redirect"),
                    "redirect_location": cur_website_probe.get("redirect_location"),
                }
                if cur_website_probe
                else None
            ),
            "email": cur_email,
            "phone": cur_phone,
        },
        "target_brand": {
            "brand_name": clean_brand,
            "website": canonical_root,
            "domain": canonical_domain,
            "email": target_email,
        },
        "checks": {
            "brand_name_match": brand_name_match,
            "website_domain_match": website_domain_match,
            "website_not_redirect_pipe": not cur_website_is_redirect,
            "canonical_website_200_ok": canonical_root_is_200,
            "website_canonical_200_ok": website_canonical_ok,
            "email_domain_match": email_domain_match,
            "phone_valid_non_placeholder": phone_check["ok"],
            "phone_details": phone_check,
        },
        "issue_count": len(profile_issues),
        "issues": profile_issues,
        "remediation_commands": remediation_commands,
    }

    if skip_http and not dom_fixtures:
        dom_audit: dict[str, Any] = {
            "ok": False,
            "skipped": True,
            "website_root": canonical_root,
            "note": "DOM HTTP probing was skipped (--skip-http without --dom-json).",
            "issue_count": 0,
            "issues": [],
        }
    else:
        dom_audit = _audit_a2p_dom(
            root_probe=route_probes["/"],
            privacy_probe=route_probes["/privacy-policy"],
            terms_probe=route_probes["/terms-of-service"],
            brand_name=clean_brand,
            website_root=canonical_root,
            legal_name=legal_name,
        )

    return {
        "ok": bool(profile_audit["ok"] and dom_audit["ok"]),
        "location_id": lid,
        "brand_name": clean_brand,
        "legal_name": (legal_name or clean_brand).strip(),
        "website": canonical_root,
        "profile_audit": profile_audit,
        "dom_audit": dom_audit,
    }


def a2p_campaign_pack(
    *,
    brand_name: str,
    website: str,
    email: str,
    phone: str | None = None,
    location_id: str | None = None,
    legal_name: str | None = None,
    address: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str = "US",
    timezone: str = "America/Chicago",
    use_case: str = "LOW_VOLUME_MIXED",
    vertical: str = "CONSTRUCTION_MATERIALS",
    form_url: str | None = None,
    form_selector: str = "form#quoteForm input#tcpaConsent",
    privacy_url: str | None = None,
    terms_url: str | None = None,
    service_summary: str | None = None,
    old_brand_terms: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a copy-paste and API-ready A2P 10DLC Campaign Registration JSON and Markdown bundle."""
    clean_brand = (brand_name or "").strip()
    if not clean_brand:
        raise HighLevelError("Provide --brand-name for the A2P 10DLC campaign pack.")
    canonical_root = _normalize_root_url(website)
    canonical_domain = _normalize_domain(canonical_root)
    clean_email = (email or "").strip()
    if not clean_email or "@" not in clean_email:
        raise HighLevelError("Provide a valid business --email matching the canonical website domain.")
    if _email_domain(clean_email) != canonical_domain:
        raise HighLevelError(
            f"--email domain '{_email_domain(clean_email)}' must match canonical --website domain '{canonical_domain}'."
        )

    lid = (location_id or "<LOCATION_ID>").strip()
    clean_legal = (legal_name or clean_brand).strip()
    clean_phone = (phone or "(512) 555-0100 [Provision Live LC Phone Local Number]").strip()
    phone_audit = inspect_a2p_phone(phone) if phone else None
    display_phone = clean_phone if (phone_audit and phone_audit["ok"]) else "(512) 555-0100"
    clean_address = (address or "100 Main St").strip()
    clean_city = (city or "Austin").strip()
    clean_state = (state or "TX").strip()
    clean_postal = (postal_code or "78701").strip()
    clean_country = (country or "US").strip()
    clean_tz = (timezone or "America/Chicago").strip()
    clean_use_case = (use_case or "LOW_VOLUME_MIXED").strip()
    clean_vertical = (vertical or "CONSTRUCTION_MATERIALS").strip()
    clean_form_url = (form_url or f"{canonical_root}/#quoteForm").strip()
    clean_privacy_url = (privacy_url or f"{canonical_root}/privacy-policy").strip()
    clean_terms_url = (terms_url or f"{canonical_root}/terms-of-service").strip()
    clean_selector = (form_selector or "form#quoteForm input#tcpaConsent").strip()
    clean_services = (
        service_summary
        or "monolithic concrete slab foundations, laser select-fill pad grading, and metal building erection quotes"
    ).strip()

    old_terms = [t.strip() for t in (old_brand_terms or []) if t and t.strip()]
    new_terms = [
        canonical_domain if ("." in t and " " not in t) else clean_brand
        for t in old_terms
    ]
    replace_args = (
        f' \\\n  --replace-from "{",".join(old_terms)}" \\\n  --replace-to "{",".join(new_terms)}" \\\n  --include-workflow-steps'
        if old_terms
        else ""
    )

    rebrand_cli = (
        f'legends-gohighlevel location-rebrand \\\n'
        f'  --location-id {lid} \\\n'
        f'  --name "{clean_brand}" \\\n'
        f'  --website "{canonical_root}" \\\n'
        f'  --email "{clean_email}" \\\n'
        f'  --address "{clean_address}" \\\n'
        f'  --city "{clean_city}" \\\n'
        f'  --state "{clean_state}" \\\n'
        f'  --postal-code "{clean_postal}" \\\n'
        f'  --country "{clean_country}" \\\n'
        f'  --timezone "{clean_tz}"{replace_args}'
    )

    entity_prefix = (
        f"{clean_brand} (a web property owned and operated by {clean_legal})"
        if clean_legal.lower().replace("&", "and") != clean_brand.lower().replace("&", "and")
        else clean_brand
    )
    campaign_description = (
        f"{entity_prefix} ({canonical_root}) uses this campaign to send transactional and customer-care SMS notifications "
        f"to property owners who explicitly request a project estimate for {clean_services} through our online calculator "
        f"and quote request form at {clean_form_url}. Messages include instant specification confirmations, project "
        f"coordinator scheduling updates, on-site evaluation reminders, and written line-item quote notifications. "
        f"No cold outreach, purchased lead lists, or third-party affiliate marketing messages are ever sent."
    )

    opt_in_checkbox_disclosure = (
        f"By checking this box, I consent to receive quote-related and project coordination SMS text messages from "
        f"{clean_brand} at the mobile number provided. Consent is optional and not a condition of purchase or quote "
        f"submission. Msg & data rates may apply. Msg frequency varies. Reply STOP to opt out, HELP for help. "
        f"View our Privacy Policy ({clean_privacy_url}) and Terms of Service ({clean_terms_url})."
    )

    opt_in_workflow_description = (
        f"1. End users visit {canonical_root}/ (specifically the online calculator and quote request form at {clean_form_url}). "
        f"2. The user enters their Full Name (input#fullName), Mobile Phone Number (input#phone), and Property Town/ZIP Code (input#townOrZip) inside form#quoteForm. "
        f"3. Above the submit button (button#submitQuoteBtn), the user is presented with an optional, unchecked-by-default SMS consent checkbox ({clean_selector}) displaying the following verbatim disclosure: "
        f'"{opt_in_checkbox_disclosure}" '
        f"4. Direct clickable links to the live Privacy Policy ({clean_privacy_url}, which contains an explicit mobile/SMS non-sharing clause) and Terms of Service ({clean_terms_url}) are displayed adjacent to the checkbox. "
        f"5. SMS messages are only sent when the user explicitly checks {clean_selector} and submits the form."
    )

    sample_messages = [
        (
            f"{clean_brand}: Hi {{{{contact.first_name}}}}, we received your {canonical_domain} estimate request for your "
            f"concrete slab & building project in {{{{contact.city}}}}. Our estimator is reviewing your specs now. "
            f"Msg & data rates may apply. Reply HELP for help, STOP to opt out."
        ),
        (
            f"{clean_brand}: Hi {{{{contact.first_name}}}}, your written line-item foundation & pad grading quote is ready. "
            f"Are you available for a quick 5-minute site-access review call today or tomorrow? "
            f"Msg & data rates may apply. Reply HELP for help, STOP to opt out."
        ),
        (
            f"{clean_brand}: Reminder for {{{{contact.first_name}}}}: Your on-site pad elevation and slab layout check in "
            f"{{{{contact.city}}}} is confirmed. Reply to this text if you need to adjust your time window. "
            f"Msg & data rates may apply. Reply HELP for help, STOP to opt out."
        ),
    ]

    opt_in_confirmation_message = (
        f"{clean_brand}: You are now opted in to receive SMS updates regarding your quote request and project "
        f"specifications. Msg & data rates may apply. Msg frequency varies. Reply HELP for help, STOP to opt out."
    )
    opt_out_message = (
        f"{clean_brand}: You have been unsubscribed and will receive no further SMS messages from us. "
        f"Reply START to re-subscribe or email {clean_email} for assistance."
    )
    help_message = (
        f"{clean_brand}: For assistance with your concrete slab or metal building quote, call {display_phone}, "
        f"email {clean_email}, or visit {canonical_root}. Msg & data rates may apply. Reply STOP to opt out."
    )

    brand_alignment_checklist = {
        "location_id": lid,
        "ghl_business_profile_targets": {
            "name": clean_brand,
            "legalBusinessName": clean_legal,
            "website": canonical_root,
            "email": clean_email,
            "phone": clean_phone,
            "address": clean_address,
            "city": clean_city,
            "state": clean_state,
            "postalCode": clean_postal,
            "country": clean_country,
            "timezone": clean_tz,
        },
        "rebrand_commands": {
            "agency_location_rebrand": rebrand_cli,
            "subaccount_update": (
                f'legends-gohighlevel subaccount-update \\\n'
                f'  --name "{clean_brand}" \\\n'
                f'  --website "{canonical_root}" \\\n'
                f'  --email "{clean_email}" \\\n'
                f'  --address "{clean_address}" \\\n'
                f'  --city "{clean_city}" \\\n'
                f'  --state "{clean_state}" \\\n'
                f'  --postal-code "{clean_postal}" \\\n'
                f'  --country "{clean_country}" \\\n'
                f'  --timezone "{clean_tz}"'
            ),
        },
        "pre_submission_gates": [
            f"Gate 1 (Canonical 200 OK Website): GHL Business Profile website MUST be '{canonical_root}' (returning HTTP 200 OK), NEVER a 301 redirect domain.",
            f"Gate 2 (Brand & Email Parity): GHL Business Profile name MUST be '{clean_brand}' and email MUST be '{clean_email}' (@{canonical_domain}).",
            "Gate 3 (Live LC Phone Number): Replace any +15125550100 (555 placeholder) with a live provisioned LC Phone local number before submitting A2P.",
            f"Gate 4 (Unbundled Optional SMS Checkbox): {clean_selector} on {canonical_root}/ must be unchecked by default, not required, and display '{clean_brand}', 'Msg & data rates may apply', 'Msg frequency varies', and 'Reply STOP to opt out, HELP for help'.",
            f"Gate 5 (Privacy Policy Non-Sharing Clause): {clean_privacy_url} must return HTTP 200 OK and state that mobile phone numbers and SMS opt-in data are never sold or shared with third parties for marketing purposes.",
        ],
    }

    campaign_registration = {
        "use_case": clean_use_case,
        "vertical": clean_vertical,
        "campaign_description": campaign_description,
        "opt_in_method": "WEB_FORM",
        "opt_in_form_url": clean_form_url,
        "opt_in_form_selector": clean_selector,
        "privacy_policy_url": clean_privacy_url,
        "terms_of_service_url": clean_terms_url,
        "opt_in_workflow_description": opt_in_workflow_description,
        "opt_in_checkbox_disclosure": opt_in_checkbox_disclosure,
        "sample_messages": sample_messages,
        "opt_in_keywords": ["START", "YES", "UNSTOP"],
        "opt_in_confirmation_message": opt_in_confirmation_message,
        "opt_out_keywords": ["STOP", "END", "CANCEL", "UNSUBSCRIBE", "QUIT"],
        "opt_out_message": opt_out_message,
        "help_keywords": ["HELP", "INFO"],
        "help_message": help_message,
        "message_contents_flags": {
            "embedded_link": True,
            "embedded_phone": True,
            "age_gated": False,
            "direct_lending_or_loan": False,
            "affiliate_lead_generation": False,
        },
    }

    markdown = "\n".join(
        [
            f"# A2P 10DLC 1-Shot Registration Pack: {clean_brand} (`{lid}`)",
            "",
            "## 1. Brand Alignment & GHL Business Profile Checklist",
            "",
            "| Field | Required Value | TCR / Twilio Validation Rule |",
            "| :--- | :--- | :--- |",
            f"| **Location ID** | `{lid}` | Target GoHighLevel sub-account |",
            f"| **Friendly Business / DBA Name** | `{clean_brand}` | Must match `<title>`, `<h1>`, and SMS sender prefix |",
            f"| **Legal Business Name** | `{clean_legal}` | Must match EIN / Sole Prop / LLC Trust Center filing |",
            f"| **Canonical Website URL** | `{canonical_root}` | Must return `HTTP 200 OK` (NEVER a `301` redirect pipe) |",
            f"| **Business Email** | `{clean_email}` | Domain (`@{canonical_domain}`) must match website root |",
            f"| **LC Phone Number** | `{clean_phone}` | Must be a live provisioned local number (never a `555` placeholder) |",
            f"| **Physical Address** | `{clean_address}, {clean_city}, {clean_state} {clean_postal}, {clean_country}` | Complete street address required for CAN-SPAM & A2P |",
            "",
            "### GHL Location Rebrand Command (Preview -> Apply)",
            "```sh",
            rebrand_cli,
            "```",
            "",
            "## 2. A2P 10DLC Campaign Registration Fields (Copy-Paste Ready)",
            "",
            f"- **Campaign Use Case:** `{clean_use_case}`",
            f"- **Vertical:** `{clean_vertical}`",
            f"- **Opt-In Form URL:** `{clean_form_url}`",
            f"- **DOM Selector:** `{clean_selector}`",
            f"- **Privacy Policy URL:** `{clean_privacy_url}`",
            f"- **Terms of Service URL:** `{clean_terms_url}`",
            "- **Message Content Flags:** Embedded Link = `Yes` (canonical domain only, no public shorteners), Embedded Phone = `Yes`, Direct Lending/Loan = `No`, Age-Gated = `No`, Third-Party/Affiliate Lead Gen = `No`",
            "",
            "### Campaign Use Case Description",
            "```text",
            campaign_description,
            "```",
            "",
            "### How Do Leads/Contacts Consent to Receive Messages? (Opt-In Workflow)",
            "```text",
            opt_in_workflow_description,
            "```",
            "",
            "### Verbatim Web Form Checkbox Disclosure Text",
            "```text",
            opt_in_checkbox_disclosure,
            "```",
            "",
            "## 3. Compliant Sample SMS Messages",
            "",
            "### Sample Message #1 (Estimator Spec Confirmation)",
            "```text",
            sample_messages[0],
            "```",
            "",
            "### Sample Message #2 (Written Quote & Site Review Scheduling)",
            "```text",
            sample_messages[1],
            "```",
            "",
            "### Sample Message #3 (On-Site Pad & Slab Check Reminder)",
            "```text",
            sample_messages[2],
            "```",
            "",
            "## 4. Mandatory Keyword Auto-Replies (`START` / `STOP` / `HELP`)",
            "",
            "- **Opt-In Keywords (`START, YES, UNSTOP`):**",
            f"  `{opt_in_confirmation_message}`",
            "- **Opt-Out Keywords (`STOP, END, CANCEL, UNSUBSCRIBE, QUIT`):**",
            f"  `{opt_out_message}`",
            "- **Help Keywords (`HELP, INFO`):**",
            f"  `{help_message}`",
            "",
        ]
    )

    return {
        "ok": True,
        "location_id": lid,
        "brand_name": clean_brand,
        "legal_name": clean_legal,
        "website": canonical_root,
        "email": clean_email,
        "phone": clean_phone,
        "phone_audit": phone_audit,
        "brand_alignment_checklist": brand_alignment_checklist,
        "campaign_registration": campaign_registration,
        "markdown": markdown,
    }

