import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

import football_provider_mesh as mesh


def row(source, quality, *, logo="", score=None):
    return {
        "id": source + ":1",
        "event_date": "2026-10-13T18:00:00+00:00",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "home_score": score,
        "away_score": 0 if score is not None else None,
        "status": "scheduled",
        "league_name": "Premier League",
        "home_logo": logo,
        "away_logo": "",
        "current_minute": 0,
        "source": source,
        "source_quality": quality,
        "sources": [source],
        "provider_ids": {source: "1"},
        "provider_meta": {source: {}},
        "raw_data": {"source": source},
    }


class ProviderMeshTests(unittest.TestCase):
    def test_quality_order_keeps_espn_core_and_fills_missing_fields(self):
        espn = row("espn", mesh.PROVIDER_QUALITY["espn"])
        sport = row("sportscore", mesh.PROVIDER_QUALITY["sportscore"], logo="https://img/logo.png")
        merged = mesh.merge_events([sport, espn])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "espn")
        self.assertEqual(merged[0]["home_logo"], "https://img/logo.png")
        self.assertIn("espn", merged[0]["sources"])
        self.assertIn("sportscore", merged[0]["sources"])

    def test_sportscore_odds_parser_rejects_ai_probability(self):
        payload = {
            "ai_prediction": {
                "market": "double chance",
                "outcome": "1X",
                "probability": 0.78,
                "odds": 1.31,
            },
            "bookmakers": [{
                "market": "Double Chance",
                "selection": "1X",
                "bookmaker": "Example",
                "decimal_odds": 1.44,
            }],
        }
        found = mesh.explicit_sportscore_odds(payload)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["source"], "sportscore_explicit_json")
        self.assertEqual(found[0]["odds"], 1.44)

    @patch.object(mesh, "fetch_thesportsdb_day", return_value=[])
    @patch.object(mesh, "fetch_sportscore_day", return_value=[])
    @patch.object(mesh, "fetch_espn_day")
    def test_bsd_is_not_called_when_free_coverage_is_sufficient(
        self, espn, _sport, _tsdb
    ):
        espn.return_value = [row("espn", mesh.PROVIDER_QUALITY["espn"])]
        def forbidden():
            raise AssertionError("BSD must not be instantiated")
        client = mesh.FreeFirstFootballClient(
            bsd_factory=forbidden,
            min_free_matches=1,
        )
        page = client.list_events(date(2026, 10, 13), date(2026, 10, 13))
        self.assertEqual(len(page.events), 1)
        self.assertFalse(page.bsd_used)
        self.assertEqual(client.bsd_requests_saved, 1)

    @patch.object(mesh, "fetch_thesportsdb_day", return_value=[])
    @patch.object(mesh, "fetch_sportscore_day", return_value=[])
    @patch.object(mesh, "fetch_espn_day", return_value=[])
    def test_bsd_backfills_when_free_coverage_is_empty(self, *_):
        class FakeBSD:
            requests_made = 0
            def list_events(self, *_args, **_kwargs):
                self.requests_made += 1
                return mesh.BSDPage(
                    events=[{
                        "id": 99,
                        "event_date": "2026-10-13T18:00:00+00:00",
                        "home_team": "Arsenal",
                        "away_team": "Chelsea",
                        "home_score": 0,
                        "away_score": 0,
                        "status": "scheduled",
                    }],
                    total_reported=1,
                    pages_fetched=1,
                    complete=True,
                )
        fake = FakeBSD()
        client = mesh.FreeFirstFootballClient(
            bsd_factory=lambda: fake,
            min_free_matches=1,
        )
        page = client.list_events(date(2026, 10, 13), date(2026, 10, 13))
        self.assertTrue(page.bsd_used)
        self.assertEqual(page.bsd_requests, 1)
        self.assertIn("bsd", page.events[0]["sources"])


if __name__ == "__main__":
    unittest.main()
