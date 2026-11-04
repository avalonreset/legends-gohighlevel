"""Bounded GoHighLevel API v2 and internal web-app backend transport. No arbitrary URLs, redirects, or write retries."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import __version__

API_ROOT = "https://services.leadconnectorhq.com"
BACKEND_ROOT = "https://backend.leadconnectorhq.com"
API_VERSION = "2021-07-28"
API_VERSION_V3 = "v3"
ID_RE = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
OBJECT_KEY_RE = re.compile(r"[A-Za-z0-9._-]{2,80}\Z")
SSH_TARGET_RE = re.compile(r"[A-Za-z0-9._-]+@[A-Za-z0-9._-]+\Z")
CONTAINER_RE = re.compile(r"[A-Za-z0-9._-]{2,80}\Z")

ALLOWED_PATHS = (
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/customValues(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/customFields\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/tags(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/contacts/\Z"),
    re.compile(r"/contacts/upsert\Z"),
    re.compile(r"/contacts/[A-Za-z0-9_-]{8,64}(?:/(?:tags|notes))?\Z"),
    re.compile(r"/opportunities/pipelines\Z"),
    re.compile(r"/opportunities/search\Z"),
    re.compile(r"/opportunities/\Z"),
    re.compile(r"/opportunities/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/calendars/\Z"),
    re.compile(r"/calendars/[A-Za-z0-9_-]{8,64}(?:/free-slots)?\Z"),
    re.compile(r"/conversations/search\Z"),
    re.compile(r"/workflows/\Z"),
    re.compile(r"/workflows/search\Z"),
    re.compile(r"/workflows/step-types\Z"),
    re.compile(r"/workflows/definition/validate\Z"),
    re.compile(r"/workflows/[A-Za-z0-9_-]{8,64}(?:/(?:definition|status|logs|logs/aggregate))?\Z"),
    re.compile(r"/forms/\Z"),
    re.compile(r"/surveys/\Z"),
    re.compile(r"/funnels/funnel/list\Z"),
    re.compile(r"/funnels/page(?:/count)?\Z"),
    re.compile(r"/funnels/lookup/redirect/list\Z"),
    re.compile(r"/objects/\Z"),
    re.compile(r"/objects/[A-Za-z0-9._-]{2,80}\Z"),
    re.compile(r"/objects/[A-Za-z0-9._-]{2,80}/records/search\Z"),
    re.compile(r"/associations/\Z"),
    re.compile(r"/associations/objectKey/[A-Za-z0-9._-]{2,80}\Z"),
    re.compile(r"/voice-ai/agents(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/voice-ai/dashboard/call-logs(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/conversation-ai/agents/search\Z"),
    re.compile(r"/conversation-ai/agents/[A-Za-z0-9_-]{8,64}(?:/(?:actions|followup-settings))?\Z"),
    re.compile(r"/social-media-posting/[A-Za-z0-9_-]{8,64}/accounts\Z"),
    re.compile(r"/social-media-posting/[A-Za-z0-9_-]{8,64}/posts/list\Z"),
    re.compile(r"/social-media-posting/[A-Za-z0-9_-]{8,64}/posts(?:/[A-Za-z0-9_-]{8,64})?\Z"),
)

ALLOWED_BACKEND_PATHS = (
    re.compile(r"/companies/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/locations/search\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/customFields(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/customValues(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/tags(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/contacts/\Z"),
    re.compile(r"/contacts/upsert\Z"),
    re.compile(r"/contacts/[A-Za-z0-9_-]{8,64}(?:/(?:tags|notes))?\Z"),
    re.compile(r"/opportunities/pipelines(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/opportunities/search\Z"),
    re.compile(r"/opportunities/\Z"),
    re.compile(r"/opportunities/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/calendars/\Z"),
    re.compile(r"/calendars/[A-Za-z0-9_-]{8,64}(?:/free-slots)?\Z"),
    re.compile(r"/workflows/\Z"),
    re.compile(r"/workflows/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/oauth/static/scopes\Z"),
    re.compile(r"/marketplace/private-integration/location/[A-Za-z0-9_-]{8,64}(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/users/search\Z"),
    re.compile(r"/users/permissions\Z"),
    re.compile(r"/users/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/reporting/dashboards\Z"),
    re.compile(r"/reporting/dashboards/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/reporting/dashboards/[A-Za-z0-9_-]{8,64}/permissions\Z"),
    re.compile(r"/reporting/dashboards/[A-Za-z0-9_-]{8,64}/duplicate\Z"),
    re.compile(r"/email-isv/onload\Z"),
    re.compile(r"/email-isv/Setting/feature/company/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/email-isv/Setting/feature/location/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/email-isv/feature/domain(?:/(?:list|verify|set-default|v2/add-domain|[A-Za-z0-9._-]{2,120}|set-default-headers/[A-Za-z0-9._-]{2,120}|unset-default-headers/[A-Za-z0-9._-]{2,120}))?\Z"),
    re.compile(r"/email-isv/provider/mailgun(?:/(?:locations|domains|forwarding-address-settings|reply-address-settings))?\Z"),
    re.compile(r"/conversations/providers/mailgun(?:/(?:fetch|fetch/domain|validations))?\Z"),
    re.compile(r"/saas-billing-v2/billing-config/LOCATION/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/saas-billing-v2/billing-config/group/[A-Za-z0-9_-]{8,64}/[A-Za-z0-9_,-]{3,400}\Z"),
    re.compile(r"/saas_service/saas-config/[A-Za-z0-9_-]{8,64}/update-(?:twilio|mailgun)-rebilling\Z"),
    re.compile(r"/saas-api/location-metadata/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/internal-tools/billing/company-info/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/internal-tools/billing/customer(?:/billing-details)?\Z"),
    re.compile(r"/internal-tools/billing/company/[A-Za-z0-9_-]{8,64}/plan\Z"),
    re.compile(r"/internal-tools/billing/update-tax\Z"),
)

ALLOWED_BACKEND_WRITE_PATHS = (
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/customFields(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/customValues(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/tags(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/contacts/\Z"),
    re.compile(r"/contacts/upsert\Z"),
    re.compile(r"/contacts/[A-Za-z0-9_-]{8,64}(?:/(?:tags|notes))?\Z"),
    re.compile(r"/opportunities/pipelines(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/opportunities/\Z"),
    re.compile(r"/opportunities/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/calendars/\Z"),
    re.compile(r"/calendars/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/workflows/\Z"),
    re.compile(r"/workflows/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/marketplace/private-integration/location/[A-Za-z0-9_-]{8,64}(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/users/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/reporting/dashboards/[A-Za-z0-9_-]{8,64}/permissions\Z"),
    re.compile(r"/reporting/dashboards/[A-Za-z0-9_-]{8,64}/duplicate\Z"),
    re.compile(r"/email-isv/Setting/feature/company/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/email-isv/Setting/feature/location/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/email-isv/feature/domain(?:/(?:verify|set-default|v2/add-domain|[A-Za-z0-9._-]{2,120}|set-default-headers/[A-Za-z0-9._-]{2,120}|unset-default-headers/[A-Za-z0-9._-]{2,120}))?\Z"),
    re.compile(r"/email-isv/provider/mailgun(?:/(?:locations|domains|forwarding-address-settings|reply-address-settings))?\Z"),
    re.compile(r"/conversations/providers/mailgun(?:/validations)?\Z"),
    re.compile(r"/saas-billing-v2/billing-config/group/[A-Za-z0-9_-]{8,64}/[A-Za-z0-9_,-]{3,400}\Z"),
    re.compile(r"/saas_service/saas-config/[A-Za-z0-9_-]{8,64}/update-(?:twilio|mailgun)-rebilling\Z"),
    re.compile(r"/saas-api/location-metadata/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/internal-tools/billing/customer/billing-details\Z"),
    re.compile(r"/internal-tools/billing/update-tax\Z"),
)

MAX_RESPONSE = 16 * 1024 * 1024

_WORKER_INDEXEDDB_SCRIPT = r"""
const fs = require('fs');
const path = require('path');
const targetUserId = process.env.GHL_TARGET_USER_ID || '';
const dir = '/profile/Default/IndexedDB/https_app.gohighlevel.com_0.indexeddb.leveldb';
if (!fs.existsSync(dir)) {
  console.error(JSON.stringify({ error: 'IndexedDB directory not found in container.' }));
  process.exit(1);
}
const files = fs.readdirSync(dir).filter(f => f.endsWith('.ldb') || f.endsWith('.log'));
let bestTok = null;
let bestExp = 0;
let bestUser = null;
for (const f of files) {
  const buf = fs.readFileSync(path.join(dir, f));
  const str = buf.toString('latin1');
  const matches = str.match(/eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}/g) || [];
  for (const m of matches) {
    try {
      const payload = JSON.parse(Buffer.from(m.split('.')[1], 'base64url').toString('utf8'));
      const iss = String(payload.iss || '');
      if (!iss.includes('securetoken.google.com')) continue;
      if (targetUserId && payload.user_id !== targetUserId) continue;
      if (payload.exp && payload.exp > bestExp) {
        bestExp = payload.exp;
        bestTok = m;
        bestUser = payload.user_id || payload.sub || null;
      }
    } catch (e) {}
  }
}
if (!bestTok) {
  console.error(JSON.stringify({ error: 'No active Firebase ID token found in IndexedDB.' }));
  process.exit(1);
}
console.log(JSON.stringify({ token: bestTok, exp: bestExp, user_id: bestUser }));
"""


class HighLevelError(Exception):
    """Actionable error safe to display without leaking tokens or raw provider bodies."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HighLevelError("Redirect refused; credentials were not forwarded.")


def valid_id(value: str | None) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value.strip()):
        raise HighLevelError("Expected a valid HighLevel resource identifier.")
    return value.strip()


def valid_object_key(value: str | None) -> str:
    if not isinstance(value, str) or not OBJECT_KEY_RE.fullmatch(value.strip()):
        raise HighLevelError("Expected a valid HighLevel object key (e.g. custom_objects.vehicles).")
    return value.strip()


def _valid_token(value: str | None, env_hint: str = "GHL_PIT (or GHL_ACCESS_TOKEN)") -> str:
    if not value or value != value.strip() or len(value) < 12 or any(
        ord(c) < 33 or ord(c) > 126 for c in value
    ):
        raise HighLevelError(
            f"Set {env_hint} through your secret manager in the process environment."
        )
    return value


def subaccount_config_path() -> Path:
    custom = os.environ.get("GHL_CONFIG_FILE")
    if custom:
        return Path(custom).expanduser().resolve()
    return Path.home() / ".config" / "legends-gohighlevel" / "config.json"


def _mask_token(tok: str | None) -> str | None:
    if not tok or len(tok) < 8:
        return None
    prefix = "pit-" if tok.startswith("pit-") else tok[:4]
    return f"{prefix}****{tok[-4:]}"


def load_subaccount_config(profile: str | None = None) -> dict[str, Any]:
    cfg_path = subaccount_config_path()
    file_cfg: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                file_cfg = loaded
        except (OSError, ValueError):
            file_cfg = {}

    raw_profiles = file_cfg.get("profiles") if isinstance(file_cfg.get("profiles"), dict) else {}
    selected_profile = (
        profile
        or os.environ.get("GHL_PROFILE")
        or file_cfg.get("default_profile")
        or ("default" if "default" in raw_profiles else (next(iter(raw_profiles)) if raw_profiles else "default"))
    )
    prof_entry = raw_profiles.get(selected_profile) if isinstance(raw_profiles.get(selected_profile), dict) else {}

    env_tok = os.environ.get("GHL_PIT") or os.environ.get("GHL_ACCESS_TOKEN") or ""
    env_loc = os.environ.get("GHL_LOCATION_ID") or ""

    file_tok = str(prof_entry.get("pit") or prof_entry.get("token") or file_cfg.get("pit") or file_cfg.get("token") or "").strip()
    file_loc = str(prof_entry.get("location_id") or file_cfg.get("location_id") or "").strip()

    explicit_profile = bool(profile and profile in raw_profiles)
    if explicit_profile and file_tok and file_loc:
        resolved_tok = file_tok
        resolved_loc = file_loc
        source = f"config:{cfg_path}#{selected_profile}"
    else:
        resolved_tok = env_tok.strip() or file_tok
        resolved_loc = env_loc.strip() or file_loc
        source = (
            "env:GHL_PIT+GHL_LOCATION_ID"
            if (env_tok.strip() and env_loc.strip())
            else (f"config:{cfg_path}#{selected_profile}" if (file_tok and file_loc) else "unconfigured")
        )

    profiles_summary = {}
    for pname, pval in raw_profiles.items():
        if isinstance(pval, dict):
            ptok = str(pval.get("pit") or pval.get("token") or "").strip()
            profiles_summary[pname] = {
                "name": pval.get("name") or pname,
                "location_id": pval.get("location_id"),
                "token_masked": _mask_token(ptok),
            }

    return {
        "config_path": str(cfg_path),
        "config_file_present": cfg_path.is_file(),
        "selected_profile": selected_profile,
        "source": source,
        "location_id": resolved_loc,
        "token_present": bool(resolved_tok),
        "token_masked": _mask_token(resolved_tok),
        "profiles": profiles_summary,
        "_resolved_token": resolved_tok,
    }


def agency_config_path() -> Path:
    custom = os.environ.get("GHL_AGENCY_CONFIG")
    if custom:
        return Path(custom).expanduser().resolve()
    return Path.home() / ".config" / "legends-gohighlevel" / "agency.json"


def load_agency_config() -> dict[str, Any]:
    cfg_path = agency_config_path()
    file_cfg: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                file_cfg = loaded
        except (OSError, ValueError):
            file_cfg = {}

    company_id = os.environ.get("GHL_COMPANY_ID") or file_cfg.get("company_id") or ""
    worker_ssh = os.environ.get("GHL_WORKER_SSH") or file_cfg.get("worker_ssh") or ""
    worker_container = (
        os.environ.get("GHL_WORKER_CONTAINER")
        or file_cfg.get("worker_container")
        or "ghl-worker"
    )
    worker_user_id = (
        os.environ.get("GHL_WORKER_USER_ID")
        or file_cfg.get("worker_user_id")
        or ""
    )
    return {
        "config_path": str(cfg_path),
        "config_file_present": cfg_path.is_file(),
        "company_id": str(company_id).strip(),
        "worker_ssh": str(worker_ssh).strip(),
        "worker_container": str(worker_container).strip(),
        "worker_user_id": str(worker_user_id).strip(),
        "token_env_present": bool(os.environ.get("GHL_TOKEN_ID")),
    }


def extract_worker_token_via_ssh(
    *,
    worker_ssh: str,
    worker_container: str = "ghl-worker",
    worker_user_id: str = "",
) -> dict[str, Any]:
    """Extract the active Firebase token-id from the worker container IndexedDB via SSH."""
    clean_ssh = worker_ssh.strip()
    clean_container = worker_container.strip()
    clean_user = worker_user_id.strip()
    if not SSH_TARGET_RE.fullmatch(clean_ssh):
        raise HighLevelError("Invalid worker SSH target format (expected user@host).")
    if not CONTAINER_RE.fullmatch(clean_container):
        raise HighLevelError("Invalid worker container name.")
    if clean_user and not ID_RE.fullmatch(clean_user):
        raise HighLevelError("Invalid worker user ID format.")

    remote_cmd = f"docker exec -i -e GHL_TARGET_USER_ID={clean_user} {clean_container} node -"
    try:
        proc = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", clean_ssh, remote_cmd],
            input=_WORKER_INDEXEDDB_SCRIPT,
            text=True,
            capture_output=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HighLevelError(f"Failed to execute SSH worker token extraction: {exc}") from None

    if proc.returncode != 0:
        raise HighLevelError(
            "Worker IndexedDB token extraction failed; verify SSH connectivity and container status."
        )
    try:
        parsed = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise HighLevelError("Worker IndexedDB token helper returned invalid JSON.") from None

    tok = _valid_token(str(parsed.get("token", "")), env_hint="GHL_TOKEN_ID")
    return {
        "token": tok,
        "exp": parsed.get("exp"),
        "user_id": parsed.get("user_id"),
        "source": f"ssh:{clean_ssh}:{clean_container}",
    }


class Client:
    """Bounded client for Official HighLevel API v2 (services.leadconnectorhq.com)."""

    def __init__(
        self,
        token: str | None = None,
        location_id: str | None = None,
        profile: str | None = None,
    ):
        sub_cfg = load_subaccount_config(profile=profile) if (token is None or location_id is None) else {}
        raw_token = token if token is not None else sub_cfg.get("_resolved_token", "")
        raw_loc = location_id if location_id is not None else sub_cfg.get("location_id", "")
        self.token = _valid_token(raw_token)
        self.location_id = valid_id(raw_loc) if raw_loc else ""
        if not self.location_id:
            raise HighLevelError(
                "Set GHL_LOCATION_ID in the process environment or configure ~/.config/legends-gohighlevel/config.json."
            )
        self.auth_kind = "pit" if self.token.startswith("pit-") else "bearer"
        self.last_rate_limits: dict[str, int | str | None] = {}
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )

    def _allowed_path(self, path: str) -> bool:
        return any(pattern.fullmatch(path) for pattern in ALLOWED_PATHS)

    def _extract_rate_limits(self, headers) -> dict[str, int | str | None]:
        if not headers:
            return {}
        out: dict[str, int | str | None] = {}
        mapping = {
            "burst_limit": "x-ratelimit-max",
            "burst_remaining": "x-ratelimit-remaining",
            "burst_interval_ms": "x-ratelimit-interval-milliseconds",
            "daily_limit": "x-ratelimit-limit-daily",
            "daily_remaining": "x-ratelimit-daily-remaining",
        }
        for key, header_name in mapping.items():
            raw = headers.get(header_name)
            if raw is not None:
                try:
                    out[key] = int(raw)
                except ValueError:
                    out[key] = str(raw)
        return out

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
        version: str = API_VERSION,
    ) -> dict:
        if not self._allowed_path(path):
            raise HighLevelError("Unsupported HighLevel API path.")
        if method not in {"GET", "POST", "PUT", "DELETE"}:
            raise HighLevelError("Unsupported HTTP method.")
        if version not in {API_VERSION, API_VERSION_V3}:
            raise HighLevelError("Unsupported HighLevel API Version header.")
        if method in {"POST", "PUT", "DELETE"} and not (
            re.fullmatch(r"/locations/[A-Za-z0-9_-]{8,64}/customValues(?:/[A-Za-z0-9_-]{8,64})?", path)
            or re.fullmatch(r"/locations/[A-Za-z0-9_-]{8,64}/tags(?:/[A-Za-z0-9_-]{8,64})?", path)
            or re.fullmatch(r"/contacts/upsert", path)
            or re.fullmatch(r"/contacts/[A-Za-z0-9_-]{8,64}(?:/(?:tags|notes))?", path)
            or re.fullmatch(r"/opportunities/[A-Za-z0-9_-]{8,64}", path)
            or re.fullmatch(r"/objects/[A-Za-z0-9._-]{2,80}/records/search", path)
            or re.fullmatch(r"/workflows/search", path)
            or re.fullmatch(r"/workflows/definition/validate", path)
            or re.fullmatch(r"/workflows/[A-Za-z0-9_-]{8,64}/(?:status|definition)", path)
            or re.fullmatch(r"/social-media-posting/[A-Za-z0-9_-]{8,64}/posts/list", path)
            or re.fullmatch(r"/social-media-posting/[A-Za-z0-9_-]{8,64}/posts(?:/[A-Za-z0-9_-]{8,64})?", path)
        ):
            raise HighLevelError("Write method is restricted to reviewed single-resource CRM endpoints.")

        url = API_ROOT + path
        if query:
            clean_q = {k: v for k, v in query.items() if v is not None and v != ""}
            if clean_q:
                url += "?" + urllib.parse.urlencode(clean_q, doseq=True)

        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.token,
            "Version": version,
            "Accept": "application/json",
            "User-Agent": f"legends-gohighlevel/{__version__}",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=30) as response:
                self.last_rate_limits = self._extract_rate_limits(response.headers)
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise HighLevelError("HighLevel API response exceeded the size limit.")
            if not raw:
                return {}
            text_body = raw.decode("utf-8")
            if text_body.strip() == "OK":
                return {"ok": True, "message": "OK"}
            result = json.loads(text_body)
        except urllib.error.HTTPError as exc:
            self.last_rate_limits = self._extract_rate_limits(getattr(exc, "headers", None))
            err_hint = ""
            try:
                err_raw = exc.read(1024).decode("utf-8", errors="ignore")
                if "WORKFLOW_API_NOT_ENABLED_FOR_LOCATION" in err_raw:
                    err_hint = " (WORKFLOW_API_NOT_ENABLED_FOR_LOCATION: HighLevel Workflows API v3 beta is not enabled on this location yet)"
                elif "Calendar is inactive" in err_raw:
                    err_hint = " (Calendar is inactive in HighLevel Settings > Calendars)"
            except Exception:
                pass
            raise HighLevelError(
                f"HighLevel HTTP {exc.code}{err_hint}; inspect token scopes, location ID, or service status. "
                "No automatic retry. A failed write may have reached the service."
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise HighLevelError(
                "HighLevel connection failed. No automatic retry; inspect remote "
                "state before repeating a write."
            ) from None
        except (ValueError, UnicodeError):
            raise HighLevelError("Invalid HighLevel JSON response.") from None

        if not isinstance(result, dict):
            raise HighLevelError("Expected a JSON object from HighLevel API.")
        return result


class BackendClient:
    """Bounded client for HighLevel internal web-app backend (backend.leadconnectorhq.com)."""

    def __init__(
        self,
        token_id: str | None = None,
        company_id: str | None = None,
        worker_ssh: str | None = None,
        worker_container: str | None = None,
        worker_user_id: str | None = None,
    ):
        cfg = load_agency_config()
        raw_company = company_id if company_id is not None else cfg["company_id"]
        self.company_id = valid_id(raw_company) if raw_company else ""

        raw_tok = token_id if token_id is not None else os.environ.get("GHL_TOKEN_ID")
        if raw_tok:
            self.token_id = _valid_token(raw_tok, env_hint="GHL_TOKEN_ID")
            self.token_source = "env:GHL_TOKEN_ID"
            self.token_exp = None
            self.worker_user_id = worker_user_id or cfg["worker_user_id"] or None
        else:
            ssh_target = worker_ssh if worker_ssh is not None else cfg["worker_ssh"]
            container = worker_container if worker_container is not None else cfg["worker_container"]
            user_id = worker_user_id if worker_user_id is not None else cfg["worker_user_id"]
            if not ssh_target:
                raise HighLevelError(
                    "Set GHL_TOKEN_ID in the environment or configure worker_ssh in "
                    "~/.config/legends-gohighlevel/agency.json."
                )
            extracted = extract_worker_token_via_ssh(
                worker_ssh=ssh_target,
                worker_container=container,
                worker_user_id=user_id,
            )
            self.token_id = extracted["token"]
            self.token_source = extracted["source"]
            self.token_exp = extracted.get("exp")
            self.worker_user_id = extracted.get("user_id") or user_id or None

        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )

    def _allowed_path(self, path: str) -> bool:
        return any(pattern.fullmatch(path) for pattern in ALLOWED_BACKEND_PATHS)

    def _allowed_write_path(self, path: str) -> bool:
        return any(pattern.fullmatch(path) for pattern in ALLOWED_BACKEND_WRITE_PATHS)

    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
    ) -> dict:
        if not self._allowed_path(path):
            raise HighLevelError(f"Unsupported HighLevel backend path: {path}")
        if method not in {"GET", "POST", "PUT", "DELETE"}:
            raise HighLevelError("Unsupported HTTP method for internal backend.")
        if method in {"POST", "PUT", "DELETE"} and not self._allowed_write_path(path):
            raise HighLevelError("Write method is restricted to reviewed agency/dashboard governance endpoints.")

        url = BACKEND_ROOT + path
        if query:
            clean_q = {k: v for k, v in query.items() if v is not None and v != ""}
            if clean_q:
                url += "?" + urllib.parse.urlencode(clean_q, doseq=True)

        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "token-id": self.token_id,
            "Version": API_VERSION,
            "channel": "APP",
            "source": "WEB_USER",
            "Accept": "application/json",
            "User-Agent": f"legends-gohighlevel/{__version__}",
        }
        if path.startswith("/internal-tools/"):
            headers["authorization"] = f"Bearer {self.token_id}"
            headers["source-id"] = "platform-billing"
        if data is not None:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise HighLevelError("HighLevel backend response exceeded the size limit.")
            if not raw:
                return {}
            text_body = raw.decode("utf-8")
            if text_body.strip() == "OK":
                return {"ok": True, "message": "OK"}
            result = json.loads(text_body)
        except urllib.error.HTTPError as exc:
            raise HighLevelError(
                f"HighLevel backend HTTP {exc.code} on {method} {path}; inspect worker token-id, "
                "companyId, or payload schema. No automatic retry."
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise HighLevelError(
                "HighLevel backend connection failed. No automatic retry; inspect remote "
                "state before repeating a write."
            ) from None
        except (ValueError, UnicodeError):
            raise HighLevelError("Invalid HighLevel backend JSON response.") from None

        if not isinstance(result, (dict, list)):
            raise HighLevelError("Expected a JSON object or array from HighLevel backend.")
        return result
