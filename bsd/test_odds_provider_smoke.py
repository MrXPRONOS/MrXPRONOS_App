"""Offline contract tests for the real-HTTP smoke summary: no network or keys."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from odds_provider_smoke import summarize, probe

AT = datetime(2026, 10, 28, 14, 0, tzinfo=timezone.utc)


class StubResponse:
    def __init__(self, code, body):
        self.status_code, self.body = code, body
    def json(self):
        return self.body


class StubSession:
    def __init__(self, response):
        self.response = response
    def get(self, *args, **kwargs):
        return self.response


def board(updated):
    return {"fixtures": [{
        "home_team": "Home Team", "away_team": "Away Team",
        "commence_time": "2026-10-29T16:00:00Z", "in_play": False,
        "bookmakers": [{"kind": "sportsbook", "key": "book",
            "last_update": updated,
            "markets": {"h2h": [{"name": "Home Team", "price": -150}]}}]
    }]}


class HealthSmokeTests(unittest.TestCase):
    def test_fresh_public_quotes_observed(self):
        d = summarize("oddslink_public", board(AT.isoformat()), AT)
        self.assertTrue(d["schema_valid"])
        self.assertEqual(d["fresh_timestamped_prices"], 1)
        self.assertEqual(d["fixtures_with_fresh_prices"], 1)

    def test_old_price_not_mistaken_for_current(self):
        d = summarize("oddslink_public",
                      board((AT-timedelta(hours=3)).isoformat()), AT)
        self.assertEqual(d["fresh_timestamped_prices"], 0)

    def test_rejected_schema_is_not_a_connection_success(self):
        r = probe("oddslink_public", "https://example.test",
                  session=StubSession(StubResponse(200, {"bad": []})), now=AT)
        self.assertTrue(r["connected"])
        self.assertFalse(r["schema_valid"])
        self.assertEqual(r["result"], "invalid_schema")

    def test_http_429_remains_restricted(self):
        r = probe("oddslink_public", "https://example.test",
                  session=StubSession(StubResponse(429, {})), now=AT)
        self.assertFalse(r["connected"])
        self.assertEqual(r["result"], "restricted")


if __name__ == "__main__":
    unittest.main()
