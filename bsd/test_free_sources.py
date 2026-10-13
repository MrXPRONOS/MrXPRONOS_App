import os
import unittest
from datetime import date

from free_sources import FreeFootballHub, SOURCE_RANKINGS


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.ok = 200 <= status < 300
        self.headers = {}
        self.url = "https://example.test"

    def raise_for_status(self):
        if not self.ok:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, **kwargs):
        key = (url, tuple(sorted((params or {}).items())))
        self.calls.append(key)
        if key not in self.routes:
            raise AssertionError("Unexpected request: %r" % (key,))
        return FakeResponse(self.routes[key])


class FreeSourceTests(unittest.TestCase):
    def test_source_ranking_is_explicit(self):
        self.assertEqual(SOURCE_RANKINGS["espn"]["rank"], 1)
        self.assertEqual(SOURCE_RANKINGS["bsd"]["rank"], 2)
        self.assertLess(SOURCE_RANKINGS["sportscore"]["rank"], SOURCE_RANKINGS["thesportsdb"]["rank"])
        self.assertLess(SOURCE_RANKINGS["thesportsdb"]["rank"], SOURCE_RANKINGS["openligadb"]["rank"])

    def test_sportscore_day_normalization(self):
        url = "https://sportscore.com/api/v1/fixtures/"
        params = (("date", "2026-10-13"), ("limit", 200), ("sport", "football"))
        session = FakeSession({
            (url, params): {
                "matches": [{
                    "id": "55",
                    "slug": "arsenal-chelsea",
                    "home": "Arsenal",
                    "away": "Chelsea",
                    "home_score": 2,
                    "away_score": 1,
                    "status": "live",
                    "time": "2026-10-13T18:00:00Z",
                    "competition": "Premier League",
                }]
            }
        })
        hub = FreeFootballHub(session=session, enabled=True)
        rows = hub.sportscore_day(date(2026, 10, 13))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "sportscore")
        self.assertEqual(rows[0]["home_team"], "Arsenal")
        self.assertEqual(rows[0]["home_score"], 2)
        self.assertEqual(rows[0]["source_slug"], "arsenal-chelsea")

    def test_thesportsdb_day_normalization(self):
        url = "https://www.thesportsdb.com/api/v1/json/123/eventsday.php"
        params = (("d", "2026-10-13"), ("s", "Soccer"))
        session = FakeSession({
            (url, params): {
                "events": [{
                    "idEvent": "999",
                    "strHomeTeam": "Arsenal",
                    "strAwayTeam": "Chelsea",
                    "intHomeScore": "2",
                    "intAwayScore": "1",
                    "strStatus": "Match Finished",
                    "strTimestamp": "2026-10-13T18:00:00Z",
                    "strLeague": "English Premier League",
                }]
            }
        })
        hub = FreeFootballHub(session=session, enabled=True)
        rows = hub.thesportsdb_day(date(2026, 10, 13))
        self.assertEqual(rows[0]["source"], "thesportsdb")
        self.assertEqual(rows[0]["status"], "finished")
        self.assertEqual(rows[0]["away_score"], 1)

    def test_openligadb_normalization(self):
        url = "https://api.openligadb.de/getmatchdata/bl1"
        session = FakeSession({
            (url, ()): [{
                "matchID": 123,
                "matchDateTimeUTC": "2026-10-13T18:00:00Z",
                "matchIsFinished": True,
                "team1": {"teamName": "Bayern München", "teamIconUrl": "h.png"},
                "team2": {"teamName": "Dortmund", "teamIconUrl": "a.png"},
                "league": {"leagueName": "Bundesliga"},
                "matchResults": [{
                    "resultTypeKind": "After90Minutes",
                    "pointsTeam1": 3,
                    "pointsTeam2": 2,
                }],
                "goals": [{"goalGetterName": "Example", "matchMinute": 20}],
            }]
        })
        hub = FreeFootballHub(session=session, enabled=True)
        rows = hub.openligadb_current(shortcuts=["bl1"])
        self.assertEqual(rows[0]["source"], "openligadb")
        self.assertEqual(rows[0]["home_score"], 3)
        self.assertEqual(rows[0]["goals"][0]["matchMinute"], 20)

    def test_enrichment_preserves_bsd_identity(self):
        day = date(2026, 10, 13)
        hub = FreeFootballHub(session=FakeSession({}), enabled=True)
        hub.day = lambda _day: {
            "sportscore": [{
                "source_match_id": "ss1",
                "source_slug": "arsenal-chelsea",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "event_date": "2026-10-13T18:00:00Z",
                "league_name": "Premier League",
                "home_logo": "h.png",
                "away_logo": "a.png",
                "home_score": None,
                "away_score": None,
            }],
            "thesportsdb": [],
            "openligadb": [],
        }
        event = {
            "id": 42,
            "home_team_id": 100,
            "away_team_id": 200,
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "event_date": "2026-10-13T18:00:00Z",
            "status": "notstarted",
        }
        diag = hub.enrich_bsd_events([event], day)
        self.assertEqual(event["id"], 42)
        self.assertEqual(event["home_team_id"], 100)
        self.assertEqual(event["league_name"], "Premier League")
        self.assertIn("sportscore", event["provider_sources"])
        self.assertGreaterEqual(diag["fields_filled"], 1)

    def test_diagnostics_do_not_claim_sportscore_odds_api(self):
        hub = FreeFootballHub(session=FakeSession({}), enabled=True)
        info = hub.diagnostics()
        self.assertFalse(info["sportscore_odds_api"]["supported"])


if __name__ == "__main__":
    unittest.main()
