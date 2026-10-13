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

    def test_espn_enrichment_parses_stoppage_cards_subs_stats_and_match_info(self):
        summary = {
            "header": {
                "id": "401",
                "competitions": [{
                    "id": "401",
                    "date": "2026-10-13T18:00:00Z",
                    "competitors": [
                        {"homeAway": "home", "score": "2", "team": {"id": "1", "displayName": "Arsenal"}},
                        {"homeAway": "away", "score": "1", "team": {"id": "2", "displayName": "Chelsea"}},
                    ],
                    "status": {"type": {"state": "post", "completed": True, "detail": "FT"}},
                }],
            },
            "details": [
                {
                    "scoringPlay": True,
                    "type": {"text": "Goal"},
                    "clock": {"displayValue": "90'+2'"},
                    "athletes": [
                        {"displayName": "Bukayo Saka"},
                        {"displayName": "Martin Odegaard", "type": "assist"},
                    ],
                    "team": {"id": "1"},
                },
                {
                    "yellowCard": True,
                    "type": {"text": "Yellow Card"},
                    "clock": {"displayValue": "51'"},
                    "athletes": [{"displayName": "Player Card"}],
                    "team": {"id": "2"},
                },
                {
                    "substitution": True,
                    "type": {"text": "Substitution"},
                    "clock": {"displayValue": "68'"},
                    "athletes": [
                        {"displayName": "Player In"},
                        {"displayName": "Player Out"},
                    ],
                    "team": {"id": "1"},
                },
            ],
            "boxscore": {
                "teams": [
                    {
                        "team": {"id": "1"},
                        "statistics": [
                            {"name": "wonCorners", "displayValue": "7"},
                            {"name": "totalShots", "displayValue": "15"},
                            {"name": "shotsOnTarget", "displayValue": "6"},
                            {"name": "possessionPct", "displayValue": "58%"},
                            {"name": "foulsCommitted", "displayValue": "9"},
                        ],
                    },
                    {
                        "team": {"id": "2"},
                        "statistics": [
                            {"name": "wonCorners", "displayValue": "3"},
                            {"name": "totalShots", "displayValue": "10"},
                            {"name": "shotsOnTarget", "displayValue": "4"},
                            {"name": "possessionPct", "displayValue": "42%"},
                            {"name": "foulsCommitted", "displayValue": "12"},
                        ],
                    },
                ],
                "players": [{
                    "team": {"id": "1"},
                    "statistics": [{
                        "name": "general",
                        "names": ["MIN", "SH", "SOG"],
                        "athletes": [{
                            "athlete": {"id": "10", "displayName": "Bukayo Saka"},
                            "starter": True,
                            "didNotPlay": False,
                            "stats": ["90", "4", "2"],
                        }],
                    }],
                }],
            },
            "gameInfo": {
                "venue": {"fullName": "Emirates Stadium", "address": {"city": "London", "country": "England"}},
                "attendance": 60250,
                "officials": [{"official": {"displayName": "Ref Example"}}],
                "weather": {"displayValue": "Clear", "temperature": 18},
            },
        }
        enriched = m.extract_match_enrichment(summary)
        self.assertEqual(enriched["goals"][0]["player"], "Bukayo Saka")
        self.assertEqual(enriched["goals"][0]["minute_total"], 92)
        self.assertEqual(enriched["goals"][0]["assists"], ["Martin Odegaard"])
        self.assertEqual(enriched["cards"][0]["type"], "yellow")
        self.assertEqual(enriched["substitutions"][0]["players"], ["Player In", "Player Out"])
        self.assertEqual(enriched["stats"]["home"]["corners"], "7")
        self.assertEqual(enriched["stats"]["away"]["possession"], "42%")
        self.assertEqual(enriched["info"]["venue"], "Emirates Stadium")
        self.assertEqual(enriched["info"]["attendance"], 60250)
        self.assertEqual(enriched["info"]["referees"], ["Ref Example"])
        self.assertEqual(enriched["timeline"][-1]["minute_total"], 92)
        self.assertEqual(enriched["player_stats"][0]["player"], "Bukayo Saka")
        self.assertEqual(enriched["player_stats"][0]["stats"]["SOG"], "2")

    @patch("football_match_lifecycle.verify_espn_public_page")
    @patch("football_match_lifecycle.fetch_espn_summary")
    def test_prepublication_goal_is_revalidated_directly_on_espn(self, fetch_summary, verify_page):
        fetch_summary.return_value = {
            "header": {
                "id": "401",
                "competitions": [{
                    "id": "401",
                    "date": "2026-10-13T18:00:00Z",
                    "competitors": [
                        {"homeAway": "home", "score": "2", "team": {"id": "1", "displayName": "Arsenal"}},
                        {"homeAway": "away", "score": "1", "team": {"id": "2", "displayName": "Chelsea"}},
                    ],
                    "status": {"type": {"state": "in", "completed": False, "detail": "67'"}},
                }],
            },
            "details": [{
                "scoringPlay": True,
                "type": {"text": "Goal"},
                "clock": {"displayValue": "64'"},
                "athletes": [{"displayName": "Bukayo Saka"}],
                "team": {"id": "1"},
            }],
        }
        verify_page.return_value = {
            "reachable": True,
            "content_verified": True,
            "url": "https://www.espn.com/soccer/match/_/gameId/401",
            "status": 200,
        }
        result = m.verify_espn_before_publish(object(), {
            "event_id": "401",
            "kind": "goal",
            "home": "Arsenal",
            "away": "Chelsea",
            "score": "2-1",
            "goal": {"player": "Bukayo Saka", "minute": 64},
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["quality"], 100)
        fetch_summary.assert_called_once_with(unittest.mock.ANY, "401", force=True)

        rejected = m.verify_espn_before_publish(object(), {
            "event_id": "401",
            "kind": "goal",
            "home": "Arsenal",
            "away": "Chelsea",
            "score": "2-1",
            "goal": {"player": "Wrong Player", "minute": 64},
        })
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "goal_not_confirmed")


    @patch("football_match_lifecycle.verify_espn_public_page")
    @patch("football_match_lifecycle.fetch_espn_day")
    def test_fixture_preflight_blocks_changed_espn_kickoff(self, fetch_day, verify_page):
        fetch_day.return_value = [{
            "source": "espn",
            "id": "401",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "home_score": None,
            "away_score": None,
            "state": "pre",
            "status_detail": "Scheduled",
            "event_date": "2026-10-13T20:00:00+00:00",
            "espn_url": "https://www.espn.com/soccer/match/_/gameId/401",
        }]
        verify_page.return_value = {"reachable": True, "content_verified": True}
        result = m.verify_espn_fixtures_before_publish(object(), {
            "kind": "programme",
            "fixtures": [{
                "home": "Arsenal",
                "away": "Chelsea",
                "event_date": "2026-10-13T18:00:00+00:00",
            }],
        })
        self.assertFalse(result["ok"])
        self.assertEqual(result["contradictions"][0]["reason"], "kickoff_mismatch")

    @patch("football_match_lifecycle.fetch_espn_day", return_value=[])
    def test_fixture_preflight_does_not_block_when_espn_has_no_coverage(self, fetch_day):
        result = m.verify_espn_fixtures_before_publish(object(), {
            "kind": "avant_match",
            "fixtures": [{
                "home": "ASKO Kara",
                "away": "AC Barracuda",
                "event_date": "2026-10-13T18:00:00+00:00",
            }],
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "espn_not_covered")
        self.assertEqual(result["covered"], 0)
        fetch_day.assert_called()

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

    def test_goal_publication_carries_espn_verification_and_link(self):
        post = channel.lifecycle_publication({
            "kind": "goal",
            "key": "goal:401:2-1:64:bukayo-saka",
            "home": "Arsenal",
            "away": "Chelsea",
            "league": "Premier League",
            "minute": 67,
            "score": "2-1",
            "source": "ESPN",
            "espn_event_id": "401",
            "espn_url": "https://www.espn.com/soccer/match/_/gameId/401",
            "goal": {
                "player": "Bukayo Saka",
                "minute_text": "64'",
                "minute_total": 64,
                "assists": ["Martin Odegaard"],
                "penalty": False,
                "own_goal": False,
            },
        })
        self.assertIsNotNone(post)
        self.assertEqual(post.verification["event_id"], "401")
        self.assertIn("Passe", post.text)
        self.assertIn("Martin Odegaard", post.text)
        buttons = [b for row in post.keyboard["inline_keyboard"] for b in row]
        self.assertTrue(any("ESPN" in b["text"] for b in buttons))

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
