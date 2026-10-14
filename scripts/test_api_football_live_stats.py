"""Offline regression tests; no API keys and no HTTP requests."""
import unittest
from datetime import datetime, timezone
from scripts.api_football_live_stats import parse_statistics, find_matches, build_row, norm_name, league_stats_coverage, safe_remaining, ProviderRejectedRequest

class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.fixture={
            "fixture":{"id":98761,"date":"2026-10-14T19:00:00Z","status":{"elapsed":61}},
            "teams":{"home":{"id":101,"name":"FC Example United"},
                     "away":{"id":202,"name":"City Athletic"}},
            "goals":{"home":1,"away":1},
        }
        self.match={
            "canonical_match_id":"20261014_example-united_city-athletic",
            "home_team":"Example United",
            "away_team":"City Athletic",
            "event_date":"2026-10-14T19:00:00Z",
            "minute":60,"is_live":True,"is_finished":False,"league_name":"League",
            "merged_stats":{"home":{},"away":{}},
        }

    def test_real_fixture_stats_market_names(self):
        response=[
            {"team":{"id":101},"statistics":[
                {"type":"Corner Kicks","value":7},
                {"type":"Total Shots","value":18},
                {"type":"Fouls","value":12},
                {"type":"Shots on Goal","value":5},
                {"type":"Ball Possession","value":"52%"},
            ]},
            {"team":{"id":202},"statistics":[
                {"type":"Corner Kicks","value":4},
                {"type":"Total Shots","value":10},
                {"type":"Fouls","value":11},
                {"type":"Shots on Goal","value":3},
                {"type":"Ball Possession","value":"48%"},
            ]},
        ]
        stats=parse_statistics(response,"101","202")
        self.assertEqual(stats["totals"]["corners"],11)
        self.assertEqual(stats["totals"]["total_shots"],28)
        self.assertEqual(stats["totals"]["fouls"],23)
        self.assertEqual(stats["home"]["ball_possession"],52)
        row=build_row(self.match,self.fixture,stats)
        self.assertEqual(row["source_name"],"api_football")
        self.assertEqual(row["source_match_id"],"98761")
        self.assertEqual(row["canonical_match_id"],self.match["canonical_match_id"])

    def test_null_is_unknown_not_zero(self):
        stats=parse_statistics([
            {"team":{"id":101},"statistics":[{"type":"Corner Kicks","value":None}]},
            {"team":{"id":202},"statistics":[{"type":"Corner Kicks","value":3}]},
        ],"101","202")
        self.assertNotIn("corners",stats["totals"])
        self.assertNotIn("corner_kicks",stats["home"])
        self.assertIsNone(build_row(self.match,self.fixture,stats))

    def test_match_both_teams_and_kickoff(self):
        self.assertEqual(len(find_matches([self.match],[self.fixture])),1)
        inverted={**self.fixture,"teams":{"home":self.fixture["teams"]["away"],"away":self.fixture["teams"]["home"]}}
        self.assertEqual(find_matches([self.match],[inverted]),[])
        ambiguous={**self.fixture,"fixture":{**self.fixture["fixture"],"id":98762}}
        self.assertEqual(find_matches([self.match],[self.fixture,ambiguous]),[])
        late={**self.fixture,"fixture":{**self.fixture["fixture"],"date":"2026-10-15T09:00:00Z"}}
        self.assertEqual(find_matches([self.match],[late]),[])


class ProviderCoverageTests(unittest.TestCase):
    def test_known_unsupported_league_skips_stats(self):
        payload=[{
            "league":{"id":123},
            "seasons":[
                {"year":2025,"coverage":{"fixtures":{"statistics_fixtures":True}}},
                {"year":2026,"coverage":{"fixtures":{"statistics_fixtures":False}}},
            ],
        }]
        self.assertIs(league_stats_coverage(payload,123,2026),False)
        self.assertIs(league_stats_coverage(payload,123,2025),True)

    def test_unknown_coverage_remains_unknown(self):
        payload=[{"league":{"id":123},"seasons":[
            {"year":2026,"coverage":{"fixtures":{}}}
        ]}]
        self.assertIsNone(league_stats_coverage(payload,123,2026))
        self.assertIsNone(league_stats_coverage([],123,2026))

    def test_provider_restriction_exposes_keys_only(self):
        exception=ProviderRejectedRequest(["plan", "requests"])
        self.assertEqual(exception.error_keys, ["plan", "requests"])
        self.assertNotIn("token", str(exception).lower())

    def test_quota_missing_header_fails_neutral(self):
        self.assertIsNone(safe_remaining(None))
        self.assertIsNone(safe_remaining("unknown"))
        self.assertEqual(safe_remaining("95"),95)
        self.assertEqual(safe_remaining("0"),0)


if __name__ == "__main__":
    unittest.main()
