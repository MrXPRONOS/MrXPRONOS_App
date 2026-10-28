"""Catalog diagnostics use historical data without implying live publication."""
import unittest
from scripts.catalog_snapshot_health import analyze


class CatalogSnapshotHealthTests(unittest.TestCase):
    def test_over_cap_and_numbering_gaps(self):
        data = {"audit":{"checked_at":"2026-10-27T12:00:00+00:00",
                         "not_yet_indexed_total":4},
                "source_observed":{
                    "short":{"1":{"1":[],"2":[],"3":[]}},
                    "long":{"1":{str(x):[] for x in range(1,14)}},
                    "gap":{"2":{"2":[],"4":[]}},
                }}
        result = analyze(data, category="anime")
        self.assertEqual(result["titles_observed"],3)
        self.assertEqual(result["titles_over_cap"],1)
        self.assertEqual(result["titles_within_cap"],2)
        self.assertEqual(result["titles_with_numbering_gaps"],1)
        self.assertEqual(result["titles_missing_episode_one"],1)
        self.assertFalse(result["telegram_real_time_verified"])
        self.assertFalse(result["selection_eligibility_verified"])

    def test_episode_number_twelve_plus_second_season_counts_to_cap(self):
        data={"source_observed":{"multi":{"1":{str(i):[] for i in range(1,9)},
                                          "2":{str(i):[] for i in range(1,6)}}}}
        result=analyze(data,category="series")
        self.assertEqual(result["historical_episode_numbers"],13)
        self.assertEqual(result["titles_over_cap"],1)

    def test_empty_snapshot_is_not_live_eligibility(self):
        result=analyze({},category="series")
        self.assertEqual(result["titles_observed"],0)
        self.assertIsNone(result["snapshot_checked_at"])
        self.assertFalse(result["publication_rights_verified"])
        self.assertFalse(result["selection_eligibility_verified"])


if __name__ == "__main__":
    unittest.main()
