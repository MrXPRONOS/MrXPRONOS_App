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

    def test_openliga_builds_table_from_results(self):
        payload = [
            {
                "team1": {"teamName": "Bayern München"},
                "team2": {"teamName": "Dortmund"},
                "matchResults": [
                    {"resultOrderID": 1, "pointsTeam1": 1, "pointsTeam2": 0},
                    {"resultOrderID": 2, "pointsTeam1": 2, "pointsTeam2": 1},
                ],
            },
            {
                "team1": {"teamName": "Dortmund"},
                "team2": {"teamName": "Leverkusen"},
                "matchResults": [
                    {"resultOrderID": 2, "pointsTeam1": 1, "pointsTeam2": 1},
                ],
            },
        ]
        bundesliga = next(x for x in stats.LEAGUES if x.openliga)
        rows = stats.fetch_openliga_table(FakeSession(payload), bundesliga, season=2026)
        self.assertEqual(rows[0]["team"], "Bayern München")
        self.assertEqual(rows[0]["points"], 3)
        dortmund = next(x for x in rows if x["team"] == "Dortmund")
        self.assertEqual(dortmund["points"], 1)
        self.assertEqual(dortmund["played"], 2)

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
        self.assertIn("Sources", post.text)

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
