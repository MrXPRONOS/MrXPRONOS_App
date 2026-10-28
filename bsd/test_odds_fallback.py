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
        out=from_pinnwire(event,NOW,snapshot_generated_at=NOW.isoformat())
        self.assertEqual(out["1X2_HOME_FT"]["odds"],1.82)
        self.assertEqual(out["OU_2.5_OVER_FT"]["odds"],1.8)
        self.assertEqual(out["1X2_HOME_FT"]["quote_timestamp_type"],"provider_snapshot")
        self.assertFalse(out["1X2_HOME_FT"]["per_market_update_verified"])
        self.assertEqual(from_pinnwire(event,NOW),{})
        self.assertEqual(from_pinnwire(event,NOW,
            snapshot_generated_at=(NOW-timedelta(minutes=5)).isoformat()),{})
        self.assertEqual(from_pinnwire({**event,"event_type":"live"},NOW,
            snapshot_generated_at=NOW.isoformat()),{})

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
                "label":"Real Madrid","odds_dec":1.8}],
                "polled_at":NOW.isoformat()}]})])
        with patch.dict(os.environ,{"PINNWIRE_API_KEY":"demo","ODDSLINK_API_KEY":"","MOVIODDS_ENABLE":"1"},clear=False):
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
                "side":"O","line":"2.5","odds_dec":1.91}],
                "polled_at":NOW.isoformat()}]})])
        router=OddsRouter(lambda event,at: ({"1X2_HOME_FT":{"odds":1.50}}, {}),
                          session=session, order=("goaldir","moviodds"))
        with patch.dict(os.environ,{"MOVIODDS_ENABLE":"1"}):
            out,diag=router.fetch(EVENT,NOW,market_code="OU_2.5_OVER_FT")
        self.assertEqual(diag["provider"],"moviodds")
        self.assertEqual(out["OU_2.5_OVER_FT"]["odds"],1.91)


    def test_market_quote_comparison_selects_highest_verified_same_market(self):
        captured=NOW
        session=FakeSession([FakeResponse(200,{"matches":[{
            **ROW,"in_play":False,"polled_at":captured.isoformat(),
            "quotes":[{"group_name":"Match Result","label":"Real Madrid",
                       "odds_dec":1.62}]}]})])
        def bsd(event, when):
            return {"1X2_HOME_FT":{"odds":1.33,"origin":"bsd_consensus",
                    "updated_at":when.isoformat()}},{}
        with patch.dict(os.environ,{"MOVIODDS_ENABLE":"1"}):
            router=OddsRouter(bsd,session=session,order=("goaldir","moviodds"))
            out,diag=router.fetch(EVENT,captured,market_code="1X2_HOME_FT")
        self.assertEqual(out["1X2_HOME_FT"]["odds"],1.33)
        self.assertEqual(diag["provider"],"goaldir")
        self.assertEqual(diag["verified_provider_count"],1)
        self.assertEqual(diag["exact_market_code"],"1X2_HOME_FT")
        self.assertIsNone(router.usage.get("moviodds"))

    def test_pinnwire_fresh_snapshot_precedes_lower_source(self):
        from bsd_odds_fallback import SOURCE_TIERS
        session=FakeSession([FakeResponse(200,{
            "generated_at":NOW.isoformat(),
            "events":[{
                **ROW,"event_type":"prematch","is_have_odds":True,
                "periods":{"num_0":{"money_line":{"home":1.52}}}
            }]
        })])
        def bsd(event,when):
            return {"1X2_HOME_FT":{"odds":2.9,"origin":"bsd_consensus",
                      "updated_at":when.isoformat()}},{}
        with patch.dict(os.environ,{"PINNWIRE_API_KEY":"test-key"}):
            router=OddsRouter(bsd,session=session,order=("pinnwire","goaldir"))
            q,diag=router.fetch(EVENT,NOW,"1X2_HOME_FT")
        self.assertEqual(q["1X2_HOME_FT"]["odds"],1.52)
        self.assertEqual(q["1X2_HOME_FT"]["quote_timestamp_type"],"provider_snapshot")
        self.assertEqual(diag["provider"],"pinnwire")
        self.assertEqual(diag["verified_provider_count"],1)
        self.assertEqual(diag["provider_priority_rank"],SOURCE_TIERS["pinnwire"])
        self.assertEqual(session.calls,1)

    def test_slow_generation_uses_actual_request_clock(self):
        later=NOW+timedelta(minutes=10)
        session=FakeSession([FakeResponse(200,{
            "generated_at":later.isoformat(),
            "events":[{
                **ROW,"event_type":"prematch","is_have_odds":True,
                "periods":{"num_0":{"money_line":{"home":1.51}}}
            }]
        })])
        with patch.dict(os.environ,{"PINNWIRE_API_KEY":"test-key"}):
            router=OddsRouter(lambda ev,when: ({},{}),session=session,
                order=("pinnwire",),clock=lambda:later)
            quotes,diag=router.fetch(EVENT,NOW,"1X2_HOME_FT")
        self.assertEqual(quotes["1X2_HOME_FT"]["odds"],1.51)
        self.assertEqual(diag["provider"],"pinnwire")
        self.assertEqual(quotes["1X2_HOME_FT"]["updated_at"],later.isoformat())

    def test_stale_pinnwire_snapshot_falls_back(self):
        stale=(NOW-timedelta(minutes=5)).isoformat()
        session=FakeSession([FakeResponse(200,{
            "generated_at":stale,
            "events":[{**ROW,"event_type":"prematch",
                       "periods":{"num_0":{"money_line":{"home":1.42}}}}]
        })])
        with patch.dict(os.environ,{"PINNWIRE_API_KEY":"test-key"}):
            router=OddsRouter(lambda ev,at:({"1X2_HOME_FT":{
                "odds":1.39,"origin":"bsd_consensus","updated_at":at.isoformat()}},{}),
                session=session,order=("pinnwire","goaldir"))
            q,diag=router.fetch(EVENT,NOW,"1X2_HOME_FT")
        self.assertEqual(q["1X2_HOME_FT"]["odds"],1.39)
        self.assertEqual(diag["provider"],"goaldir")

    def test_stale_higher_quote_cannot_override_fresh_bsd(self):
        stale=(NOW-timedelta(hours=3)).isoformat()
        session=FakeSession([FakeResponse(200,{"matches":[{
            **ROW,"in_play":False,"polled_at":stale,
            "quotes":[{"group_name":"Match Result","label":"Real Madrid",
                       "odds_dec":9.99}]}]})])
        with patch.dict(os.environ,{"MOVIODDS_ENABLE":"1"}):
            router=OddsRouter(lambda ev,now:({"1X2_HOME_FT":{
                "odds":1.36,"origin":"bsd_consensus",
                "updated_at":now.isoformat()}},{}),
                session=session,order=("goaldir","moviodds"))
            out,diag=router.fetch(EVENT,NOW,market_code="1X2_HOME_FT")
        self.assertEqual(out["1X2_HOME_FT"]["odds"],1.36)
        self.assertEqual(diag["provider"],"goaldir")
        self.assertEqual(diag["verified_provider_count"],1)

    def test_untimed_external_quote_is_not_a_verified_offer(self):
        session=FakeSession([FakeResponse(200,{"matches":[{
            **ROW,"in_play":False,
            "quotes":[{"group_name":"Match Result","label":"Real Madrid",
                       "odds_dec":8.88}]}]})])
        with patch.dict(os.environ,{"MOVIODDS_ENABLE":"1"}):
            router=OddsRouter(lambda ev,now:({},{}),
                session=session,order=("goaldir","moviodds"))
            out,diag=router.fetch(EVENT,NOW,market_code="1X2_HOME_FT")
        self.assertEqual(out,{})
        self.assertEqual(diag["verified_provider_count"],0)

    def test_fifteen_minute_kickoff_gate(self):
        self.assertTrue(match_fixture({**ROW,"kickoff_utc":"2026-10-14T19:15:00Z"},EVENT))
        self.assertFalse(match_fixture({**ROW,"kickoff_utc":"2026-10-14T19:16:00Z"},EVENT))

    def test_public_board_american_odds_and_market_identity(self):
        from bsd_odds_fallback import from_oddslink_public, american_to_decimal
        fixture={**ROW,"home_team":"Real Madrid","away_team":"FC Barcelona",
          "bookmakers":[
            {"key":"book_a","kind":"sportsbook","last_update":NOW.isoformat(),
             "markets":{"h2h":[{"name":"Real Madrid","price":-200},{"name":"Draw","price":+220}],
                        "totals":[{"name":"Over","point":2.5,"price":+105}]}},
            {"key":"book_b","kind":"sportsbook","last_update":NOW.isoformat(),
             "markets":{"h2h":[{"name":"Real Madrid","price":-150}]}},
            {"key":"exchange","kind":"exchange","last_update":NOW.isoformat(),
             "markets":{"h2h":[{"name":"Real Madrid","price":+900}]}}
          ]}
        self.assertEqual(american_to_decimal(-200),1.5)
        self.assertEqual(american_to_decimal(150),2.5)
        self.assertIsNone(american_to_decimal(1.85))
        q=from_oddslink_public(fixture,NOW,"1X2_HOME_FT")
        self.assertEqual(set(q),{"1X2_HOME_FT"})
        self.assertAlmostEqual(q["1X2_HOME_FT"]["odds"],1+100/150,places=4)
        self.assertEqual(q["1X2_HOME_FT"]["bookmaker"],"book_b")

    def test_public_board_rejects_missing_quote_timestamp(self):
        from bsd_odds_fallback import from_oddslink_public
        fixture={"home_team":"Real Madrid","away_team":"FC Barcelona",
          "bookmakers":[{"key":"book_a","kind":"sportsbook","last_update":None,
          "markets":{"h2h":[{"name":"Real Madrid","price":-200}]}}]}
        self.assertEqual(from_oddslink_public(fixture,NOW),{})

    def test_public_board_fetch_router(self):
        session=FakeSession([FakeResponse(200,{"fixtures":[{
             "home_team":"Real Madrid","away_team":"FC Barcelona",
             "commence_time":EVENT["event_date"],"in_play":False,
             "bookmakers":[{"key":"book_a","kind":"sportsbook","last_update":NOW.isoformat(),
             "markets":{"totals":[{"name":"Over","point":2.5,"price":-110}]}}]
        }]})])
        router=OddsRouter(lambda ev,at: ({},{}),session=session,order=("oddslink_public",))
        q,diagnostic=router.fetch(EVENT,NOW,market_code="OU_2.5_OVER_FT")
        self.assertAlmostEqual(q["OU_2.5_OVER_FT"]["odds"],1.90909,places=4)
        self.assertEqual(diagnostic["provider"],"oddslink_public")

    def test_external_first_default_order(self):
        from bsd_odds_fallback import ORDER
        self.assertEqual(ORDER, ("pinnwire", "oddslink", "oddslink_public",
                                  "moviodds", "goaldir", "oddsharvester"))

    def test_oddslink_epl_feed_skipped_for_unknown_league(self):
        session=FakeSession([])
        router=OddsRouter(lambda event,at: ({},{}),session=session,order=("oddslink",))
        with patch.dict(os.environ,{"ODDSLINK_API_KEY":"test-key"}):
            result,diag=router.fetch(EVENT,NOW,market_code="1X2_HOME_FT")
        self.assertEqual(result,{})
        self.assertEqual(session.calls,0)
        self.assertEqual(diag["verified_provider_count"],0)

    def test_all_unavailable_returns_empty_not_fake_quote(self):
        router=OddsRouter(lambda ev,at: ({},{}),order=("goaldir",))
        result,diag=router.fetch(EVENT,NOW)
        self.assertEqual(result,{})
        self.assertIsNone(diag["provider"])


if __name__ == "__main__": unittest.main()
