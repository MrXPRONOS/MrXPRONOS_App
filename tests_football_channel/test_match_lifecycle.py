import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bsd"))

import football_match_lifecycle as m
import football_channel as channel


NOW = datetime(2026, 10, 13, 18, 30, tzinfo=timezone.utc)


class MatchLifecycleTests(unittest.TestCase):
    def test_parse_espn_event(self):
        raw = {
            "id": "401",
            "date": "2026-10-13T18:00:00Z",
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "score": "2", "team": {"id": "1", "displayName": "Arsenal", "logo": "https://a/logo.png"}},
                    {"homeAway": "away", "score": "1", "team": {"id": "2", "displayName": "Chelsea", "logo": "https://b/logo.png"}},
                ],
                "status": {
                    "displayClock": "67:00",
                    "period": 2,
                    "type": {"state": "in", "shortDetail": "67'", "completed": False},
                },
            }],
        }
        event = m.parse_espn_event(raw)
        self.assertEqual(event["home_team"], "Arsenal")
        self.assertEqual(event["away_team"], "Chelsea")
        self.assertEqual(event["home_score"], 2)
        self.assertEqual(event["away_score"], 1)
        self.assertEqual(event["minute"], 67)
        self.assertEqual(event["state"], "in")
        self.assertEqual(event["home_logo"], "https://a/logo.png")
        self.assertEqual(event["away_logo"], "https://b/logo.png")

    def test_extract_lineups_and_goals(self):
        summary = {
            "rosters": [
                {
                    "homeAway": "home",
                    "roster": [
                        {"starter": True, "athlete": {"displayName": f"Home {i}"}}
                        for i in range(1, 12)
                    ],
                },
                {
                    "homeAway": "away",
                    "roster": [
                        {"starter": True, "athlete": {"displayName": f"Away {i}"}}
                        for i in range(1, 12)
                    ],
                },
            ],
            "details": [{
                "scoringPlay": True,
                "type": {"text": "Goal"},
                "clock": {"displayValue": "64'"},
                "athletes": [{"displayName": "Bukayo Saka"}],
                "team": {"id": "1"},
            }],
        }
        lineups = m.extract_lineups(summary)
        self.assertEqual(len(lineups["home"]), 11)
        self.assertEqual(len(lineups["away"]), 11)
        goals = m.extract_goals(summary)
        self.assertEqual(goals[-1]["player"], "Bukayo Saka")
        self.assertEqual(goals[-1]["minute"], 64)

    @patch("football_match_lifecycle.fetch_espn_summary")
    @patch("football_match_lifecycle.collect_external")
    def test_composition_signal_transporte_les_logos(self, collect_external, fetch_summary):
        kickoff = NOW + timedelta(minutes=30)
        base = [{
            "id": "bsd-lineup",
            "event_date": kickoff.isoformat(),
            "home_team": {"name": "Arsenal"},
            "away_team": {"name": "Chelsea"},
            "league_name": "Premier League",
        }]
        collect_external.return_value = [{
            "source": "espn",
            "id": "espn-lineup",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_logo": "https://a/logo.png",
            "away_logo": "https://b/logo.png",
            "home_score": 0,
            "away_score": 0,
            "minute": 0,
            "state": "pre",
            "status_detail": "Scheduled",
            "event_date": kickoff.isoformat(),
        }]
        fetch_summary.return_value = {
            "rosters": [
                {
                    "homeAway": "home",
                    "roster": [
                        {"starter": True, "athlete": {"displayName": f"Home {i}"}}
                        for i in range(1, 12)
                    ],
                },
                {
                    "homeAway": "away",
                    "roster": [
                        {"starter": True, "athlete": {"displayName": f"Away {i}"}}
                        for i in range(1, 12)
                    ],
                },
            ],
        }

        signals = m.lifecycle_signals(base, set(), NOW, object(), lambda _: 100)
        compositions = [x for x in signals if x["kind"] == "composition"]
        self.assertEqual(len(compositions), 1)
        self.assertEqual(compositions[0]["home_logo"], "https://a/logo.png")
        self.assertEqual(compositions[0]["away_logo"], "https://b/logo.png")
        self.assertEqual(len(compositions[0]["lineups"]["home"]), 11)
        self.assertEqual(len(compositions[0]["lineups"]["away"]), 11)

    def test_composition_publication_attache_le_template(self):
        post = channel.lifecycle_publication({
            "kind": "composition",
            "key": "composition:401",
            "home": "Arsenal",
            "away": "Chelsea",
            "league": "Premier League",
            "kickoff": NOW + timedelta(minutes=30),
            "source": "ESPN",
            "home_logo": "https://a/logo.png",
            "away_logo": "https://b/logo.png",
            "lineups": {
                "home": [f"Home Player {i}" for i in range(1, 12)],
                "away": [f"Away Player {i}" for i in range(1, 12)],
            },
        })
        self.assertIsNotNone(post)
        self.assertEqual(post.category, "composition")
        self.assertIsNotNone(post.card)
        self.assertEqual(post.card["competition"], "Premier League")
        self.assertEqual(len(post.card["home_players"]), 11)
        self.assertEqual(len(post.card["away_players"]), 11)
        self.assertEqual(post.card["home_logo"], "https://a/logo.png")
        self.assertEqual(post.card["away_logo"], "https://b/logo.png")

    @patch("football_match_lifecycle.fetch_espn_summary")
    @patch("football_match_lifecycle.collect_external")
    def test_recent_goal_signal_only_once_per_score(self, collect_external, fetch_summary):
        base = [{
            "id": "bsd-1",
            "event_date": "2026-10-13T18:00:00+00:00",
            "home_team": {"name": "Arsenal"},
            "away_team": {"name": "Chelsea"},
            "league_name": "Premier League",
        }]
        collect_external.return_value = [{
            "source": "espn",
            "id": "espn-1",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_team_id": "1",
            "away_team_id": "2",
            "home_score": 2,
            "away_score": 1,
            "minute": 67,
            "state": "in",
            "status_detail": "67'",
            "event_date": "2026-10-13T18:00:00+00:00",
        }]
        fetch_summary.return_value = {
            "details": [{
                "scoringPlay": True,
                "type": {"text": "Goal"},
                "clock": {"displayValue": "64'"},
                "athletes": [{"displayName": "Bukayo Saka"}],
                "team": {"id": "1"},
            }]
        }
        signals = m.lifecycle_signals(base, set(), NOW, object(), lambda _: 100)
        goals = [x for x in signals if x["kind"] == "goal"]
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["key"], "goal:espn-1:2-1:64:bukayo-saka")

        again = m.lifecycle_signals(base, {"goal:espn-1:2-1:64:bukayo-saka"}, NOW, object(), lambda _: 100)
        self.assertFalse([x for x in again if x["kind"] == "goal"])

    @patch("football_match_lifecycle.fetch_espn_summary")
    @patch("football_match_lifecycle.collect_external")
    def test_old_goal_is_not_announced(self, collect_external, fetch_summary):
        base = [{
            "id": "bsd-1",
            "event_date": "2026-10-13T18:00:00+00:00",
            "home_team": {"name": "Arsenal"},
            "away_team": {"name": "Chelsea"},
            "league_name": "Premier League",
        }]
        collect_external.return_value = [{
            "source": "espn",
            "id": "espn-1",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_score": 1,
            "away_score": 0,
            "minute": 70,
            "state": "in",
            "status_detail": "70'",
            "event_date": "2026-10-13T18:00:00+00:00",
        }]
        fetch_summary.return_value = {
            "details": [{
                "scoringPlay": True,
                "type": {"text": "Goal"},
                "clock": {"displayValue": "12'"},
                "athletes": [{"displayName": "Player"}],
            }]
        }
        signals = m.lifecycle_signals(base, set(), NOW, object(), lambda _: 100)
        self.assertFalse([x for x in signals if x["kind"] == "goal"])

    @patch("football_match_lifecycle.fetch_espn_summary", return_value={})
    @patch("football_match_lifecycle.fetch_supabase_live", return_value=[])
    @patch("football_match_lifecycle.fetch_espn_day")
    def test_lifecycle_can_use_espn_without_bsd(self, fetch_day, _supabase, _summary):
        fetch_day.return_value = [{
            "source": "espn",
            "id": "espn-fast",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_score": 0,
            "away_score": 0,
            "minute": 4,
            "state": "in",
            "status_detail": "4'",
            "event_date": (NOW - timedelta(minutes=4)).isoformat(),
            "league": "Premier League",
        }]
        signals = m.lifecycle_signals([], set(), NOW, object(), lambda _: 100)
        kickoff = [x for x in signals if x["kind"] == "kickoff"]
        self.assertEqual(len(kickoff), 1)
        self.assertEqual(kickoff[0]["key"], "kickoff:espn-fast")

    def test_goal_signal_rendered_for_actu_foot(self):
        post = channel.lifecycle_publication({
            "kind": "goal",
            "key": "goal:401:2-1",
            "home": "Arsenal",
            "away": "Chelsea",
            "league": "Premier League",
            "minute": 67,
            "score": "2-1",
            "source": "ESPN",
            "goal": {"player": "Bukayo Saka", "minute_text": "64'", "penalty": False, "own_goal": False},
        })
        self.assertIsNotNone(post)
        self.assertEqual(post.category, "goal")
        self.assertIn("BUUUUT", post.text)
        self.assertIn("Bukayo Saka", post.text)
        self.assertIn("2-1", post.text)
        self.assertTrue(post.keyboard)

    @patch("football_match_lifecycle.fetch_espn_summary", return_value={})
    @patch("football_match_lifecycle.collect_external")
    def test_espn_cache_confirms_score_update_1_1(self, collect, _summary):
        collect.return_value = [{
            "source": "supabase_live", "id": "espn:401912650",
            "home_team": "Newcastle Jets", "away_team": "Gamba Osaka",
            "home_score": 1, "away_score": 1,
            "minute": 59, "state": "in",
            "status_detail": "STATUS_SECOND_HALF",
            "event_date": "2026-10-13T07:45:00Z"
        }]
        found = m.lifecycle_signals([], set(), NOW, object(), lambda _: 0)
        updates = [x for x in found if x["kind"] == "score_update"]
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["score"], "1-1")
        publication = channel.lifecycle_publication(updates[0])
        self.assertIn("SCORE LIVE", publication.text)
        self.assertIn("1-1", publication.text)
        again = m.lifecycle_signals([], {updates[0]["key"]}, NOW, object(), lambda _: 0)
        self.assertFalse([x for x in again if x["kind"] == "score_update"])

    def test_explicit_halftime_status(self):
        self.assertTrue(m.is_halftime({"status_detail": "STATUS_HALFTIME"}))
        self.assertTrue(m.is_halftime({"status_detail": "HT"}))
        self.assertFalse(m.is_halftime({"status_detail": "STATUS_SECOND_HALF"}))


if __name__ == "__main__":
    unittest.main()
