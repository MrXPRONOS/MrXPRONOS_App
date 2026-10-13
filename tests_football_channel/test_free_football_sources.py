import unittest
from unittest.mock import patch
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import free_football_sources as f


class FreeFootballSourcesTests(unittest.TestCase):
    def test_quality_ranking(self):
        self.assertGreater(f.PROVIDER_RANK["bsd"]["quality"], f.PROVIDER_RANK["espn"]["quality"])
        self.assertGreater(f.PROVIDER_RANK["espn"]["quality"], f.PROVIDER_RANK["sportscore"]["quality"])
        self.assertGreater(f.PROVIDER_RANK["sportscore"]["quality"], f.PROVIDER_RANK["thesportsdb"]["quality"])
        self.assertGreater(f.PROVIDER_RANK["thesportsdb"]["quality"], f.PROVIDER_RANK["openligadb"]["quality"])

    def test_merge_keeps_provider_provenance(self):
        rows = [
            {
                "source": "sportscore", "id": "sportscore:1", "source_match_id": "1",
                "home_team": "Arsenal", "away_team": "Chelsea",
                "event_date": "2026-10-13T18:00:00+00:00",
                "provider_slug": "arsenal-vs-chelsea",
                "provider_quality": 86, "home_score": 1, "away_score": 0,
            },
            {
                "source": "thesportsdb", "id": "thesportsdb:9", "source_match_id": "9",
                "home_team": "Arsenal FC", "away_team": "Chelsea FC",
                "event_date": "2026-10-13T18:02:00+00:00",
                "provider_quality": 78, "home_score": 1, "away_score": 0,
            },
        ]
        merged = f.merge_provider_matches(rows)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "sportscore")
        self.assertEqual(set(merged[0]["provider_sources"]), {"sportscore", "thesportsdb"})
        self.assertEqual(merged[0]["provider_ids"]["thesportsdb"], "9")

    def test_sportscore_enrichment_extracts_lineup_goal_and_stats(self):
        starters_home = [{"name": f"H{i}", "starter": True} for i in range(1, 12)]
        starters_away = [{"name": f"A{i}", "starter": True} for i in range(1, 12)]
        detail = {
            "lineups": {"home": starters_home, "away": starters_away},
            "timeline": [
                {"type": "Goal", "minute": "64'", "player": {"name": "H7"}, "assist": "H10"},
                {"type": "Yellow Card", "minute": "70'", "player": {"name": "A4"}},
            ],
            "statistics": [
                {"name": "Corners", "home": 7, "away": 3},
                {"name": "Shots on Target", "home": 6, "away": 2},
            ],
            "venue": "Emirates Stadium",
        }
        data = f.extract_sportscore_enrichment(detail)
        self.assertEqual(len(data["lineups"]["home"]), 11)
        self.assertEqual(data["goals"][0]["player"], "H7")
        self.assertEqual(data["goals"][0]["minute_total"], 64)
        self.assertEqual(data["goals"][0]["assists"], ["H10"])
        self.assertEqual(data["stats"]["home"]["corners"], 7)
        self.assertEqual(data["stats"]["away"]["shots_on_target"], 2)
        self.assertEqual(data["info"]["venue"], "Emirates Stadium")

    def test_provider_fallback_prefers_sportscore_mapping(self):
        match = {
            "source": "espn",
            "id": "401",
            "provider_slugs": {"sportscore": "arsenal-vs-chelsea"},
            "provider_ids": {"thesportsdb": "9"},
        }
        with patch.object(f, "fetch_sportscore_detail", return_value={
            "timeline": [{"type": "Goal", "minute": "10'", "player": {"name": "Saka"}}]
        }) as sport, patch.object(f, "fetch_thesportsdb_details") as tsdb:
            data = f.fetch_provider_enrichment(object(), match)
        self.assertEqual(data["goals"][0]["player"], "Saka")
        sport.assert_called_once()
        tsdb.assert_not_called()


if __name__ == "__main__":
    unittest.main()
