import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import free_football_providers as providers
import bsd_h2h


class FreeFootballProvidersTests(unittest.TestCase):
    def test_provider_policy_quality_and_odds(self):
        policy = providers.provider_policy()
        self.assertGreater(policy["quality"]["espn"], policy["quality"]["bsd"])
        self.assertGreater(policy["quality"]["bsd"], policy["quality"]["sportscore"])
        self.assertEqual(policy["fetch_priority"][-1], "bsd")
        self.assertEqual(policy["odds_priority"], ["bsd"])
        self.assertFalse(policy["sportscore_odds_api_supported"])

    def test_sportscore_normalization_preserves_zero_score(self):
        row = providers.normalize_sportscore({
            "id": 55,
            "home": "Arsenal",
            "away": "Chelsea",
            "home_score": 0,
            "away_score": 0,
            "status": "live",
            "time": "2026-10-13T18:00:00Z",
            "slug": "arsenal-chelsea",
        })
        self.assertEqual(row["home_score"], 0)
        self.assertEqual(row["away_score"], 0)
        self.assertEqual(row["status"], "live")
        self.assertEqual(row["source"], "sportscore")

    def test_tsdb_normalization(self):
        row = providers.normalize_tsdb({
            "idEvent": "123",
            "strSport": "Soccer",
            "strHomeTeam": "Arsenal",
            "strAwayTeam": "Chelsea",
            "intHomeScore": "2",
            "intAwayScore": "1",
            "strStatus": "Match Finished",
            "strTimestamp": "2026-10-13T18:00:00Z",
        })
        self.assertEqual(row["status"], "finished")
        self.assertEqual(row["home_score"], 2)
        self.assertEqual(row["source"], "thesportsdb")

    def test_openliga_normalization(self):
        row = providers.normalize_openliga({
            "matchID": 9,
            "matchDateTimeUTC": "2026-10-13T18:00:00Z",
            "matchIsFinished": True,
            "team1": {"teamId": 1, "teamName": "Bayern"},
            "team2": {"teamId": 2, "teamName": "Dortmund"},
            "matchResults": [
                {"resultOrderID": 1, "pointsTeam1": 1, "pointsTeam2": 0},
                {"resultOrderID": 2, "pointsTeam1": 3, "pointsTeam2": 1},
            ],
        })
        self.assertEqual(row["home_score"], 3)
        self.assertEqual(row["away_score"], 1)
        self.assertEqual(row["status"], "finished")

    def test_merge_facts_never_treats_zero_as_missing(self):
        hub = providers.FreeFootballProviders(session=MagicMock())
        high = {
            "source": "sportscore", "source_quality": 91,
            "home_score": 0, "away_score": 0,
            "home_team": "A", "away_team": "B",
        }
        low = {
            "source": "thesportsdb", "source_quality": 80,
            "home_score": 2, "away_score": 1,
            "home_team": "A", "away_team": "B",
        }
        merged = hub.merge_facts([high, low])
        self.assertEqual(merged["home_score"], 0)
        self.assertEqual(merged["away_score"], 0)

    def test_sportscore_h2h_prevents_bsd_request(self):
        kickoff = datetime.now(timezone.utc) + timedelta(days=1)
        fixture = {
            "id": 999,
            "event_date": kickoff.isoformat(),
            "home_team": {"id": 1, "name": "Arsenal"},
            "away_team": {"id": 2, "name": "Chelsea"},
        }
        client = MagicMock()
        client.session = MagicMock()
        client.get_h2h.side_effect = AssertionError("BSD H2H should not be called")
        free = {
            "source": "sportscore",
            "total_matches": 4,
            "home_wins": 2,
            "away_wins": 1,
            "draws": 1,
            "home_goals": 6,
            "away_goals": 4,
            "recent_matches": [],
        }
        with patch.object(bsd_h2h, "_free_h2h_sportscore", return_value=free):
            result = bsd_h2h.hybrid_h2h(
                client, fixture, [], min_local_meetings=3,
                allow_api=True, now=datetime.now(timezone.utc),
            )
        self.assertEqual(result["source"], "sportscore")
        self.assertEqual(result["total_matches"], 4)
        client.get_h2h.assert_not_called()


if __name__ == "__main__":
    unittest.main()
