"""Offline tests for free multi-source football routing."""
import os
import unittest
from datetime import datetime, timezone

from bsd.free_football_sources import (
    SOURCE_QUALITY,
    SourceSnapshot,
    _sportscore_rows,
    best_match,
    enrich_bsd_events,
    extract_sportscore_odds,
    preferred_day_events,
    sportscore_goals,
    sportscore_lineups,
    summarize_h2h,
)


class TestFreeFootballSources(unittest.TestCase):
    def test_quality_order(self):
        self.assertGreater(SOURCE_QUALITY["espn"]["overall"], SOURCE_QUALITY["sportscore"]["overall"])
        self.assertGreater(SOURCE_QUALITY["sportscore"]["overall"], SOURCE_QUALITY["bsd"]["overall"])
        self.assertEqual(SOURCE_QUALITY["sportscore"]["odds"], 0)
        self.assertGreater(SOURCE_QUALITY["bsd"]["overall"], SOURCE_QUALITY["thesportsdb"]["overall"])
        self.assertGreater(SOURCE_QUALITY["thesportsdb"]["overall"], SOURCE_QUALITY["openligadb"]["overall"])

    def test_sportscore_fixture_normalization(self):
        rows = _sportscore_rows({
            "matches": [{
                "home": "Arsenal",
                "away": "Chelsea",
                "home_score": 2,
                "away_score": 1,
                "status": "finished",
                "time": "2026-10-13T18:00:00Z",
                "slug": "arsenal-vs-chelsea",
            }]
        })
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "sportscore")
        self.assertEqual(rows[0]["state"], "post")
        self.assertEqual(rows[0]["home_score"], 2)

    def test_bsd_event_keeps_id_and_gains_provider_refs(self):
        bsd = [{
            "id": 12345,
            "home_team": {"id": 1, "name": "Arsenal"},
            "away_team": {"id": 2, "name": "Chelsea"},
            "event_date": "2026-10-13T18:00:00+00:00",
            "status": "notstarted",
        }]
        sportscore = _sportscore_rows({
            "matches": [{
                "home": "Arsenal",
                "away": "Chelsea",
                "status": "scheduled",
                "time": "2026-10-13T18:00:00Z",
                "slug": "arsenal-vs-chelsea",
            }]
        })
        out = enrich_bsd_events(
            bsd,
            {"sportscore": SourceSnapshot("sportscore", sportscore, "now")},
        )
        self.assertEqual(out[0]["id"], 12345)
        self.assertEqual(out[0]["_provider_match_refs"]["sportscore"]["slug"], "arsenal-vs-chelsea")
        self.assertIn("bsd", out[0]["_provider_evidence"])
        self.assertIn("sportscore", out[0]["_provider_evidence"])

    def test_preferred_source_wins_without_duplicate(self):
        weak = [{
            "source": "openligadb",
            "id": "openligadb:1",
            "provider_event_id": "1",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "event_date": "2026-10-13T18:00:00+00:00",
            "state": "pre",
        }]
        strong = [{
            "source": "espn",
            "id": "espn:9",
            "provider_event_id": "9",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "event_date": "2026-10-13T18:00:00+00:00",
            "state": "pre",
        }]
        merged = preferred_day_events({
            "openligadb": SourceSnapshot("openligadb", weak, "now"),
            "espn": SourceSnapshot("espn", strong, "now"),
        })
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "espn")
        self.assertEqual(set(merged[0]["_provider_evidence"]), {"espn", "openligadb"})

    def test_sportscore_lineups_and_goal_timeline(self):
        detail = {
            "match": {
                "lineups": {
                    "home": {"starters": [{"name": f"H{i}"} for i in range(1, 12)]},
                    "away": {"starters": [{"name": f"A{i}"} for i in range(1, 12)]},
                },
                "timeline": [{
                    "type": "goal",
                    "minute": 64,
                    "player": {"name": "Scorer"},
                    "assist": {"name": "Assist"},
                }],
            }
        }
        lineups = sportscore_lineups(detail)
        goals = sportscore_goals(detail)
        self.assertEqual(len(lineups["home"]), 11)
        self.assertEqual(len(lineups["away"]), 11)
        self.assertEqual(goals[0]["player"], "Scorer")
        self.assertEqual(goals[0]["assists"], ["Assist"])

    def test_sportscore_odds_remain_diagnostic_even_if_legacy_flag_is_set(self):
        old = os.environ.get("SPORTSCORE_ALLOW_UNDOCUMENTED_ODDS")
        os.environ["SPORTSCORE_ALLOW_UNDOCUMENTED_ODDS"] = "1"
        try:
            probe = extract_sportscore_odds({
                "match": {"odds": [{"market": "1x2", "home": 1.9}]}
            })
            self.assertTrue(probe["available"])
            self.assertFalse(probe["contract_verified"])
            self.assertFalse(probe["automation_allowed"])
        finally:
            if old is None:
                os.environ.pop("SPORTSCORE_ALLOW_UNDOCUMENTED_ODDS", None)
            else:
                os.environ["SPORTSCORE_ALLOW_UNDOCUMENTED_ODDS"] = old

    def test_h2h_summary(self):
        rows = [
            {
                "source": "sportscore", "state": "post",
                "home_team": "Arsenal", "away_team": "Chelsea",
                "home_score": 2, "away_score": 1,
                "event_date": "2026-01-01T15:00:00+00:00",
            },
            {
                "source": "sportscore", "state": "post",
                "home_team": "Chelsea", "away_team": "Arsenal",
                "home_score": 0, "away_score": 0,
                "event_date": "2025-08-01T15:00:00+00:00",
            },
        ]
        summary = summarize_h2h(rows, "Arsenal", "Chelsea")
        self.assertEqual(summary["total_matches"], 2)
        self.assertEqual(summary["home_wins"], 1)
        self.assertEqual(summary["draws"], 1)
        self.assertEqual(summary["away_wins"], 0)


if __name__ == "__main__":
    unittest.main()
