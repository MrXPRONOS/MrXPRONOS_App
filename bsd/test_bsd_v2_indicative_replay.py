"""Native BSD V2 indicative price acceptance tests for offline counterfactual."""
import unittest
from datetime import datetime,timezone
from bsd_v2_indicative_replay import model_only_publication,experimental_model_prediction
from bsd_v2_market_expansion import ExtendedMarket
NOW=datetime(2026,10,31,tzinfo=timezone.utc)

def prediction(key,p,conservative,category='pro',code=None):
 return {'category':category,'prediction':{'key':key,
  'internal_market_code':code or ('DC_1X_FT' if key=='1X' else 'ASIAN_HANDICAP_HOME_+1.5_FT'),
  'probability':p,'conservative_probability':conservative}}

class SiteIndicativeGateTests(unittest.TestCase):
 def test_same_native_price_as_production(self):
  out,reason=model_only_publication(prediction('1X',.80,.785),now=NOW)
  self.assertEqual(reason,'published_model_indicative')
  self.assertEqual(out['odds_source'],'mrxpronos_model')
  self.assertEqual(out['odds'],1.2)
  self.assertEqual(out['tier'],'INDICATIF')
 def test_high_probability_cannot_fake_minimum_odds(self):
  out,reason=model_only_publication(prediction('AH_HOME_PLUS_15',.90,.89),now=NOW)
  self.assertIsNone(out)
  self.assertEqual(reason,'chosen_market_unpriceable')
 def test_weak_conservative_probability_rejected(self):
  out,reason=model_only_publication(prediction('1X',.80,.77),now=NOW)
  self.assertIsNone(out)
  self.assertEqual(reason,'v21_model_confidence_or_price_below_floor')
 def test_simple_category_is_not_published(self):
  out,reason=model_only_publication(prediction('1X',.80,.785,category='simple'),now=NOW)
  self.assertIsNone(out)
  self.assertEqual(reason,'category_or_confidence_below_79')
 def test_probability_below_79_rejected(self):
  out,reason=model_only_publication(prediction('1X',.78,.777),now=NOW)
  self.assertIsNone(out)
  self.assertEqual(reason,'category_or_confidence_below_79')
 def test_new_market_retains_own_market_code_and_provenance(self):
  c=ExtendedMarket('HOME_OVER_05','HOME_TEAM_OVER_0.5_FT','team_goals',.80)
  feat={'league_samples':100,'home_recent_matches':12,'away_recent_matches':12,
        'home_venue_matches':5,'away_venue_matches':5}
  pred=experimental_model_prediction(c,.80,.785,feat)
  out,reason=model_only_publication(pred,now=NOW)
  self.assertEqual(reason,'published_model_indicative')
  self.assertEqual(out['market_code'],'HOME_TEAM_OVER_0.5_FT')
if __name__=='__main__': unittest.main()
