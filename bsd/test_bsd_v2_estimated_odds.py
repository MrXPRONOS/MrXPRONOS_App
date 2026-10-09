"""Vérifie la provenance et les calculs du fallback indicatif."""
import unittest
from datetime import datetime, timezone
from bsd_v2_estimated_odds import (
    reference_overround, estimated_quote, valid_standalone_prediction,
    ESTIMATED_SOURCE,
)

class IndicativeOddsTests(unittest.TestCase):
    def setUp(self):
        self.row={"key":"1X", "market_code":"DC_1X_FT",
                  "probability":0.76, "conservative_probability":0.73}
        self.now=datetime(2026,10,9,tzinfo=timezone.utc)

    def test_default_overround_is_explicit(self):
        margin,source=reference_overround({})
        self.assertEqual(margin,0.06)
        self.assertEqual(source,"hypothese_6pct")

    def test_complete_bsd_pair_calibrates_overround(self):
        quotes={"BTTS_YES_FT":{"odds":1.90,"origin":"bsd_consensus"},
                "BTTS_NO_FT":{"odds":1.90,"origin":"bsd_consensus"}}
        margin,source=reference_overround(quotes)
        self.assertAlmostEqual(margin,2/1.90-1)
        self.assertEqual(source,"bsd_marches_complets")

    def test_missing_market_produces_distinct_indicative_price(self):
        quote=estimated_quote(self.row,{},now=self.now)
        self.assertIsNotNone(quote)
        self.assertEqual(quote["origin"],ESTIMATED_SOURCE)
        self.assertTrue(quote["estimated"])
        self.assertLess(quote["odds"],quote["fair_odds"])
        site={"selection_key":"1X","odds":quote["odds"],
              "odds_source":ESTIMATED_SOURCE,"estimated_odds":True}
        self.assertTrue(valid_standalone_prediction(site))

    def test_never_overwrites_real_quote_on_same_market(self):
        existing={"DC_1X_FT":{"odds":1.23,"origin":"bsd_consensus"}}
        self.assertIsNone(estimated_quote(self.row,existing,now=self.now))

    def test_reject_untrusted_or_unsafe_pricing(self):
        self.assertFalse(valid_standalone_prediction({
            "selection_key":"1X","odds":1.45,"odds_source":ESTIMATED_SOURCE}))
        self.assertFalse(valid_standalone_prediction({
            "selection_key":"UNDER_45","odds":1.45,"odds_source":ESTIMATED_SOURCE,
            "estimated_odds":True}))
        self.assertIsNone(estimated_quote({**self.row,"conservative_probability":0.2},{},now=self.now))
        self.assertIsNone(estimated_quote({**self.row,"probability":float("nan")},{},now=self.now))

if __name__=="__main__":
    unittest.main()
