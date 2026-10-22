"""Bounded GoHighLevel API v2 transport. No arbitrary URLs, redirects, or write retries."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

API_ROOT = "https://services.leadconnectorhq.com"
API_VERSION = "2021-07-28"
ID_RE = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
ALLOWED_PATHS = (
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/customValues(?:/[A-Za-z0-9_-]{8,64})?\Z"),
    re.compile(r"/locations/[A-Za-z0-9_-]{8,64}/customFields\Z"),
    re.compile(r"/contacts/\Z"),
    re.compile(r"/contacts/upsert\Z"),
    re.compile(r"/contacts/[A-Za-z0-9_-]{8,64}(?:/(?:tags|notes))?\Z"),
    re.compile(r"/opportunities/pipelines\Z"),
    re.compile(r"/opportunities/search\Z"),
    re.compile(r"/opportunities/\Z"),
    re.compile(r"/opportunities/[A-Za-z0-9_-]{8,64}\Z"),
    re.compile(r"/calendars/\Z"),
    re.compile(r"/calendars/[A-Za-z0-9_-]{8,64}/free-slots\Z"),
    re.compile(r"/conversations/search\Z"),
    re.compile(r"/workflows/\Z"),
    re.compile(r"/forms/\Z"),
    re.compile(r"/surveys/\Z"),
)
MAX_RESPONSE = 16 * 1024 * 1024


class HighLevelError(Exception):
    """Actionable error safe to display without leaking tokens or raw provider bodies."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HighLevelError("Redirect refused; credentials were not forwarded.")


def valid_id(value: str | None) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value.strip()):
        raise HighLevelError("Expected a valid HighLevel resource identifier.")
    return value.strip()


def _valid_token(value: str | None) -> str:
    if not value or value != value.strip() or len(value) < 12 or any(
        ord(c) < 33 or ord(c) > 126 for c in value
    ):
        raise HighLevelError(
            "Set GHL_PIT (or GHL_ACCESS_TOKEN) through your secret manager in the process environment."
        )
    return value


class Client:
    """Bounded client for Official HighLevel API v2 (services.leadconnectorhq.com)."""

    def __init__(self, token: str | None = None, location_id: str | None = None):
        raw_token = token if token is not None else (
            os.environ.get("GHL_PIT") or os.environ.get("GHL_ACCESS_TOKEN")
        )
        raw_loc = location_id if location_id is not None else os.environ.get("GHL_LOCATION_ID")
        self.token = _valid_token(raw_token)
        self.location_id = valid_id(raw_loc) if raw_loc else ""
        if not self.location_id:
            raise HighLevelError(
                "Set GHL_LOCATION_ID in the process environment for sub-account API operations."
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
    ) -> dict:
        if not self._allowed_path(path):
            raise HighLevelError("Unsupported HighLevel API path.")
        if method not in {"GET", "POST", "PUT", "DELETE"}:
            raise HighLevelError("Unsupported HTTP method.")
        if method in {"POST", "PUT", "DELETE"} and not (
            re.fullmatch(r"/locations/[A-Za-z0-9_-]{8,64}/customValues(?:/[A-Za-z0-9_-]{8,64})?", path)
            or re.fullmatch(r"/contacts/upsert", path)
            or re.fullmatch(r"/contacts/[A-Za-z0-9_-]{8,64}(?:/(?:tags|notes))?", path)
            or re.fullmatch(r"/opportunities/[A-Za-z0-9_-]{8,64}", path)
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
            "Version": API_VERSION,
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
            result = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.last_rate_limits = self._extract_rate_limits(getattr(exc, "headers", None))
            raise HighLevelError(
                f"HighLevel HTTP {exc.code}; inspect token scopes, location ID, or service status. "
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
