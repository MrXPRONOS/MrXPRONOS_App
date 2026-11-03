"""Regression: no artificial price floor for high-confidence indicative odds."""
import unittest
from datetime import datetime,timezone
from bsd_v2_estimated_odds import (
    DEFAULT_OVERROUND,ESTIMATED_SOURCE,estimated_quote,
    model_reference_for_observation,price_selected_market,
)
NOW=datetime(2026,11,3,1,40,tzinfo=timezone.utc)
def selected(p):
    return {'key':'1X','market_code':'DC_1X_FT',
            'internal_market_code':'DC_1X_FT',
            'probability':p,'conservative_probability':p-.015}
class IndicativeFloorRegression(unittest.TestCase):
    def test_high_confidence_without_external_quote_is_not_floored(self):
        for p in (.79,.80,.81,.82,.83):
            with self.subTest(probability=p):
                self.assertIsNone(estimated_quote(selected(p),{},now=NOW))
                self.assertIsNone(price_selected_market(selected(p),{},now=NOW))
                observer=model_reference_for_observation(selected(p),now=NOW)
                self.assertIsNotNone(observer)
                self.assertLess(observer['odds'],1.20)
                self.assertFalse(observer['recommendation_eligible'])
                self.assertFalse(observer['telegram_eligible'])
    def test_lower_probability_keeps_full_six_percent_margin(self):
        for p in (.70,.74,.76):
            with self.subTest(probability=p):
                q=estimated_quote(selected(p),{},now=NOW)
                self.assertIsNotNone(q)
                self.assertEqual(q['origin'],ESTIMATED_SOURCE)
                self.assertEqual(q['overround_assumption'],DEFAULT_OVERROUND)
                self.assertAlmostEqual(q['odds'],round(1/(p*(1+DEFAULT_OVERROUND)),3))
                self.assertGreater(q['odds'],1.20)
    def test_genuine_external_prices_remain_unchanged(self):
        row=selected(.81)
        quote=price_selected_market(row,{'DC_1X_FT':{
              'origin':'bsd_consensus','odds':1.26,
              'updated_at':NOW.isoformat()}},now=NOW)
        self.assertEqual(quote['odds'],1.26)
        self.assertEqual(quote['odds_source'],'bsd_consensus')
        self.assertFalse(quote['estimated_odds'])
    def test_never_use_external_quote_as_model_price(self):
        row=selected(.80)
        quotes={'DC_1X_FT':{'origin':'bsd_consensus','odds':1.35}}
        self.assertIsNone(estimated_quote(row,quotes,now=NOW))
if __name__=='__main__':unittest.main()
