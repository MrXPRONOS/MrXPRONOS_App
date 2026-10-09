"""Tests ciblés sur le script d'importation BSD réellement exécuté (2024–2026)."""
import unittest
from bsd_backfill_2024_2026 import season_year, items_from_leagues
from bsd_history import ingest_events


class Backfill2024Tests(unittest.TestCase):
    def test_current_season_years(self):
        self.assertEqual(season_year({"year": 2024}), 2024)
        self.assertEqual(season_year({"year": 2025}), 2025)
        self.assertEqual(season_year({"year": 2026}), 2026)

    def test_year_not_invented(self):
        self.assertIsNone(season_year({"name": "Torneo Apertura"}))

    def test_page_contract(self):
        self.assertEqual(items_from_leagues({"count": 1, "results": [{"id": 85}]})[1], 1)

    def test_season_merge_keeps_unique_events(self):
        old = [{"id": 1, "status": "notstarted", "home_team_id": 3}]
        new = [{"id": 1, "status": "finished", "home_score": 2}, {"id": 2, "status": "finished"}]
        out = ingest_events(old, new)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["home_team_id"], 3)
        self.assertEqual(out[0]["home_score"], 2)


if __name__ == "__main__":
    unittest.main()
