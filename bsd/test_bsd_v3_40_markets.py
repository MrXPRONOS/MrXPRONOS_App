"""Regression tests for the 40-market shadow prototype. No API or production feed."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from bsd_v2_core import score_matrix
from bsd_v3_40_markets import SPECS, BY_KEY, probabilities, result, settle_market
from bsd_v3_40_engine import rank_markets, enrich_all_markets
from bsd_v3_40_calibration import from_sums, GoalCalibration
from datetime import datetime,timezone

class V3MarketsTests(unittest.TestCase):
    def setUp(self):
        self.matrix=score_matrix(1.4,1.1,rho=-0.02)
        self.rows={r["key"]:r for r in probabilities(self.matrix)}
    def test_40_exact(self):
        self.assertEqual(len(SPECS),40)
        self.assertEqual(set(s.number for s in SPECS),set(range(1,41)))
        self.assertEqual(len(self.rows),40)
    def test_full_probability_partition(self):
        for row in self.rows.values():
            self.assertAlmostEqual(sum(row[x] for x in ("probability","push_probability","lose_probability")),1.,places=7)
    def test_coherent_totals(self):
        self.assertAlmostEqual(self.rows["TOTAL_OVER_25"]["probability"]+self.rows["TOTAL_UNDER_25"]["probability"],1.,places=7)
        self.assertGreaterEqual(self.rows["TOTAL_OVER_05"]["probability"],self.rows["TOTAL_OVER_15"]["probability"])
        self.assertGreaterEqual(self.rows["TOTAL_OVER_15"]["probability"],self.rows["TOTAL_OVER_25"]["probability"])
        self.assertAlmostEqual(self.rows["BTTS_YES"]["probability"]+self.rows["BTTS_NO"]["probability"],1.,places=7)
    def test_coherent_outcomes(self):
        p1=self.rows["RESULT_HOME"]["probability"]
        px=self.rows["RESULT_DRAW"]["probability"]
        p2=self.rows["RESULT_AWAY"]["probability"]
        self.assertAlmostEqual(p1+px+p2,1.,places=7)
        self.assertAlmostEqual(self.rows["DC_1X"]["probability"],p1+px,places=7)
        self.assertAlmostEqual(self.rows["DC_X2"]["probability"],p2+px,places=7)
        self.assertAlmostEqual(self.rows["DNB_HOME"]["push_probability"],px,places=7)
    def test_handicap(self):
        self.assertEqual(result("HANDICAP_HOME_P15",0,1),"win")
        self.assertEqual(result("HANDICAP_HOME_P15",0,2),"lose")
        self.assertEqual(result("HANDICAP_AWAY_P25",3,1),"win")
        self.assertEqual(result("HANDICAP_AWAY_P25",4,1),"lose")
    def test_dnb(self):
        self.assertEqual(result("DNB_HOME",1,1),"push")
        self.assertEqual(result("DNB_HOME",2,1),"win")
        self.assertEqual(result("DNB_HOME",0,1),"lose")
        self.assertAlmostEqual(self.rows["DNB_HOME"]["fair_odds"],
            (1-self.rows["DNB_HOME"]["push_probability"])/self.rows["DNB_HOME"]["probability"],places=5)
    def test_win_to_nil(self):
        self.assertEqual(result("WIN_TO_NIL_HOME",2,0),"win")
        self.assertEqual(result("WIN_TO_NIL_HOME",2,1),"lose")
        self.assertEqual(result("CLEAN_HOME",0,0),"win")
        self.assertEqual(result("BTTS_YES",2,0),"lose")
    def test_time_and_cancel(self):
        self.assertEqual(settle_market("DNB_HOME",status="postponed"),"pending")
        self.assertEqual(settle_market("DNB_HOME",status="cancelled"),"void")
        self.assertEqual(settle_market("DNB_HOME",status="finished",home_score=1,away_score=1),"push")
    def test_never_rank_without_verified_quoted_odds_and_holdout(self):
        self.assertEqual(rank_markets(list(self.rows.values()),{},now=datetime.now(timezone.utc)),[])
    def test_all_40_confidence_independent_of_quote(self):
        expected={"home_recent_matches":10,"away_recent_matches":8,"league_samples":120,
                  "home_venue_matches":5,"away_venue_matches":4}
        rows=enrich_all_markets(list(self.rows.values()),expected)
        self.assertEqual(len(rows),40)
        for item in rows:
            self.assertAlmostEqual(item["confidence_pct"],round(item["probability"]*100,1))
            self.assertFalse(item["confidence_calibrated"])
            self.assertEqual(item["market_status"],"model_option_unverified")

    def test_multiple_qualified_markets_are_not_capped(self):
        now=datetime.now(timezone.utc)
        quotes={}
        checks={}
        for key in ("TOTAL_OVER_15","TOTAL_UNDER_45","DC_1X"):
            quotes[key]={"verified":True,"estimated":False,"source":"bsd_consensus",
                         "odds":99,"captured_at":now.isoformat()}
            checks[key]={"samples":200,"test_brier":0.1,"baseline_brier":0.2,
                         "chronological_holdout":True}
        picks=rank_markets(list(self.rows.values()),quotes,now=now,validation=checks)
        self.assertEqual(len(picks),3)

    def test_goal_calibration_preserves_all_market_coherence(self):
        m=from_sums(n=400,actual_home=580,actual_away=440,
                    predicted_home=600,predicted_away=400)
        home,away=m.apply(1.4,1.1)
        self.assertEqual(len(probabilities(score_matrix(home,away))),40)
        p={x["key"]:x["probability"] for x in probabilities(score_matrix(home,away))}
        self.assertAlmostEqual(p["RESULT_HOME"]+p["RESULT_DRAW"]+p["RESULT_AWAY"],1,places=7)
        self.assertAlmostEqual(p["DC_1X"],p["RESULT_HOME"]+p["RESULT_DRAW"],places=7)
        self.assertTrue(.88<=m.home_scale<=1.12)
        self.assertTrue(.88<=m.away_scale<=1.12)
        self.assertEqual(GoalCalibration.from_dict(m.to_dict()).trained,400)

    def test_goal_calibration_small_sample_is_identity(self):
        m=from_sums(n=20,actual_home=40,actual_away=30,
                    predicted_home=20,predicted_away=20)
        self.assertEqual(m.apply(1.3,1.1),(1.3,1.1))
        self.assertFalse(m.applied)

    def test_invalid_distribution(self):
        with self.assertRaises(ValueError):
            probabilities({(0,0):.5})

if __name__=="__main__":
    unittest.main()
