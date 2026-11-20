"""Offline tests for the read-only Anime health report."""
import unittest

from scripts.anime_health_report import summarize


class AnimeHealthReportTests(unittest.TestCase):
    def test_counts_ongoing_and_public_receipts(self):
        data = {
            "series": {"petite-serie": {
                "public_id": 10,
                "episodes": {"1": {
                    "1": {"message_id": 11},
                    "2": {"message_id": 12},
                }},
                "season_status": {"1": "en_cours"},
                "public_episode_posts": {
                    "S01E01": {"poster": 20, "video": 21},
                },
            }},
            "active_batch": None,
            "scans": {"-100123": {"complete": True}},
        }
        report = summarize(data)
        self.assertEqual(report["titles"], 1)
        self.assertEqual(report["seasons"], 1)
        self.assertEqual(report["ongoing_seasons"], 1)
        self.assertEqual(report["private_episodes"], 2)
        self.assertEqual(report["public_episode_pairs"], 1)
        self.assertEqual(report["sources_scanned"], 1)
        self.assertFalse(report["active_batch"])

    def test_empty_catalogue_is_safe(self):
        self.assertFalse(summarize({})["active_batch"])


if __name__ == "__main__":
    unittest.main()
