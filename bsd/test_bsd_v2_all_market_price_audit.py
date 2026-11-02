"""Off-line all-market coverage and price provenance tests."""
import unittest
from unittest.mock import patch
from datetime import datetime,timedelta,timezone

from bsd_v2_all_market_price_audit import (
    OLD_KEYS,CATALOG_KEYS,ExperimentalCalibrator,_model_price,all_markets_for_fixture,
)
from bsd_v2_odds_comparison_all_markets import quote_gap,aggregate,SUPPORTED_NATIVE_CODES
from bsd_v2_market_expansion import ALL_KEYS
from bsd_v2_odds_comparison import valid_independent_quote

NOW=datetime(2026,11,2,12,tzinfo=timezone.utc)
KICKOFF=NOW+timedelta(hours=2)

class OldCal:
    outcome_calibration=None
    def score(self,c):
        return .75*c.probability,c.probability,15

class AllMarketTests(unittest.TestCase):
    def test_catalog_has_16_plus_9_different_codes(self):
        self.assertEqual(len(OLD_KEYS),16)
        self.assertEqual(len(ALL_KEYS),9)
        self.assertEqual(len(CATALOG_KEYS),25)
        self.assertEqual(len(set(CATALOG_KEYS)),25)
    def test_low_model_probability_retains_research_price(self):
        price,status=_model_price('X','1X2_DRAW_FT',.24,.22,now=NOW)
        self.assertEqual(status,'research_only')
        self.assertGreater(price['odds'],1.20)
        self.assertFalse(price['publishable_as_indicative_price'])
    def test_model_very_high_probability_still_recorded_below_min_site_odds(self):
        price,status=_model_price('AH_HOME_PLUS_15','ASIAN_HANDICAP_HOME_+1.5_FT',.95,.93,now=NOW)
        self.assertEqual(status,'research_only')
        self.assertGreater(price['odds'],1.01)
        self.assertLess(price['odds'],1.20)
    def test_compare_sub120_research_quote_when_provider_offers_it(self):
        q={'origin':'pinnwire','odds':1.10,'bookmaker':'Pinnacle',
            'updated_at':(NOW-timedelta(minutes=1)).isoformat(),
            'captured_at':NOW.isoformat(),'quote_timestamp_verified':True}
        row,status=quote_gap({'indicative_odds':1.09},q,'ASIAN_HANDICAP_HOME_+1.5_FT',NOW,KICKOFF)
        self.assertEqual(status,'ok')
        self.assertEqual(row['model_price'],1.09)
        self.assertEqual(row['external_price'],1.10)
    def test_missing_quote_timestamp_cannot_create_pair(self):
        q={'origin':'pinnwire','odds':1.7}
        row,status=quote_gap({'indicative_odds':1.35},q,'OU_2.5_OVER_FT',NOW,KICKOFF)
        self.assertIsNone(row)
        self.assertEqual(status,'incomplete_quote')
    def test_new_provider_adapters_unimplemented_not_fake_comparisons(self):
        self.assertNotIn('DRAW_NO_BET_HOME_FT',SUPPORTED_NATIVE_CODES)
        self.assertNotIn('TOTAL_UNDER_1.5_HT',SUPPORTED_NATIVE_CODES)
    def test_no_bets_selected_filter_on_catalogue(self):
        fixture={'id':123,'event_date':KICKOFF.isoformat(),'status':'notstarted'}
        features={'home':1.4,'away':1.1,'league_samples':90,
                  'home_recent_matches':12,'away_recent_matches':12}
        with patch('bsd_v2_all_market_price_audit.estimate_goals',return_value=(features,'ok')),\
             patch('bsd_v2_all_market_price_audit.adjust_totals',side_effect=lambda e,i,rows,m:rows),\
             patch('bsd_v2_all_market_price_audit.btts_candidates',side_effect=lambda e,i,rows,m:rows),\
             patch('bsd_v2_all_market_price_audit.adjust_dc',side_effect=lambda e,i,rows,m,cal:rows):
            rows=all_markets_for_fixture(fixture,None,rho=0,calibration=OldCal(),
                totals=None,btts=None,dc=None,new_calibration=ExperimentalCalibrator(),
                ht_ratio=None,now=NOW)
        self.assertEqual(len(rows),25)
        self.assertEqual({m['key'] for m in rows},set(CATALOG_KEYS))
        self.assertIsNone(next(m for m in rows if m['key']=='HT_UNDER_15')['indicative_odds'])
        self.assertTrue(any(m['pricing_status']=='research_only' for m in rows))
    def test_aggregate_empty_and_nonempty(self):
        self.assertEqual(aggregate([])['n'],0)
        self.assertEqual(aggregate([{'absolute_difference':.1,'abs_relative_pct':5.}])['n'],1)

if __name__=='__main__':unittest.main()
