"""No-vig calibration diagnostic must not mix books or missing outcomes."""
import unittest
from datetime import datetime,timedelta,timezone
from bsd_v2_market_no_vig import no_vig_probability

T=datetime(2026,11,2,20,tzinfo=timezone.utc)
K=T+timedelta(hours=3)

def quote(p,book='bookA',origin='pinnwire'):
 return {'odds':p,'bookmaker':book,'origin':origin,
         'captured_at':T.isoformat(),
         'updated_at':(T-timedelta(minutes=20)).isoformat(),
         'quote_timestamp_verified':True}

class VigRemovalTests(unittest.TestCase):
 def test_two_sided_btts_with_margin(self):
  q={'BTTS_YES_FT':quote(1.9),'BTTS_NO_FT':quote(1.9)}
  p,reason=no_vig_probability('BTTS_YES_FT',q,captured=T,kickoff=K)
  self.assertEqual(reason,'ok')
  self.assertAlmostEqual(p['no_vig_probability'],.5)
  self.assertAlmostEqual(p['overround'],2/1.9-1,places=5)
 def test_three_sided_full_time(self):
  q={'1X2_HOME_FT':quote(2),'1X2_DRAW_FT':quote(4),
     '1X2_AWAY_FT':quote(4)}
  p,reason=no_vig_probability('1X2_HOME_FT',q,captured=T,kickoff=K)
  self.assertEqual(reason,'ok')
  self.assertAlmostEqual(p['no_vig_probability'],.5)
 def test_refuse_missing_complement(self):
  p,reason=no_vig_probability('BTTS_YES_FT',{'BTTS_YES_FT':quote(1.9)},captured=T,kickoff=K)
  self.assertIsNone(p)
  self.assertEqual(reason,'missing_complementary_market_quote')
 def test_no_mix_best_prices_different_bookmakers(self):
  q={'BTTS_YES_FT':quote(1.9,'bookA'),'BTTS_NO_FT':quote(1.9,'bookB')}
  p,reason=no_vig_probability('BTTS_YES_FT',q,captured=T,kickoff=K)
  self.assertIsNone(p)
  self.assertEqual(reason,'complements_from_different_bookmakers')
 def test_no_implied_probability_for_refund_market(self):
  p,reason=no_vig_probability('DRAW_NO_BET_HOME_FT',{},captured=T,kickoff=K)
  self.assertIsNone(p)
  self.assertEqual(reason,'no_complete_outcome_group_supported')
if __name__=='__main__': unittest.main()
