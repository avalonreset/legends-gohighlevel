"""Unit tests for GoHighLevel Social Planner and Official X API Bridge."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
from typing import Any
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legends_gohighlevel.social import (
    GhlXBridge,
    build_oauth1_header,
    is_widescreen_candidate,
)


class _FakeGhlClient:
    def __init__(self, posts: list[dict[str, Any]], location_id: str = "loc_test_12345678") -> None:
        self.location_id = location_id
        self._posts = posts

    def request(self, method: str, path: str, body: dict | None = None, query: dict | None = None) -> dict:
        assert method == "POST"
        assert path.endswith("/posts/list")
        return {"results": {"posts": self._posts}}


class _FakeXClient:
    def __init__(self) -> None:
        self.uploads = 0
        self.tweets: list[dict[str, Any]] = []

    def verify_user(self) -> dict[str, Any]:
        return {"id": "1000000000000000001", "username": "ExampleBrand", "name": "Example Brand"}

    def check_media_status(self, media_id: str) -> dict[str, Any]:
        return {"media_id_string": media_id, "processing_info": {"state": "succeeded"}}

    def upload_video_chunked(self, video_path: Path, **kwargs: Any) -> dict[str, Any]:
        self.uploads += 1
        return {
            "media_id": "2000000000000000001",
            "size_bytes": video_path.stat().st_size,
            "sha256": "deadbeef",
            "segments": 1,
            "processing_state": "succeeded",
        }

    def create_tweet(self, text: str, media_id: str | None = None, username: str = "i") -> dict[str, Any]:
        tid = f"tweet_{len(self.tweets) + 1}"
        rec = {"tweet_id": tid, "text": text, "media_id": media_id, "url": f"https://x.com/{username}/status/{tid}"}
        self.tweets.append(rec)
        return rec


class SocialXBridgeTests(unittest.TestCase):
    def test_build_oauth1_header_deterministic(self) -> None:
        hdr = build_oauth1_header(
            method="POST",
            url="https://upload.twitter.com/1.1/media/upload.json",
            consumer_key="ckey123",
            consumer_secret="csec456",
            access_token="atok789",
            access_token_secret="asec012",
            body_params={"command": "INIT", "total_bytes": "1000"},
            nonce="fixednonce123",
            timestamp="1700000000",
        )
        self.assertTrue(hdr.startswith("OAuth "))
        self.assertIn('oauth_consumer_key="ckey123"', hdr)
        self.assertIn('oauth_token="atok789"', hdr)
        self.assertIn('oauth_signature_method="HMAC-SHA1"', hdr)
        self.assertIn('oauth_signature="', hdr)

    def test_is_widescreen_candidate_filters_aspect_and_cutoff(self) -> None:
        cutoff = datetime(2026, 10, 27, 0, 0, tzinfo=timezone.utc)
        li_post = {
            "platform": "linkedin",
            "media_url": "https://assets.cdn.filesafe.space/loc_test_12345678/media/wide.mp4",
            "display_date": "2026-10-27T21:24:00.000Z",
        }
        ig_post = {
            "platform": "instagram",
            "media_url": "https://assets.cdn.filesafe.space/loc_test_12345678/media/vert.mp4",
            "display_date": "2026-10-27T21:25:00.000Z",
        }
        old_post = {
            "platform": "linkedin",
            "media_url": "https://assets.cdn.filesafe.space/loc_test_12345678/media/old.mp4",
            "display_date": "2026-09-19T16:17:00.000Z",
        }
        self.assertTrue(is_widescreen_candidate(li_post, cutoff))
        self.assertFalse(is_widescreen_candidate(ig_post, cutoff))
        self.assertFalse(is_widescreen_candidate(old_post, cutoff))

    def test_ghl_x_bridge_deduplicates_linkedin_pair_and_publishes_once(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
            tmp_path = Path(raw_tmp)
            dummy_mp4 = tmp_path / "dummy.mp4"
            dummy_mp4.write_bytes(b"0000ftypisom" * 100)

            posts = [
                {
                    "_id": "li_page_1",
                    "platform": "linkedin",
                    "status": "published",
                    "summary": "what do I actually sell to clients? (business intelligence)",
                    "displayDate": "2026-10-27T21:24:40.709Z",
                    "scheduleDate": "2026-10-27T21:23:00.000Z",
                    "media": [{"url": "https://assets.cdn.filesafe.space/loc_test_12345678/media/wide16x9.mp4", "type": "video/mp4"}],
                },
                {
                    "_id": "li_prof_1",
                    "platform": "linkedin",
                    "status": "published",
                    "summary": "what do I actually sell to clients? (business intelligence)",
                    "displayDate": "2026-10-27T21:24:39.824Z",
                    "scheduleDate": "2026-10-27T21:23:00.000Z",
                    "media": [{"url": "https://assets.cdn.filesafe.space/loc_test_12345678/media/wide16x9.mp4", "type": "video/mp4"}],
                },
                {
                    "_id": "ig_vert_1",
                    "platform": "instagram",
                    "status": "published",
                    "summary": "what do I actually sell to clients? (business intelligence)",
                    "displayDate": "2026-10-27T21:27:46.291Z",
                    "scheduleDate": "2026-10-27T21:25:00.000Z",
                    "media": [{"url": "https://assets.cdn.filesafe.space/loc_test_12345678/media/vert9x16.mp4", "type": "video/mp4"}],
                },
            ]

            ghl = _FakeGhlClient(posts)
            x_cli = _FakeXClient()
            bridge = GhlXBridge(state_dir=tmp_path / "state")

            # 1. Preview mode sends 0 writes
            prev = bridge.sync(ghl, x_cli, apply=False)
            self.assertEqual(prev["writes_sent"], 0)
            self.assertEqual(len(prev["actions"]), 1)
            self.assertEqual(prev["actions"][0]["action"], "publish_to_x_preview")
            self.assertEqual(prev["actions"][0]["ghl_post_ids"], ["li_page_1", "li_prof_1"])
            self.assertTrue(prev.get("plan_sha256"))

            # 2. Apply mode publishes once to X when --confirm-plan matches
            applied = bridge.sync(
                ghl,
                x_cli,
                apply=True,
                confirm_plan=prev["plan_sha256"],
                local_media_override=dummy_mp4,
            )
            self.assertEqual(applied["writes_sent"], 1)
            self.assertEqual(len(x_cli.tweets), 1)
            self.assertEqual(x_cli.tweets[0]["text"], "what do I actually sell to clients? (business intelligence)")
            self.assertEqual(applied["actions"][0]["action"], "published_to_x")

            # 3. Subsequent sync is idempotent (already_published, 0 writes)
            prev2 = bridge.sync(ghl, x_cli, apply=False)
            again = bridge.sync(
                ghl,
                x_cli,
                apply=True,
                confirm_plan=prev2["plan_sha256"],
                local_media_override=dummy_mp4,
            )
            self.assertEqual(again["writes_sent"], 0)
            self.assertEqual(len(x_cli.tweets), 1)
            self.assertEqual(again["actions"][0]["action"], "already_published")


if __name__ == "__main__":
    unittest.main()
