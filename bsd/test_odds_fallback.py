"""Offline contract tests for five-provider fallback; no network or API key."""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from bsd_odds_fallback import (OddsRouter, match_fixture, from_oddslink,
                               from_pinnwire, from_harvester, from_movi, quote)

NOW = datetime(2026, 10, 13, 10, 0, tzinfo=timezone.utc)
EVENT = {"home_team":"Real Madrid","away_team":"FC Barcelona","event_date":"2026-10-14T19:00:00Z"}
ROW = {"home":"Real Madrid","away":"FC Barcelona","kickoff_utc":"2026-10-14T19:00:00Z"}


class FakeResponse:
    def __init__(self, status, data):
        self.status_code = status
        self.data = data
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError("HTTP "+str(self.status_code))
    def json(self):
        return self.data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
    def get(self, *args, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


class RouterTests(unittest.TestCase):
    def test_match_reversed_or_mismatched_rejected(self):
        self.assertTrue(match_fixture(ROW,EVENT))
        self.assertFalse(match_fixture({**ROW,"away":"Another FC"},EVENT))
        self.assertFalse(match_fixture({**ROW,"home":"FC Barcelona","away":"Real Madrid"},EVENT))
        self.assertFalse(match_fixture({**ROW,"kickoff_utc":"2026-10-16T19:00:00Z"},EVENT))

    def test_quote_freshness(self):
        self.assertIsNone(quote(1.5,"pinnwire",NOW,updated=(NOW+timedelta(hours=1)).isoformat()))
        self.assertIsNone(quote(1.5,"pinnwire",NOW,updated=(NOW-timedelta(days=3)).isoformat()))
        self.assertIsNone(quote(0.9,"pinnwire",NOW))
        self.assertEqual(quote(1.5,"pinnwire",NOW)["odds"],1.5)

    def test_pinnwire(self):
        event={"periods":{"num_0":{"money_line":{"home":1.82,"draw":3.4,"away":4.2},
               "totals":{"2.5":{"points":2.5,"over":1.8,"under":2.0}}}}}
        out=from_pinnwire(event,NOW)
        self.assertEqual(out["1X2_HOME_FT"]["odds"],1.82)
        self.assertEqual(out["OU_2.5_OVER_FT"]["odds"],1.8)

    def test_oddslink_strict_market(self):
        fixture={"home_team":"Real Madrid","away_team":"Barcelona",
                 "bookmakers":[{"markets":[{"key":"h2h","outcomes":[
                   {"name":"Real Madrid","price":1.92},
                   {"name":"Draw","price":3.2}]},
                   {"key":"totals","outcomes":[{"name":"Over","point":2.5,"price":1.9}]}]}]}
        out=from_oddslink(fixture,NOW)
        self.assertEqual(out["1X2_HOME_FT"]["odds"],1.92)
        self.assertEqual(out["OU_2.5_OVER_FT"]["odds"],1.9)

    def test_movi_ambiguous_market_ignored(self):
        out=from_movi({"home":"Real Madrid","away":"Barcelona",
                        "quotes":[{"group_name":"corners","label":"over","line":2.5,"odds_dec":1.8},
                        {"group_name":"goals over under","side":"over","line":2.5,"odds_dec":1.97}]},NOW)
        self.assertNotIn("OU_2.5_UNDER_FT",out)
        self.assertEqual(out["OU_2.5_OVER_FT"]["odds"],1.97)

    def test_harvester_stale_rejected(self):
        t=(NOW-timedelta(hours=2)).isoformat()
        self.assertFalse(from_harvester({"scraped_at":t,"odds":[{"1":1.7}]},NOW))

    def test_fallback_on_empty_and_rate_limit(self):
        session=FakeSession([FakeResponse(429,{}),FakeResponse(200,{"matches":[{
            **ROW,"in_play":False,"quotes":[{"group_name":"match result",
                "label":"Real Madrid","odds_dec":1.8}]}]})])
        with patch.dict(os.environ,{"PINNWIRE_API_KEY":"demo","ODDSLINK_API_KEY":""},clear=False):
            router=OddsRouter(lambda ev,at: ({},{}),session=session,
                order=("goaldir","pinnwire","moviodds"))
            result,diag=router.fetch(EVENT,NOW)
        self.assertEqual(diag["provider"],"moviodds")
        self.assertEqual(result["1X2_HOME_FT"]["odds"],1.8)
        self.assertIn("pinnwire",router.disabled)
        self.assertEqual(session.calls,2)

    def test_fallback_if_first_provider_has_wrong_market(self):
        session=FakeSession([FakeResponse(200,{"matches":[{
            **ROW,"in_play":False,"quotes":[{"group_name":"Goals Over/Under",
                "side":"O","line":"2.5","odds_dec":1.91}]}]})])
        router=OddsRouter(lambda event,at: ({"1X2_HOME_FT":{"odds":1.50}}, {}),
                          session=session, order=("goaldir","moviodds"))
        with patch.dict(os.environ,{"MOVIODDS_ENABLE":"1"}):
            out,diag=router.fetch(EVENT,NOW,market_code="OU_2.5_OVER_FT")
        self.assertEqual(diag["provider"],"moviodds")
        self.assertEqual(out["OU_2.5_OVER_FT"]["odds"],1.91)

    def test_all_unavailable_returns_empty_not_fake_quote(self):
        router=OddsRouter(lambda ev,at: ({},{}),order=("goaldir",))
        result,diag=router.fetch(EVENT,NOW)
        self.assertEqual(result,{})
        self.assertIsNone(diag["provider"])


if __name__ == "__main__": unittest.main()
