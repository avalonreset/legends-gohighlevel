"""GoHighLevel Social Planner operations and Enterprise GHL-to-X Official API Bridge."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .api import Client, HighLevelError, MAX_CONFIG_BYTES, NoRedirect, _reject_symlink_chain, scrub_secrets, valid_id

X_API_V2_ROOT = "https://api.twitter.com/2"
X_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
ALLOWED_MEDIA_HOSTS = {"assets.cdn.filesafe.space", "storage.googleapis.com"}
MAX_MEDIA_BYTES = 512 * 1024 * 1024
DEFAULT_CUTOFF_ISO = "2026-10-27T00:00:00Z"


def _pct_encode(value: str) -> str:
    return urllib.parse.quote(str(value), safe="-._~")


def build_oauth1_header(
    *,
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    body_params: dict[str, str] | None = None,
    nonce: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Build an RFC 5849 OAuth 1.0a Authorization header using HMAC-SHA1 (pure stdlib)."""
    parsed = urllib.parse.urlsplit(url)
    base_url = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)

    oauth_params: dict[str, str] = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    sig_pairs: list[tuple[str, str]] = []
    for k, v in query_pairs:
        sig_pairs.append((_pct_encode(k), _pct_encode(v)))
    for k, v in oauth_params.items():
        sig_pairs.append((_pct_encode(k), _pct_encode(v)))
    if body_params:
        for k, v in body_params.items():
            sig_pairs.append((_pct_encode(k), _pct_encode(v)))

    sig_pairs.sort(key=lambda item: (item[0], item[1]))
    normalized_params = "&".join(f"{k}={v}" for k, v in sig_pairs)
    base_string = "&".join(
        [
            _pct_encode(method.upper()),
            _pct_encode(base_url),
            _pct_encode(normalized_params),
        ]
    )
    signing_key = f"{_pct_encode(consumer_secret)}&{_pct_encode(access_token_secret)}"
    digest = hmac.new(
        signing_key.encode("ascii"),
        base_string.encode("ascii"),
        hashlib.sha1,
    ).digest()
    oauth_params["oauth_signature"] = base64.b64encode(digest).decode("ascii")

    header_parts = [
        f'{_pct_encode(k)}="{_pct_encode(oauth_params[k])}"'
        for k in sorted(oauth_params.keys())
    ]
    return "OAuth " + ", ".join(header_parts)


def load_env_file(env_path: Path | None = None) -> dict[str, str]:
    """Load key=value pairs from process environment plus an optional explicit env file (or GHL_ENV_FILE)."""
    merged: dict[str, str] = {}
    env_file_override = os.environ.get("GHL_ENV_FILE")
    candidate_file = env_path or (
        Path(env_file_override).expanduser() if env_file_override else None
    )
    if candidate_file:
        _reject_symlink_chain(candidate_file)
    if candidate_file and candidate_file.is_file():
        try:
            if candidate_file.stat().st_size > MAX_CONFIG_BYTES:
                raise HighLevelError("Environment file exceeds 1 MB size limit.")
            for raw_line in candidate_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                merged[k.strip()] = v
        except HighLevelError:
            raise
        except OSError:
            pass
    for k, v in os.environ.items():
        if v:
            merged[k] = v
    return merged


load_empire_env = load_env_file


class XOfficialClient:
    """Bounded Official X API v2 + v1.1 chunked media upload client using OAuth 1.0a."""

    def __init__(
        self,
        *,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
        env_path: Path | None = None,
    ):
        env = load_env_file(env_path)
        self.consumer_key = (
            consumer_key
            or env.get("X_API_KEY")
            or env.get("X_CONSUMER_KEY")
            or env.get("X_AVALON_CONSUMER_KEY")
            or ""
        ).strip()
        self.consumer_secret = (
            consumer_secret
            or env.get("X_API_SECRET")
            or env.get("X_CONSUMER_SECRET")
            or env.get("X_AVALON_CONSUMER_SECRET")
            or ""
        ).strip()
        self.access_token = (
            access_token
            or env.get("X_ACCESS_TOKEN")
            or env.get("X_AVALON_ACCESS_TOKEN")
            or ""
        ).strip()
        self.access_token_secret = (
            access_token_secret
            or env.get("X_ACCESS_TOKEN_SECRET")
            or env.get("X_AVALON_ACCESS_TOKEN_SECRET")
            or ""
        ).strip()
        if not (
            self.consumer_key
            and self.consumer_secret
            and self.access_token
            and self.access_token_secret
        ):
            raise HighLevelError(
                "Missing X Official API OAuth 1.0a credentials (set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, and X_ACCESS_TOKEN_SECRET in the environment)."
            )
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )

    def _auth_header(
        self,
        method: str,
        url: str,
        body_params: dict[str, str] | None = None,
    ) -> str:
        return build_oauth1_header(
            method=method,
            url=url,
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
            body_params=body_params,
        )

    def verify_user(self) -> dict[str, Any]:
        url = f"{X_API_V2_ROOT}/users/me?user.fields=username,name,verified,verified_type"
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": self._auth_header("GET", url),
                "Accept": "application/json",
                "User-Agent": "legends-gohighlevel-x-bridge/1.0",
            },
        )
        try:
            with self.opener.open(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise HighLevelError(f"X API /2/users/me failed with HTTP {exc.code}.") from None
        except (OSError, ValueError) as exc:
            raise HighLevelError(f"X API /2/users/me transport error: {exc}") from None

        user = data.get("data") or {}
        return {
            "id": str(user.get("id") or ""),
            "username": str(user.get("username") or ""),
            "name": str(user.get("name") or ""),
            "verified": bool(user.get("verified")),
            "verified_type": str(user.get("verified_type") or "none"),
        }

    def check_media_status(self, media_id: str) -> dict[str, Any]:
        clean_id = str(media_id).strip()
        if not clean_id.isdigit():
            raise HighLevelError("Invalid X media_id.")
        url = f"{X_UPLOAD_URL}?command=STATUS&media_id={clean_id}"
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": self._auth_header("GET", url),
                "Accept": "application/json",
                "User-Agent": "legends-gohighlevel-x-bridge/1.0",
            },
        )
        try:
            with self.opener.open(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise HighLevelError(f"X media STATUS check failed with HTTP {exc.code}.") from None
        except (OSError, ValueError) as exc:
            raise HighLevelError(f"X media STATUS transport error: {exc}") from None

    def upload_video_chunked(
        self,
        video_path: Path,
        *,
        chunk_size: int = 4 * 1024 * 1024,
        media_category: str = "tweet_video",
        max_poll_seconds: int = 300,
    ) -> dict[str, Any]:
        if not video_path.is_file():
            raise HighLevelError(f"Video file not found: {video_path}")
        total_bytes = video_path.stat().st_size
        if total_bytes <= 0:
            raise HighLevelError("Video file is empty.")

        # 1. INIT
        init_params = {
            "command": "INIT",
            "total_bytes": str(total_bytes),
            "media_type": "video/mp4",
            "media_category": media_category,
        }
        init_body = urllib.parse.urlencode(init_params).encode("utf-8")
        req_init = urllib.request.Request(
            X_UPLOAD_URL,
            data=init_body,
            method="POST",
            headers={
                "Authorization": self._auth_header("POST", X_UPLOAD_URL, body_params=init_params),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "legends-gohighlevel-x-bridge/1.0",
            },
        )
        try:
            with self.opener.open(req_init, timeout=30) as resp:
                init_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise HighLevelError(f"X media INIT failed with HTTP {exc.code}.") from None

        media_id = str(init_data.get("media_id_string") or init_data.get("media_id") or "")
        if not media_id:
            raise HighLevelError("X media INIT did not return a media_id.")

        # 2. APPEND chunks (multipart/form-data is not included in OAuth1 signature base string per RFC 5849)
        sha = hashlib.sha256()
        segment_index = 0
        with video_path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                sha.update(chunk)
                boundary = f"----LegendsXUpload{uuid.uuid4().hex}"
                parts = [
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"command\"\r\n\r\nAPPEND\r\n".encode("utf-8"),
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"media_id\"\r\n\r\n{media_id}\r\n".encode("utf-8"),
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"segment_index\"\r\n\r\n{segment_index}\r\n".encode("utf-8"),
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"media\"; filename=\"chunk.mp4\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode("utf-8"),
                    chunk,
                    f"\r\n--{boundary}--\r\n".encode("utf-8"),
                ]
                multipart_body = b"".join(parts)
                req_app = urllib.request.Request(
                    X_UPLOAD_URL,
                    data=multipart_body,
                    method="POST",
                    headers={
                        "Authorization": self._auth_header("POST", X_UPLOAD_URL),
                        "Content-Type": f"multipart/form-data; boundary={boundary}",
                        "User-Agent": "legends-gohighlevel-x-bridge/1.0",
                    },
                )
                try:
                    with self.opener.open(req_app, timeout=90) as resp:
                        _ = resp.read()
                except urllib.error.HTTPError as exc:
                    raise HighLevelError(
                        f"X media APPEND failed on segment {segment_index} with HTTP {exc.code}."
                    ) from None
                segment_index += 1

        # 3. FINALIZE
        fin_params = {"command": "FINALIZE", "media_id": media_id}
        fin_body = urllib.parse.urlencode(fin_params).encode("utf-8")
        req_fin = urllib.request.Request(
            X_UPLOAD_URL,
            data=fin_body,
            method="POST",
            headers={
                "Authorization": self._auth_header("POST", X_UPLOAD_URL, body_params=fin_params),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "User-Agent": "legends-gohighlevel-x-bridge/1.0",
            },
        )
        try:
            with self.opener.open(req_fin, timeout=30) as resp:
                fin_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise HighLevelError(f"X media FINALIZE failed with HTTP {exc.code}.") from None

        # 4. STATUS polling
        proc = fin_data.get("processing_info")
        started = time.time()
        while proc and proc.get("state") in ("pending", "in_progress"):
            if time.time() - started > max_poll_seconds:
                raise HighLevelError("X media processing timed out.")
            wait_s = min(max(int(proc.get("check_after_secs", 2)), 1), 10)
            time.sleep(wait_s)
            stat_data = self.check_media_status(media_id)
            proc = stat_data.get("processing_info")
            if proc and proc.get("state") == "failed":
                err_msg = (proc.get("error") or {}).get("message") or "unknown processing error"
                raise HighLevelError(f"X media processing failed: {err_msg}")

        return {
            "media_id": media_id,
            "size_bytes": total_bytes,
            "sha256": sha.hexdigest(),
            "segments": segment_index,
            "processing_state": (proc or {}).get("state", "succeeded"),
        }

    def create_tweet(self, text: str, media_id: str | None = None, username: str = "i") -> dict[str, Any]:
        clean_text = str(text or "").strip()
        if not clean_text:
            raise HighLevelError("Tweet text cannot be empty.")
        url = f"{X_API_V2_ROOT}/tweets"
        payload: dict[str, Any] = {"text": clean_text}
        if media_id:
            payload["media"] = {"media_ids": [str(media_id).strip()]}
        raw_body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=raw_body,
            method="POST",
            headers={
                "Authorization": self._auth_header("POST", url),
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "legends-gohighlevel-x-bridge/1.0",
            },
        )
        try:
            with self.opener.open(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read(500).decode("utf-8", errors="ignore")
            except Exception:
                pass
            raise HighLevelError(f"X API /2/tweets failed with HTTP {exc.code}: {err_body[:200]}") from None

        tweet_data = data.get("data") or {}
        tweet_id = str(tweet_data.get("id") or "")
        if not tweet_id:
            raise HighLevelError("X API /2/tweets did not return a tweet ID.")
        return {
            "tweet_id": tweet_id,
            "text": str(tweet_data.get("text") or clean_text),
            "url": f"https://x.com/{username}/status/{tweet_id}",
        }


def list_social_accounts(client: Client) -> dict[str, Any]:
    loc_id = valid_id(client.location_id)
    res = client.request("GET", f"/social-media-posting/{loc_id}/accounts")
    accounts = (res.get("results") or {}).get("accounts") or []
    rows = []
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        rows.append(
            {
                "id": acc.get("id"),
                "name": acc.get("name"),
                "platform": acc.get("platform"),
                "type": acc.get("type"),
                "origin_id": acc.get("originId"),
                "active": bool(acc.get("active", True)),
                "is_expired": bool(acc.get("isExpired", False)),
            }
        )
    return {
        "location_id": loc_id,
        "count": len(rows),
        "accounts": rows,
    }


def list_social_posts(client: Client, limit: int = 25) -> dict[str, Any]:
    loc_id = valid_id(client.location_id)
    bounded = max(1, min(int(limit), 100))
    res = client.request(
        "POST",
        f"/social-media-posting/{loc_id}/posts/list",
        body={"limit": str(bounded), "skip": "0", "includeUsers": "true"},
    )
    posts = (res.get("results") or {}).get("posts") or []
    rows = []
    for p in posts:
        if not isinstance(p, dict):
            continue
        media_list = p.get("media") or []
        first_media = media_list[0] if media_list and isinstance(media_list[0], dict) else {}
        rows.append(
            {
                "id": p.get("_id") or p.get("postId"),
                "parent_post_id": p.get("parentPostId"),
                "platform": p.get("platform"),
                "status": p.get("status"),
                "source": p.get("source"),
                "summary": p.get("summary"),
                "display_date": p.get("displayDate"),
                "schedule_date": p.get("scheduleDate"),
                "published_at": p.get("publishedAt"),
                "preview_link": p.get("previewLink"),
                "account_id": p.get("accountId"),
                "account_ids": p.get("accountIds") or [],
                "media_url": first_media.get("url"),
                "media_type": first_media.get("type"),
            }
        )
    return {
        "location_id": loc_id,
        "count": len(rows),
        "posts": rows,
    }


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    clean = ts.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def is_widescreen_candidate(post: dict[str, Any], cutoff_dt: datetime) -> bool:
    """Return True if a GHL Social Planner post is a 16:9 widescreen video post eligible for X mirroring."""
    media_url = str(post.get("media_url") or "")
    if not media_url.lower().endswith(".mp4"):
        return False
    parsed = urllib.parse.urlsplit(media_url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in ALLOWED_MEDIA_HOSTS:
        return False

    # Check timestamp against cutoff
    post_dt = (
        _parse_iso(post.get("display_date"))
        or _parse_iso(post.get("schedule_date"))
        or _parse_iso(post.get("published_at"))
    )
    if post_dt is None or post_dt < cutoff_dt:
        return False

    # Widescreen posts in HighLevel Social Planner target LinkedIn or YouTube (whereas Instagram/TikTok are 9:16)
    platform = str(post.get("platform") or "").lower()
    if platform in {"linkedin", "youtube"}:
        return True
    account_ids = [str(a) for a in (post.get("account_ids") or [])]
    if any("_page" in a or "_profile" in a for a in account_ids) and not any(
        "_business" in a for a in account_ids
    ):
        return True
    return False


class GhlXBridge:
    """Enterprise-grade SQLite-backed bridge syncing GoHighLevel 16:9 Social Planner posts to Official X API."""

    def __init__(self, state_dir: Path | None = None):
        env_state = os.environ.get("GHL_X_BRIDGE_STATE_DIR")
        default_state = (
            Path(env_state).expanduser().resolve()
            if env_state
            else (Path.home() / ".config" / "legends-gohighlevel" / "x-bridge")
        )
        self.state_dir = state_dir or default_state
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.state_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "bridge.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS x_bridge_jobs (
                    dedupe_key TEXT PRIMARY KEY,
                    location_id TEXT NOT NULL,
                    ghl_post_ids_json TEXT NOT NULL,
                    caption TEXT NOT NULL,
                    media_url TEXT NOT NULL,
                    schedule_date TEXT NOT NULL,
                    ghl_status TEXT NOT NULL,
                    x_status TEXT NOT NULL,
                    x_media_id TEXT,
                    x_tweet_id TEXT,
                    x_tweet_url TEXT,
                    media_sha256 TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    published_at TEXT
                )
                """
            )
            conn.commit()

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM x_bridge_jobs ORDER BY schedule_date DESC, updated_at DESC"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["ghl_post_ids"] = json.loads(d.pop("ghl_post_ids_json", "[]"))
            except ValueError:
                d["ghl_post_ids"] = []
            out.append(d)
        return out

    def download_media(self, media_url: str) -> Path:
        parsed = urllib.parse.urlsplit(media_url)
        if parsed.scheme != "https" or parsed.netloc.lower() not in ALLOWED_MEDIA_HOSTS:
            raise HighLevelError(f"Refusing to download media from untrusted host: {parsed.netloc}")
        url_hash = hashlib.sha256(media_url.encode("utf-8")).hexdigest()[:16]
        target = self.cache_dir / f"ghl-{url_hash}.mp4"
        if target.is_file() and target.stat().st_size > 0:
            return target

        req = urllib.request.Request(
            media_url,
            method="GET",
            headers={"User-Agent": "legends-gohighlevel-x-bridge/1.0"},
        )
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        tmp_target = self.cache_dir / f"ghl-{url_hash}.mp4.part"
        try:
            total_bytes = 0
            with opener.open(req, timeout=120) as resp, tmp_target.open("wb") as out_f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_MEDIA_BYTES:
                        raise HighLevelError("GHL media download exceeded 512 MB size limit.")
                    out_f.write(chunk)
            tmp_target.replace(target)
        except Exception as exc:
            if tmp_target.exists():
                try:
                    tmp_target.unlink()
                except OSError:
                    pass
            raise HighLevelError(f"Failed to download GHL media URL: {scrub_secrets(str(exc))}") from None
        return target

    def sync(
        self,
        ghl_client: Client,
        x_client: XOfficialClient | None = None,
        *,
        apply: bool = False,
        cutoff_iso: str = DEFAULT_CUTOFF_ISO,
        reuse_media_id: str | None = None,
        local_media_override: Path | None = None,
    ) -> dict[str, Any]:
        cutoff_dt = _parse_iso(cutoff_iso) or datetime(2026, 10, 27, tzinfo=timezone.utc)
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        ghl_snapshot = list_social_posts(ghl_client, limit=50)
        loc_id = ghl_snapshot["location_id"]

        # Group 16:9 widescreen candidates by media_url so LinkedIn Profile + Page pair maps to 1 X tweet
        grouped: dict[str, dict[str, Any]] = {}
        for post in ghl_snapshot["posts"]:
            if not is_widescreen_candidate(post, cutoff_dt):
                continue
            media_url = str(post["media_url"])
            dedupe_key = hashlib.sha256(f"{loc_id}:{media_url}".encode("utf-8")).hexdigest()[:24]
            entry = grouped.get(dedupe_key)
            sched = str(post.get("schedule_date") or post.get("display_date") or now_iso)
            status = str(post.get("status") or "scheduled")
            caption = str(post.get("summary") or "").strip()
            pid = str(post.get("id") or "")
            if entry is None:
                grouped[dedupe_key] = {
                    "dedupe_key": dedupe_key,
                    "location_id": loc_id,
                    "ghl_post_ids": [pid] if pid else [],
                    "caption": caption,
                    "media_url": media_url,
                    "schedule_date": sched,
                    "ghl_status": status,
                }
            else:
                if pid and pid not in entry["ghl_post_ids"]:
                    entry["ghl_post_ids"].append(pid)
                if status == "published":
                    entry["ghl_status"] = "published"
                if caption:
                    entry["caption"] = caption

        actions: list[dict[str, Any]] = []
        writes_sent = 0

        with self._connect() as conn:
            existing_rows = {
                r["dedupe_key"]: dict(r)
                for r in conn.execute("SELECT * FROM x_bridge_jobs WHERE location_id = ?", (loc_id,)).fetchall()
            }

            # Mark scheduled jobs whose GHL posts were deleted before publication as cancelled
            for dkey, row in existing_rows.items():
                if dkey not in grouped and row["x_status"] == "scheduled":
                    actions.append(
                        {
                            "dedupe_key": dkey,
                            "action": "cancel_deleted_ghl_post",
                            "caption": row["caption"],
                        }
                    )
                    if apply:
                        conn.execute(
                            "UPDATE x_bridge_jobs SET x_status = 'cancelled', updated_at = ? WHERE dedupe_key = ?",
                            (now_iso, dkey),
                        )
                        conn.commit()

            # Process active GHL widescreen groups
            for dkey, item in grouped.items():
                row = existing_rows.get(dkey)
                sched_dt = _parse_iso(item["schedule_date"]) or now_dt
                due_now = item["ghl_status"] == "published" or sched_dt <= now_dt

                if row and row["x_status"] == "published":
                    actions.append(
                        {
                            "dedupe_key": dkey,
                            "action": "already_published",
                            "caption": item["caption"],
                            "x_tweet_url": row["x_tweet_url"],
                            "x_tweet_id": row["x_tweet_id"],
                        }
                    )
                    continue

                if not due_now:
                    # Future scheduled post in GHL: record or update schedule in SQLite ledger
                    action_name = "update_scheduled" if row else "track_scheduled"
                    actions.append(
                        {
                            "dedupe_key": dkey,
                            "action": action_name,
                            "caption": item["caption"],
                            "schedule_date": item["schedule_date"],
                            "ghl_post_ids": item["ghl_post_ids"],
                        }
                    )
                    if apply:
                        conn.execute(
                            """
                            INSERT INTO x_bridge_jobs (
                                dedupe_key, location_id, ghl_post_ids_json, caption, media_url,
                                schedule_date, ghl_status, x_status, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?)
                            ON CONFLICT(dedupe_key) DO UPDATE SET
                                ghl_post_ids_json = excluded.ghl_post_ids_json,
                                caption = excluded.caption,
                                schedule_date = excluded.schedule_date,
                                ghl_status = excluded.ghl_status,
                                x_status = 'scheduled',
                                updated_at = excluded.updated_at
                            """,
                            (
                                dkey,
                                loc_id,
                                json.dumps(item["ghl_post_ids"]),
                                item["caption"],
                                item["media_url"],
                                item["schedule_date"],
                                item["ghl_status"],
                                now_iso,
                                now_iso,
                            ),
                        )
                        conn.commit()
                    continue

                # Due now!
                if not apply:
                    actions.append(
                        {
                            "dedupe_key": dkey,
                            "action": "publish_to_x_preview",
                            "caption": item["caption"],
                            "media_url": item["media_url"],
                            "schedule_date": item["schedule_date"],
                            "ghl_status": item["ghl_status"],
                            "ghl_post_ids": item["ghl_post_ids"],
                        }
                    )
                    continue

                if x_client is None:
                    x_client = XOfficialClient()

                # Claim job in SQLite before network upload/tweet
                conn.execute(
                    """
                    INSERT INTO x_bridge_jobs (
                        dedupe_key, location_id, ghl_post_ids_json, caption, media_url,
                        schedule_date, ghl_status, x_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'publishing', ?, ?)
                    ON CONFLICT(dedupe_key) DO UPDATE SET
                        ghl_post_ids_json = excluded.ghl_post_ids_json,
                        caption = excluded.caption,
                        schedule_date = excluded.schedule_date,
                        ghl_status = excluded.ghl_status,
                        x_status = 'publishing',
                        updated_at = excluded.updated_at
                    """,
                    (
                        dkey,
                        loc_id,
                        json.dumps(item["ghl_post_ids"]),
                        item["caption"],
                        item["media_url"],
                        item["schedule_date"],
                        item["ghl_status"],
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()

                try:
                    user_info = x_client.verify_user()
                    username = user_info.get("username") or "i"

                    if local_media_override and local_media_override.is_file():
                        local_video = local_media_override
                    else:
                        local_video = self.download_media(item["media_url"])

                    media_sha256 = hashlib.sha256(local_video.read_bytes()).hexdigest()

                    candidate_media_id = reuse_media_id or (row.get("x_media_id") if row else None)
                    media_id = ""
                    if candidate_media_id:
                        try:
                            stat = x_client.check_media_status(str(candidate_media_id))
                            proc_state = (stat.get("processing_info") or {}).get("state", "succeeded")
                            if proc_state == "succeeded":
                                media_id = str(candidate_media_id)
                        except HighLevelError:
                            media_id = ""

                    if not media_id:
                        up_res = x_client.upload_video_chunked(local_video)
                        media_id = up_res["media_id"]

                    # Persist staged x_media_id immediately so any downstream tweet error never re-uploads 138 MB within 24h
                    conn.execute(
                        """
                        UPDATE x_bridge_jobs
                        SET x_media_id = ?,
                            media_sha256 = ?,
                            updated_at = ?
                        WHERE dedupe_key = ?
                        """,
                        (media_id, media_sha256, datetime.now(timezone.utc).isoformat(), dkey),
                    )
                    conn.commit()

                    tweet_res = x_client.create_tweet(
                        item["caption"],
                        media_id=media_id,
                        username=username,
                    )
                    writes_sent += 1
                    pub_iso = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        """
                        UPDATE x_bridge_jobs
                        SET x_status = 'published',
                            x_media_id = ?,
                            x_tweet_id = ?,
                            x_tweet_url = ?,
                            media_sha256 = ?,
                            last_error = NULL,
                            updated_at = ?,
                            published_at = ?
                        WHERE dedupe_key = ?
                        """,
                        (
                            media_id,
                            tweet_res["tweet_id"],
                            tweet_res["url"],
                            media_sha256,
                            pub_iso,
                            pub_iso,
                            dkey,
                        ),
                    )
                    conn.commit()
                    actions.append(
                        {
                            "dedupe_key": dkey,
                            "action": "published_to_x",
                            "caption": item["caption"],
                            "x_media_id": media_id,
                            "x_tweet_id": tweet_res["tweet_id"],
                            "x_tweet_url": tweet_res["url"],
                            "media_sha256": media_sha256,
                            "published_at": pub_iso,
                        }
                    )
                except Exception as exc:
                    err_iso = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        """
                        UPDATE x_bridge_jobs
                        SET x_status = 'error',
                            last_error = ?,
                            updated_at = ?
                        WHERE dedupe_key = ?
                        """,
                        (str(exc), err_iso, dkey),
                    )
                    conn.commit()
                    raise

        result = {
            "mode": "apply" if apply else "preview",
            "location_id": loc_id,
            "cutoff_iso": cutoff_iso,
            "writes_sent": writes_sent,
            "actions": actions,
            "jobs": self.list_jobs(),
        }
        if apply:
            status_file = self.state_dir / "latest-status.json"
            status_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
