import unittest
from bsd_v2_market_expansion import ALL_KEYS,candidates,outcome,half_time_share,first_half_scores

class MarketExpansionTest(unittest.TestCase):
 def setUp(self):
  self.rows={v.key:v for v in candidates({(0,0):.1,(1,0):.2,(0,1):.3,(2,1):.1,(0,2):.1,(2,2):.2})}
 def test_all_nine_keys(self): self.assertEqual(set(self.rows),set(ALL_KEYS))
 def test_team_goals(self):
  self.assertAlmostEqual(self.rows['HOME_OVER_05'].probability,.5)
  self.assertAlmostEqual(self.rows['AWAY_OVER_05'].probability,.7)
  self.assertAlmostEqual(self.rows['HOME_UNDER_15'].probability,.7)
 def test_handicaps(self):
  self.assertAlmostEqual(self.rows['AH_HOME_PLUS_15'].probability,.9)
  self.assertAlmostEqual(self.rows['AH_AWAY_PLUS_15'].probability,1.)
  self.assertEqual(outcome('AH_HOME_PLUS_15',0,2),0)
  self.assertEqual(outcome('AH_HOME_PLUS_15',0,1),1)
 def test_refund(self):
  self.assertEqual(outcome('DNB_HOME',1,1),-1)
  self.assertEqual(outcome('DNB_HOME',2,1),1)
  self.assertEqual(outcome('DNB_AWAY',2,1),0)
  self.assertAlmostEqual(self.rows['DNB_HOME'].refund_probability,.3)
 def test_ht_missing_is_not_fabricated(self):
  self.assertIsNone(self.rows['HT_UNDER_15'].probability)
  self.assertIsNone(outcome('HT_UNDER_15',1,1))
  self.assertIsNone(first_half_scores({'home_score':2,'away_score':1}))
  self.assertIsNone(half_time_share([],min_matches=1)[0])
  self.assertEqual(outcome('HT_UNDER_15',2,1,half_time=(1,0)),1)

if __name__=='__main__':unittest.main()
