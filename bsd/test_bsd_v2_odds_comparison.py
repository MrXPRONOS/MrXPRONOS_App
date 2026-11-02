"""Tests de comparaison de cotes, sans requêtes web ni données privées."""
import unittest
from datetime import datetime,timedelta,timezone

from bsd_v2_odds_comparison import (
    comparison, pure_model_price, summarize, valid_independent_quote, choose_upcoming,
)
from bsd_v2_estimated_odds import estimated_quote

NOW=datetime(2026,11,2,10,tzinfo=timezone.utc)
KICKOFF=NOW+timedelta(hours=3)

def fresh(origin="pinnwire", *, odds=1.38, updated=None, captured=None):
    at=captured or NOW
    return {"origin":origin,"odds":odds,
            "updated_at":(updated or (NOW-timedelta(minutes=11))).isoformat(),
            "captured_at":at.isoformat(),"bookmaker":"Independent Book",
            "quote_timestamp_verified":True}

class OddsComparisonTests(unittest.TestCase):
    def test_uses_actual_native_indicative_price(self):
        selection={"category":"pro","prediction":{
            "key":"1X","internal_market_code":"DC_1X_FT",
            "probability":.800,"conservative_probability":.785}}
        actual,reason=pure_model_price(selection,now=NOW)
        expected=estimated_quote({"key":"1X","market_code":"DC_1X_FT",
                                  "probability":.800,"conservative_probability":.785},{},now=NOW)
        self.assertEqual(reason,"ok_model_indicative")
        self.assertEqual(actual["odds"],expected["odds"])
        self.assertEqual(actual["odds_source"],"mrxpronos_model")
        self.assertEqual(actual["odds"],1.20)

    def test_model_estimate_under_minimum_is_not_compared(self):
        selection={"category":"pro","prediction":{
            "key":"1X","internal_market_code":"DC_1X_FT",
            "probability":.91,"conservative_probability":.88}}
        quote,reason=pure_model_price(selection,now=NOW)
        self.assertIsNone(quote)
        self.assertEqual(reason,"indicative_price_unavailable_or_below_120")

    def test_relative_difference_and_implied_probability(self):
        row,reason=comparison(1.2,fresh(odds=1.5),code="DC_1X_FT",
                               now=NOW,kickoff=KICKOFF)
        self.assertEqual(reason,"ok")
        self.assertAlmostEqual(row["absolute_difference"],.3)
        self.assertAlmostEqual(row["relative_difference_pct"],25.0)
        self.assertAlmostEqual(row["provider_implied_probability_pct"],66.667,places=2)
        self.assertAlmostEqual(row["model_implied_probability_pct"],83.333,places=2)

    def test_reject_stale_quote_even_when_price_present(self):
        q=fresh(updated=NOW-timedelta(hours=3))
        self.assertEqual(valid_independent_quote(q,code="DC_1X_FT",
                   now=NOW,kickoff=KICKOFF)[1],"stale_or_post_kickoff")

    def test_reject_future_quote_and_inplay(self):
        q=fresh(updated=NOW+timedelta(seconds=30))
        self.assertEqual(valid_independent_quote(q,code="DC_1X_FT",
                  now=NOW,kickoff=KICKOFF)[1],"stale_or_post_kickoff")
        self.assertEqual(valid_independent_quote(fresh(),
                  code="DC_1X_FT",now=NOW,kickoff=NOW)[1],"stale_or_post_kickoff")

    def test_reject_estimated_price_masquerading_as_provider(self):
        self.assertEqual(valid_independent_quote(fresh("mrxpronos_model"),
                         code="DC_1X_FT",now=NOW,kickoff=KICKOFF)[1],"unsupported_origin")

    def test_reject_unverified_timestamp(self):
        row=fresh();row["quote_timestamp_verified"]=False
        self.assertEqual(valid_independent_quote(row,code="DC_1X_FT",
                         now=NOW,kickoff=KICKOFF)[1],"timestamp_unverified")

    def test_reject_unknown_provider_and_missing_capture(self):
        row=fresh();row.pop("captured_at")
        self.assertEqual(valid_independent_quote(row,code="DC_1X_FT",
                         now=NOW,kickoff=KICKOFF)[1],"missing_utc_timestamps")

    def test_statistics_and_no_pairs(self):
        self.assertEqual(summarize([])["comparisons"],0)
        s=summarize([{"absolute_difference":.2,"absolute_relative_difference_pct":10.},
                     {"absolute_difference":-.1,"absolute_relative_difference_pct":5.}])
        self.assertEqual(s["comparisons"],2)
        self.assertEqual(s["pct_provider_above_model"],50.)

    def test_only_upcoming_pre_match_fixture(self):
        fixtures=[
         {"id":1,"event_date":(NOW+timedelta(minutes=5)).isoformat(),"status":"notstarted"},
         {"id":2,"event_date":(NOW+timedelta(hours=2)).isoformat(),"status":"notstarted"},
         {"id":3,"event_date":(NOW+timedelta(hours=2)).isoformat(),"status":"finished"},
         {"id":2,"event_date":(NOW+timedelta(hours=2)).isoformat(),"status":"notstarted"},
        ]
        chosen,n=choose_upcoming(fixtures,NOW,24,20)
        self.assertEqual(n,1)
        self.assertEqual(chosen[0]["id"],2)

if __name__=="__main__":unittest.main()
