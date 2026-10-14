import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bsd"))

import football_stats_engine as stats
import football_channel as channel


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


class StatsEngineTests(unittest.TestCase):
    def test_parse_espn_standings(self):
        payload = {
            "children": [{
                "standings": {
                    "entries": [
                        {
                            "team": {"id": "1", "displayName": "Arsenal"},
                            "stats": [
                                {"name": "rank", "value": 1},
                                {"name": "gamesPlayed", "value": 8},
                                {"name": "wins", "value": 6},
                                {"name": "ties", "value": 1},
                                {"name": "losses", "value": 1},
                                {"name": "points", "value": 19},
                                {"name": "pointsFor", "value": 18},
                                {"name": "pointsAgainst", "value": 7},
                                {"name": "pointDifferential", "value": 11},
                            ],
                        },
                        {
                            "team": {"id": "2", "displayName": "Liverpool"},
                            "stats": [
                                {"name": "rank", "value": 2},
                                {"name": "gamesPlayed", "value": 8},
                                {"name": "wins", "value": 5},
                                {"name": "ties", "value": 2},
                                {"name": "losses", "value": 1},
                                {"name": "points", "value": 17},
                                {"name": "pointsFor", "value": 16},
                                {"name": "pointsAgainst", "value": 8},
                                {"name": "pointDifferential", "value": 8},
                            ],
                        },
                    ]
                }
            }]
        }
        rows = stats.fetch_espn_standings(
            FakeSession(payload), stats.LEAGUES[0], season=2026
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["team"], "Arsenal")
        self.assertEqual(rows[0]["points"], 19)
        self.assertEqual(rows[0]["goals_for"], 18)
        self.assertEqual(rows[0]["goal_diff"], 11)

    def test_openliga_parses_direct_table(self):
        payload = [
            {
                "TeamInfoId": 40, "TeamName": "FC Bayern München",
                "Points": 18, "OpponentGoals": 5, "Goals": 20,
                "Matches": 7, "Won": 6, "Lost": 1, "Draw": 0, "GoalDiff": 15,
            },
            {
                "TeamInfoId": 7, "TeamName": "Borussia Dortmund",
                "Points": 16, "OpponentGoals": 7, "Goals": 17,
                "Matches": 7, "Won": 5, "Lost": 1, "Draw": 1, "GoalDiff": 10,
            },
        ]
        bundesliga = next(x for x in stats.LEAGUES if x.openliga)
        rows = stats.fetch_openliga_table(FakeSession(payload), bundesliga, season=2026)
        self.assertEqual(rows[0]["team"], "FC Bayern München")
        self.assertEqual(rows[0]["points"], 18)
        self.assertEqual(rows[0]["played"], 7)
        self.assertEqual(rows[0]["goal_diff"], 15)

    def test_openliga_top_scorers(self):
        payload = [
            {"goalGetterName": "Harry Kane", "goalCount": 9},
            {"goalGetterName": "Serhou Guirassy", "goalCount": 7},
        ]
        bundesliga = next(x for x in stats.LEAGUES if x.openliga)
        rows = stats.fetch_openliga_top_scorers(FakeSession(payload), bundesliga, season=2026)
        self.assertEqual(rows[0]["player"], "Harry Kane")
        self.assertEqual(rows[0]["goals"], 9)
        self.assertEqual(rows[0]["source"], "OpenLigaDB")

    def test_table_agreement_accepts_name_variants(self):
        a = [
            {"team": "Paris Saint-Germain", "rank": 1, "points": 20},
            {"team": "Olympique Marseille", "rank": 2, "points": 18},
        ]
        b = [
            {"team": "Paris Saint Germain", "rank": 1, "points": 20},
            {"team": "Marseille", "rank": 2, "points": 18},
        ]
        self.assertGreaterEqual(stats.table_agreement(a, b), 0.6)

    def test_build_attack_and_defense_insights(self):
        snapshot = {
            "league": "Premier League",
            "sources": ["ESPN", "football-data.org"],
            "confidence": 94,
            "table": [
                {"team": "Arsenal", "rank": 1, "played": 10, "wins": 8, "points": 25,
                 "goals_for": 26, "goals_against": 7, "goal_diff": 19},
                {"team": "Liverpool", "rank": 2, "played": 10, "wins": 7, "points": 23,
                 "goals_for": 28, "goals_against": 11, "goal_diff": 17},
                {"team": "Chelsea", "rank": 3, "played": 10, "wins": 6, "points": 20,
                 "goals_for": 21, "goals_against": 6, "goal_diff": 15},
                {"team": "City", "rank": 4, "played": 10, "wins": 5, "points": 18,
                 "goals_for": 20, "goals_against": 10, "goal_diff": 10},
            ],
            "top_scorers": [],
        }
        attack = stats.build_insight(snapshot, variant=1)
        defense = stats.build_insight(snapshot, variant=2)
        self.assertEqual(attack["kind"], "attack")
        self.assertIn("Liverpool", attack["headline"])
        self.assertEqual(defense["kind"], "defense")
        self.assertIn("Chelsea", defense["headline"])

    @patch("football_channel.has_two_team_logos", return_value=True)
    @patch("football_channel.team_visual_url", return_value="https://example.com/logo.png")
    def test_prematch_renders_verified_h2h(self, _logo, _has_logos):
        fixture = {
            "id": 77,
            "event_date": "2026-10-13T20:00:00+00:00",
            "home_team": {"id": 11, "name": "Arsenal"},
            "away_team": {"id": 22, "name": "Chelsea"},
            "league_name": "Premier League",
            "status": "notstarted",
        }
        history = channel.History(Path("/tmp/nonexistent-xpronos-test-state.json"))
        now = channel.moment("2026-10-13T18:00:00+00:00")
        post = channel.avant_match(
            [fixture], history, now, [],
            {"home": "V-V-N-V-D", "away": "N-D-V-V-N"},
            {"total_matches": 10, "home_wins": 5, "away_wins": 3, "draws": 2, "avg_total_goals": 2.7},
        )
        self.assertIsNotNone(post)
        self.assertEqual(post.card["h2h_total"], 10)
        self.assertEqual(post.card["h2h_home_wins"], 5)
        self.assertEqual(post.card["h2h_draws"], 2)
        self.assertEqual(post.card["h2h_away_wins"], 3)
        self.assertNotIn("Confrontations directes", post.text)

    @patch("football_channel.daily_insight")
    def test_advanced_stat_render(self, daily):
        daily.return_value = {
            "kind": "standings",
            "title": "🏆 CLASSEMENT • Premier League",
            "headline": "Arsenal est leader avec 25 points",
            "lines": [
                "1. Arsenal — 25 pts",
                "2. Liverpool — 23 pts",
                "3. Chelsea — 20 pts",
            ],
            "source": "ESPN + football-data.org",
            "confidence": 94,
            "league_key": "premier-league",
        }
        post = channel.statistique_avancee(object(), date(2026, 10, 13))
        self.assertIsNotNone(post)
        self.assertEqual(post.category, "statistique")
        self.assertIn("Arsenal", post.text)
        self.assertIn("94%", post.text)
        self.assertIn("Source :", post.text)

    @patch("football_channel.daily_insight", return_value={
        "kind": "standings",
        "title": "Classement",
        "headline": "Donnée trop faible",
        "lines": [],
        "source": "ESPN",
        "confidence": 55,
        "league_key": "premier-league",
    })
    def test_advanced_stat_rejects_low_confidence(self, _daily):
        self.assertIsNone(
            channel.statistique_avancee(object(), date(2026, 10, 13))
        )


if __name__ == "__main__":
    unittest.main()
