"""Tests hors ligne de la sélection et du suivi du backfill BSD."""
import unittest

from bsd_backfill import items_from_leagues, season_year, league_id
from bsd_api import BSDAPIError


class BackfillTests(unittest.TestCase):
    def test_supported_years(self):
        self.assertEqual(season_year({"year": 2016, "name": "2016"}), 2016)
        self.assertEqual(season_year({"year": 2024, "name": "2024"}), 2024)
        self.assertEqual(season_year({"name": "Apertura 2023/24"}), 2023)

    def test_unknown_year_not_invented(self):
        self.assertIsNone(season_year({"name": "Torneo Apertura"}))

    def test_league_pagination_contract(self):
        rows, count = items_from_leagues({"count": 1, "results": [{"id": 85}]})
        self.assertEqual(count, 1)
        self.assertEqual(league_id(rows[0]), 85)
        with self.assertRaises(BSDAPIError):
            items_from_leagues({"data": []})


if __name__ == "__main__":
    unittest.main()
