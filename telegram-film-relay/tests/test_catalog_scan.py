"""Offline archive pagination, cursor durability and missing-number diagnostics."""
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock

from film_relay.category_runner import preflight

from film_relay.catalog_scan import (
    read_source_window, source_window_ids, split_source_windows, finalize_scan, episode_audit,
)
from scripts.merge_anime_catalog import merge


class FakeTelegram:
    def __init__(self, ids):
        self.ids = sorted(ids, reverse=True)
        self.calls = []

    async def iter_messages(self, source, *, limit, max_id=None):
        self.calls.append((limit, max_id))
        for value in [n for n in self.ids if max_id is None or n < max_id][:limit]:
            yield NS(id=value, raw_text="", document=None)


class HistoryTests(unittest.TestCase):
    def test_recent_and_archived_pages_recover_old_messages(self):
        client = FakeTelegram(range(1, 101))
        with patch.dict("os.environ", {"CINEX_CATALOG_PAGE_SIZE": "40"}):
            messages, plan = asyncio.run(read_source_window(client, "source", {}, -100123))
        self.assertEqual(len(source_window_ids(messages, plan)), 80)
        self.assertEqual(plan["next_cursor"], 21)
        self.assertEqual(plan["archive_ids"], set(range(21, 61)))
        self.assertNotIn(20, source_window_ids(messages, plan))
        self.assertIn((40, 61), client.calls)

    def test_completed_archive_rotates_without_losing_original_cursor(self):
        client = FakeTelegram(range(1, 161))
        catalogue = {"scans": {"-100123": {"cursor": 1, "complete": True, "pages": 4}},
                     "series": {}}
        with patch.dict("os.environ", {"CINEX_CATALOG_PAGE_SIZE": "40"}):
            seen = []
            for _ in range(3):
                messages, plan = asyncio.run(
                    read_source_window(client, "source", catalogue, -100123))
                self.assertTrue(plan["revisit"])
                self.assertEqual(len(plan["archive_ids"]), 40)
                seen.append(max(plan["archive_ids"]))
                finalize_scan(catalogue, [plan], [])
                self.assertEqual(catalogue["scans"]["-100123"]["cursor"], 1)
            self.assertEqual(seen, [120, 80, 40])
            _, last = asyncio.run(read_source_window(
                client, "source", catalogue, -100123))
            self.assertTrue(last["complete"])
            finalize_scan(catalogue, [last], [])
            self.assertIsNone(catalogue["scans"]["-100123"]["revisit_cursor"])
            self.assertEqual(catalogue["scans"]["-100123"]["pages"], 4)

    def test_recent_episodes_do_not_inherit_old_archive_artwork(self):
        messages = [NS(id=20, photo=True, raw_text="Naruto"),
                    NS(id=21, photo=None, raw_text="EP01"),
                    NS(id=120, photo=None, raw_text="EP01")]
        plan = {"archive_ids": {20, 21}, "recent_ids": {120},
                "allowed_ids": {21, 120}}
        windows = split_source_windows(messages, plan)
        self.assertEqual([[item.id for item in window] for window in windows],
                         [[20, 21], [120]])

    def test_archive_cursor_waits_for_all_numbered_episodes(self):
        row = {"source_key": "-100123:22", "video": NS(id=22),
               "series": "naruto", "season": 1, "episode": 2}
        plan = {"source_id": "-100123", "archive_ids": {22},
                "next_cursor": 21, "complete": False, "count": 40}
        catalogue = {"series": {"naruto": {"source_items": {}}}}
        result = finalize_scan(catalogue, [plan], [row])
        self.assertEqual(result["episodes_waiting"], 1)
        self.assertNotIn("-100123", catalogue["scans"])
        catalogue["series"]["naruto"]["source_items"][row["source_key"]] = 43
        result = finalize_scan(catalogue, [plan], [row])
        self.assertEqual(result["episodes_waiting"], 0)
        self.assertEqual(catalogue["scans"]["-100123"]["cursor"], 21)

    def test_numbering_gaps_are_only_suspicions(self):
        catalogue = {"series": {"naruto": {"source_items": {},
                    "episodes": {"1": {"1": {"message_id": 1},
                                      "3": {"message_id": 3}}}}}}
        result = episode_audit(catalogue, [
            {"series": "naruto", "season": 1, "episode": 2, "source_key": "-100555:5"},
        ], category="anime", ignored_unnumbered=4)
        self.assertEqual(result["numbering_gaps"][0]["missing_between_known"], [2])
        self.assertEqual(result["not_yet_indexed_total"], 1)
        self.assertEqual(result["unnumbered_videos_skipped"], 4)
        self.assertIn("pas la preuve", result["note"])

    def test_source_inventory_persists_across_scanned_pages(self):
        catalogue = {"series": {}}
        first = [{"series": "naruto", "season": 1, "episode": 1,
                  "source_key": "-100123:11"}]
        episode_audit(catalogue, first, category="anime")
        later = [{"series": "naruto", "season": 1, "episode": 3,
                  "source_key": "-100123:13"}]
        result = episode_audit(catalogue, later, category="anime")
        self.assertEqual(result["source_episode_numbers_observed"], 2)
        self.assertEqual(result["source_numbering_gaps"][0]["not_observed_between_known"], [2])
        self.assertEqual(result["not_yet_indexed_total"], 2)

    def test_preflight_rejects_mistyped_private_id(self):
        private = NS(peer_id=-100444, broadcast=True, username=None)
        public = NS(peer_id=-100555, broadcast=True, username="publictest")
        source = NS(peer_id=-100666, broadcast=True, username="sourcetest", noforwards=False)
        cfg = {"private": "-100999", "public": "@publictest",
               "sources": ["@sourcetest"], "category": "anime"}
        client = NS(is_user_authorized=AsyncMock(return_value=True))
        mapping = {cfg["private"]: private, cfg["public"]: public, "@sourcetest": source}
        with patch("film_relay.category_runner.resolve_peer",
                   new=AsyncMock(side_effect=lambda client, value: mapping[value])), \
             patch("film_relay.category_runner.asyncio.sleep", new=AsyncMock()), \
             patch("telethon.utils.get_peer_id", side_effect=lambda value: value.peer_id):
            with self.assertRaisesRegex(RuntimeError, "canal privé"):
                asyncio.run(preflight(client, None, cfg))

    def test_preflight_accepts_numeric_public_id(self):
        private = NS(peer_id=-100444, broadcast=True, username=None)
        public = NS(peer_id=-100555, broadcast=True, username="publictest")
        source = NS(peer_id=-100666, broadcast=True, username="sourcetest", noforwards=False)
        cfg = {"private": "-100444", "public": "-100555",
               "sources": ["@sourcetest"], "category": "series"}
        client = NS(is_user_authorized=AsyncMock(return_value=True))
        mapping = {cfg["private"]: private, cfg["public"]: public, "@sourcetest": source}
        with patch("film_relay.category_runner.resolve_peer",
                   new=AsyncMock(side_effect=lambda client, value: mapping[value])), \
             patch("film_relay.category_runner.asyncio.sleep", new=AsyncMock()), \
             patch("telethon.utils.get_peer_id", side_effect=lambda value: value.peer_id):
            result = asyncio.run(preflight(client, None, cfg))
        self.assertEqual(len(result[0]), 1)

    def test_github_merge_keeps_oldest_checkpoint_and_audit(self):
        remote = {"series": {}, "scans": {"s": {"cursor": 80, "complete": False}},
                  "audit": {"checked_at": "old"}}
        local = {"series": {}, "scans": {"s": {"cursor": 40, "complete": False}},
                 "audit": {"checked_at": "new"}}
        merged = merge(remote, local)
        self.assertEqual(merged["scans"]["s"]["cursor"], 40)
        self.assertEqual(merged["audit"]["checked_at"], "new")
        merged2 = merge({"series": {}, "source_observed": {
            "naruto": {"1": {"1": ["a:1"]}}}}, {"series": {}, "source_observed": {
            "naruto": {"1": {"1": ["a:1", "b:1"], "2": ["a:2"]}}}})
        self.assertEqual(merged2["source_observed"]["naruto"]["1"]["1"], ["a:1", "b:1"])
        self.assertEqual(merged2["source_observed"]["naruto"]["1"]["2"], ["a:2"])


if __name__ == "__main__":
    unittest.main()
