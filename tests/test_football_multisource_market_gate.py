import unittest
from datetime import datetime,timedelta,timezone
from scripts.football_multisource_market_gate import selected_quote,verify_selected_markets

NOW=datetime(2026,10,15,12,tzinfo=timezone.utc)

def choice():
    return {
        "key":"OVER_25","name":"Over 2.5","market":"over_under",
        "outcome":"over","internal_market_code":"OU_2.5_OVER_FT",
        "market_code":"OU_2.5_OVER_FT",
        "probability":0.82,"conservative_probability":0.76,
    }

def prices(delta_minutes=7,*,market="OU_2.5_OVER_FT",source="bsd_consensus"):
    return {market:{
        "odds":1.81,"origin":source,"bookmaker":"consensus",
        "updated_at":(NOW-timedelta(minutes=delta_minutes)).isoformat()
    }}

class MarketWitnessTests(unittest.TestCase):
    def test_selected_market_has_original_verified_quote(self):
        selected,why=selected_quote(choice(),prices(),at=NOW)
        self.assertEqual(why,"verified_real_consensus_market")
        self.assertEqual(selected["odds_source"],"bsd_consensus")
        self.assertEqual(selected["internal_market_code"],"OU_2.5_OVER_FT")
        self.assertFalse(selected["estimated_odds"])

    def test_other_market_never_substitutes_for_selected_one(self):
        selected,why=selected_quote(choice(),prices(market="OU_1.5_OVER_FT"),at=NOW)
        self.assertIsNone(selected)
        self.assertEqual(why,"selected_market_not_quoted")

    def test_stale_or_future_quote_never_qualifies(self):
        for age in (121,-1):
            with self.subTest(age=age):
                selected,why=selected_quote(choice(),prices(delta_minutes=age),at=NOW)
                self.assertIsNone(selected)
                self.assertEqual(why,"selected_market_quote_stale_or_untimed")

    def test_only_real_consensus_pricing_is_allowed(self):
        selected,why=selected_quote(choice(),prices(source="mrxpronos_model"),at=NOW)
        self.assertIsNone(selected)
        self.assertEqual(why,"selected_market_not_quoted")
        selected,why=selected_quote(choice(),prices(source="bsd_bookmaker"),at=NOW)
        self.assertIsNone(selected)
        self.assertEqual(why,"selected_market_not_quoted")

    def test_untrusted_production_feed_or_more_than_eight_events_rejected(self):
        with self.assertRaises(ValueError):
            verify_selected_markets([],[],{"source":"sportdata","matches":[]},at=NOW)
        with self.assertRaises(ValueError):
            verify_selected_markets([],[(None,None,{})]*9,
                {"source":"bsd","matches":[],"performance_tracker":{}},at=NOW)

if __name__=="__main__":
    unittest.main()
