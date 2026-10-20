"""Offline archive pagination, cursor durability and missing-number diagnostics."""
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from film_relay.catalog_scan import (
    read_source_window, source_window_ids, finalize_scan, episode_audit,
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
            {"series": "naruto", "season": 1, "episode": 2},
        ], category="anime", ignored_unnumbered=4)
        self.assertEqual(result["numbering_gaps"][0]["missing_between_known"], [2])
        self.assertEqual(result["not_yet_indexed_total"], 1)
        self.assertEqual(result["unnumbered_videos_skipped"], 4)
        self.assertIn("pas la preuve", result["note"])

    def test_github_merge_keeps_oldest_checkpoint_and_audit(self):
        remote = {"series": {}, "scans": {"s": {"cursor": 80, "complete": False}},
                  "audit": {"checked_at": "old"}}
        local = {"series": {}, "scans": {"s": {"cursor": 40, "complete": False}},
                 "audit": {"checked_at": "new"}}
        merged = merge(remote, local)
        self.assertEqual(merged["scans"]["s"]["cursor"], 40)
        self.assertEqual(merged["audit"]["checked_at"], "new")


if __name__ == "__main__":
    unittest.main()
