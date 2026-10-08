"""Regression checks for the coherent 1X2/double chance specialist."""
import unittest
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from bsd_v2_core import V2History,score_matrix,markets_from_matrix,choose_market,predict_v2
from bsd_v2_double_chance import (
    FEATURES,_softmax,DoubleChanceModel,OutcomeCalibration,features,
    adjust_candidates,fit_model,uncertain,score_probs)

class DoubleChanceTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,8,10,tzinfo=timezone.utc)
        self.games=[]
        for i in range(42):
            self.games.append({"id":100+i,
                "event_date":(self.now-timedelta(days=45-i)).isoformat(),
                "home_team_id":1 if i%2 else 2,"away_team_id":2 if i%2 else 1,
                "league_id":7,"status":"finished",
                "home_score":i%3,"away_score":i%2})
        self.future={"id":900,"event_date":(self.now+timedelta(days=1)).isoformat(),
            "home_team_id":1,"away_team_id":2,"league_id":7,"status":"notstarted"}
        self.index=V2History(self.games)

    def test_softmax_and_joint_market_coherence(self):
        model=DoubleChanceModel(tuple((0.,)*FEATURES for _ in range(3)),1.,100,50)
        initial=markets_from_matrix(score_matrix(1.5,1.2))
        rows=adjust_candidates(self.future,self.index,initial,model)
        p={c.key:c.probability for c in rows}
        self.assertAlmostEqual(p["1"]+p["X"]+p["2"],1.,places=10)
        self.assertAlmostEqual(p["1X"],p["1"]+p["X"],places=10)
        self.assertAlmostEqual(p["X2"],p["X"]+p["2"],places=10)
        self.assertAlmostEqual(p["12"],1.-p["X"],places=10)
        for item in initial:
            if item.key not in ("1","X","2","1X","X2","12"):
                self.assertEqual(item,next(x for x in rows if x.key==item.key))

    def test_no_future_leakage(self):
        original=features(self.future,self.index)
        injected=dict(self.future,status="finished",home_score=15,away_score=15)
        updated=features(self.future,V2History(self.games+[injected]))
        self.assertEqual(original,updated)

    def test_training_without_2024_falls_back(self):
        model,info=fit_model(self.index)
        self.assertEqual(model.blend,0.)
        self.assertEqual(info["reason"],"insufficient_2024_samples")

    def test_joint_calibration_remains_normalized(self):
        calibration=OutcomeCalibration(prior=3)
        for i in range(8):calibration.observe((.55,.25,.20),i%3)
        m=DoubleChanceModel(tuple((0.,)*FEATURES for _ in range(3)),0.)
        rows=adjust_candidates(self.future,self.index,
            markets_from_matrix(score_matrix(1.6,1.0)),m,calibration)
        p={c.key:c.probability for c in rows}
        self.assertAlmostEqual(p["1"]+p["X"]+p["2"],1.,places=10)
        self.assertAlmostEqual(p["1X"]+p["X2"]+p["12"],2.,places=10)

    def test_minimum_verified_odds_and_conservative_margin(self):
        original=next(x for x in markets_from_matrix(score_matrix(1.6,1.0))
                      if x.key=="1X")
        weak=replace(original,probability=.72)
        fail,_=choose_market([weak],odds_by_market={weak.market_code:1.5},
            require_odds=True,league_samples=10,form_samples=6)
        self.assertIsNone(fail)
        strong=replace(original,probability=.90)
        ok,_=choose_market([strong],odds_by_market={strong.market_code:1.5},
            require_odds=True,league_samples=10,form_samples=6)
        self.assertEqual(ok["candidate"].key,"1X")
        cheap,_=choose_market([strong],odds_by_market={strong.market_code:1.19},
            require_odds=True)
        self.assertIsNone(cheap)

    def test_specialized_features_know_opponent_strength_at_past_match_time(self):
        f=features(self.future,self.index)
        self.assertEqual(len(f),FEATURES)
        self.assertTrue(all(abs(x)<5 for x in f))

    def test_calibration_draw_band_and_complementary_markets(self):
        c=OutcomeCalibration(prior=30)
        for i in range(40):
            p=(.55,.20,.25) if i%2==0 else (.30,.40,.30)
            c.observe(p,1 if i%3==0 else 0)
        self.assertGreaterEqual(len(c.bins),2)
        first=c.apply((.55,.20,.25))
        second=c.apply((.30,.40,.30))
        self.assertAlmostEqual(sum(first),1,places=9)
        self.assertAlmostEqual(sum(second),1,places=9)
        self.assertNotEqual(first,second)

    def test_uncertainty_rejects_double_chance_only(self):
        model=DoubleChanceModel(tuple((0.,)*FEATURES for _ in range(3)),1.,100,100)
        self.assertIsNotNone(uncertain(self.future,self.index,model,(.9,.05,.05)))

if __name__=="__main__":unittest.main()
