"""Research adapter market and snapshot identity unit tests."""
import unittest
from datetime import datetime,timedelta,timezone
from bsd_v2_odds_research_adapters import (
    from_pinnwire_extended, from_oddslink_public_extended,NEW_CODES
)
T=datetime(2026,11,3,12,tzinfo=timezone.utc)

class MarketAdapterTests(unittest.TestCase):
 def test_pinnwire_extended_full_time_and_first_half(self):
  fixture={'event_type':'prematch','status':'pending','is_have_odds':True,
    'periods':{'num_0':{
      'spreads':{'1.5':{'hdp':1.5,'home':1.28,'away':3.7},
                 '-1.5':{'hdp':-1.5,'home':3.3,'away':1.35},
                 '0':{'hdp':0,'home':1.72,'away':2.01}},
      'totals':{'2.5':{'points':2.5,'over':1.9,'under':1.9}},
      'team_total':{'home':{'points':.5,'over':1.22,'under':4.0}},
      'team_totals':{'home':{'1.5':{'points':1.5,'over':2.1,'under':1.65}},
                     'away':{'0.5':{'points':.5,'over':1.55,'under':2.5},
                             '1.5':{'points':1.5,'over':3.2,'under':1.38}}}},
      'num_1':{'totals':{'1.5':{'points':1.5,'under':1.66,'over':2.21}}}}}
  rows=from_pinnwire_extended(fixture,T,snapshot_generated_at=(T-timedelta(seconds=20)).isoformat())
  self.assertEqual(set(NEW_CODES)-set(rows),set())
  self.assertEqual(rows['ASIAN_HANDICAP_HOME_+1.5_FT']['odds'],1.28)
  self.assertEqual(rows['ASIAN_HANDICAP_AWAY_+1.5_FT']['odds'],1.35)
  self.assertEqual(rows['DRAW_NO_BET_HOME_FT']['odds'],1.72)
  self.assertEqual(rows['HOME_TEAM_OVER_0.5_FT']['odds'],1.22)
  self.assertEqual(rows['TOTAL_UNDER_1.5_HT']['odds'],1.66)
  self.assertEqual(rows['OU_2.5_UNDER_FT']['odds'],1.9)
  self.assertTrue(rows['TOTAL_UNDER_1.5_HT']['quote_timestamp_verified'])
 def test_pinnwire_stale_snapshot_rejected(self):
  fixture={'event_type':'prematch','periods':{'num_0':{'spreads':{'0':{'hdp':0,'home':1.5}}}}}
  rows=from_pinnwire_extended(fixture,T,snapshot_generated_at=(T-timedelta(minutes=10)).isoformat())
  self.assertEqual(rows,{})
 def test_pinnwire_no_implicit_halftime_from_fulltime(self):
  fixture={'event_type':'prematch','periods':{'num_0':{'totals':{'1.5':{'points':1.5,'under':1.3}}}}}
  rows=from_pinnwire_extended(fixture,T,snapshot_generated_at=(T-timedelta(seconds=20)).isoformat())
  self.assertNotIn('TOTAL_UNDER_1.5_HT',rows)
 def test_oddslink_public_spread_zero_and_plus_15(self):
  event={'home_team':'Arsenal','away_team':'Chelsea','bookmakers':[{
       'kind':'sportsbook','key':'bookA','last_update':(T-timedelta(minutes=5)).isoformat(),
       'markets':{'spreads':[{'name':'Arsenal','point':1.5,'price':-125},
                             {'name':'Chelsea','point':1.5,'price':-130},
                             {'name':'Arsenal','point':0,'price':+150},
                             {'name':'Chelsea','point':0,'price':-170}]}}]}
  rows=from_oddslink_public_extended(event,T)
  self.assertAlmostEqual(rows['ASIAN_HANDICAP_HOME_+1.5_FT']['odds'],1.8)
  self.assertAlmostEqual(rows['ASIAN_HANDICAP_AWAY_+1.5_FT']['odds'],1+100/130)
  self.assertAlmostEqual(rows['DRAW_NO_BET_HOME_FT']['odds'],2.5)
  self.assertEqual(rows['DRAW_NO_BET_HOME_FT']['bookmaker'],'bookA')
 def test_public_board_excludes_exchange_and_stale(self):
  event={'home_team':'Arsenal','away_team':'Chelsea','bookmakers':[{
     'kind':'exchange','key':'exchange','last_update':T.isoformat(),
     'markets':{'spreads':[{'name':'Arsenal','point':1.5,'price':-125}]}},
     {'kind':'sportsbook','key':'book','last_update':(T-timedelta(hours=5)).isoformat(),
     'markets':{'spreads':[{'name':'Chelsea','point':1.5,'price':-125}]}}]}
  self.assertFalse(from_oddslink_public_extended(event,T))
if __name__=='__main__': unittest.main()
