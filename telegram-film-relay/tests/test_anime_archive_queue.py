"""Legacy scanner cursor advances only after durable source-ID queueing."""
from __future__ import annotations

import unittest
from types import SimpleNamespace as NS

from film_relay.catalog_scan import finalize_scan
from film_relay.anime_archive_queue import (
    enqueue_archive_candidates, prune_receipted_archive,
)
from scripts.merge_anime_catalog import merge


def row(n, *, series="naruto"):
    return {
        "source_key": f"-100111:{n}",
        "video": NS(id=n), "poster": NS(id=10, photo=True),
        "series": series, "title": series.title(), "season": 1,
        "episode": n - 10, "timestamp": float(n),
    }


class ArchiveQueueTests(unittest.TestCase):
    def test_opt_in_queue_advances_page_despite_zero_uploads(self):
        catalogue = {"series": {"naruto": {"source_items": {}}}}
        plan = {"source_id": "-100111", "archive_ids": {11, 12},
                "next_cursor": 10, "complete": False, "count": 2,
                "revisit": False}
        report = finalize_scan(
            catalogue, [plan], [row(11), row(12)], queue_enabled=True)
        self.assertEqual(report["pages_saved"], 1)
        self.assertEqual(report["archive_queued"], 2)
        self.assertEqual(report["episodes_waiting"], 0)
        self.assertEqual(catalogue["scans"]["-100111"]["cursor"], 10)
        self.assertEqual(len(catalogue["archive_pending"]), 2)
        # Repeated scan does not duplicate the queue.
        second = finalize_scan(
            catalogue, [plan], [row(11), row(12)], queue_enabled=True)
        self.assertEqual(second["archive_queued"], 0)

    def test_default_cursor_still_waits_until_published(self):
        catalogue = {"series": {"naruto": {"source_items": {}}}}
        plan = {"source_id": "-100111", "archive_ids": {11},
                "next_cursor": 10, "complete": False, "count": 1}
        report = finalize_scan(catalogue, [plan], [row(11)])
        self.assertEqual(report["episodes_waiting"], 1)
        self.assertEqual(report["pages_saved"], 0)

    def test_queue_references_persist_through_concurrent_merge(self):
        prior = {"series": {"naruto": {"source_items": {}}},
                 "archive_pending": {"-100111:11": {"message_id": 11}}}
        fresh = {"series": {"naruto": {"source_items": {}}},
                 "archive_pending": {"-100111:12": {"message_id": 12}}}
        result = merge(prior, fresh)
        self.assertEqual(set(result["archive_pending"]),
                         {"-100111:11", "-100111:12"})

    def test_queue_only_pruned_after_persisted_receipt(self):
        catalogue = {"series": {"naruto": {"source_items": {}}},
                     "archive_pending": {
                         "-100111:11": {"message_id": 11},
                         "-100111:12": {"message_id": 12},
                     }}
        self.assertEqual(prune_receipted_archive(catalogue), 0)
        catalogue["series"]["naruto"]["source_items"]["-100111:11"] = 91
        self.assertEqual(prune_receipted_archive(catalogue), 1)
        self.assertEqual(list(catalogue["archive_pending"]), ["-100111:12"])
        merged = merge(
            {"archive_pending": {"-100111:11": {"message_id": 11}},
             "series": {"naruto": {"source_items": {"-100111:11": 91}}}},
            {"series": {}, "archive_pending": {}})
        self.assertNotIn("-100111:11", merged["archive_pending"])


if __name__ == "__main__":
    unittest.main()
