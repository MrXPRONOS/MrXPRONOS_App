"""Regression tests: LightGBM, bivariate Poisson, ZIP and ensemble.

All synthetic records use normal BSD match fields. No actual historical
outcomes are published by these tests.
"""
import unittest
from datetime import datetime,timedelta,timezone
from dataclasses import replace

from bsd_v2_core import V2History,score_matrix,markets_from_matrix
from bsd_v2_btts import BTTSModel,btts_candidates,FEATURE_COUNT
from bsd_v2_btts_bivariate import joint_pmf,btts_probability,fit_bivariate
from bsd_v2_btts_zip import zip_pmf,zip_btts_probability,fit_zip
from bsd_v2_btts_lgbm import ml_features,fit_lightgbm
from bsd_v2_btts_ensemble import EnsembleBTTS,fit_ensemble


class FourBTTSModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start=datetime(2024,1,1,tzinfo=timezone.utc)
        cls.events=[]
        # 500 fixtures between Jan and late Aug. Repeating pairs provide
        # sufficient home, away and league history at each kick-off.
        teams=(11,22,33,44,55,66)
        for i in range(470):
            day=start+timedelta(hours=12*i)
            h=teams[i%6]
            a=teams[(i+1+(i%3))%6]
            if h==a:a=teams[(i+3)%6]
            cls.events.append({
                "id":100000+i,"event_date":day.isoformat(),"status":"finished",
                "home_team_id":h,"away_team_id":a,"league_id":9,
                "home_score":(i*7+3)%5,"away_score":(i*11+2)%4})
        cls.index=V2History(cls.events)
        cls.fixture={"id":999999,"event_date":(start+timedelta(days=260)).isoformat(),
                     "status":"notstarted","home_team_id":11,"away_team_id":22,
                     "league_id":9}

    def test_bivariate_distribution_normalization_and_btts(self):
        h,a,rho=1.5,1.25,.20
        total=sum(joint_pmf(i,j,h,a,rho) for i in range(16) for j in range(16))
        direct=sum(joint_pmf(i,j,h,a,rho) for i in range(1,16) for j in range(1,16))
        self.assertAlmostEqual(total,1.,places=7)
        self.assertAlmostEqual(direct,btts_probability(h,a,rho),places=6)
        baseline=(1-__import__("math").exp(-h))*(1-__import__("math").exp(-a))
        self.assertGreater(btts_probability(h,a,rho),baseline)
        self.assertAlmostEqual(joint_pmf(0,0,h,a,0),__import__("math").exp(-h-a))

    def test_zip_full_distribution_normalization_and_mean(self):
        p=[zip_pmf(k,1.4,.17) for k in range(25)]
        self.assertAlmostEqual(sum(p),1.,places=8)
        self.assertAlmostEqual(sum(k*pk for k,pk in enumerate(p)),1.4,places=6)
        self.assertGreater(p[0],__import__("math").exp(-1.4))
        self.assertAlmostEqual(zip_btts_probability(1.4,1.2,0.,0.),
           (1-__import__("math").exp(-1.4))*(1-__import__("math").exp(-1.2)))

    def test_feature_extraction_is_prematch_only(self):
        initial=ml_features(self.fixture,self.index)
        self.assertIsNotNone(initial)
        self.assertGreater(len(initial),30)
        future=dict(self.fixture,status="finished",home_score=19,away_score=19)
        self.assertEqual(initial,ml_features(self.fixture,V2History(self.events+[future])))

    def test_bivariate_and_zip_fit_pre2025_only(self):
        b=fit_bivariate(self.index,self.events,min_training=80)
        z=fit_zip(self.index,self.events,min_training=80)
        self.assertIsNotNone(b)
        self.assertIsNotNone(z)
        self.assertGreater(b.trained_fixtures,80)
        self.assertGreater(z.trained_fixtures,80)
        self.assertTrue(0<=b.predict({"home":1.7,"away":1.1})<=1)
        pp=z.predict(self.fixture,self.index)
        self.assertIsNotNone(pp)
        self.assertAlmostEqual(pp["btts_yes"],
            (1-pp["home_blank"])*(1-pp["away_blank"]))
        bad=dict(self.events[40],event_date="2026-03-04T18:00:00+00:00")
        with self.assertRaises(ValueError):
            fit_bivariate(self.index,[bad])
        with self.assertRaises(ValueError):
            fit_zip(self.index,[bad])

    def test_lightgbm_fit_and_probability(self):
        model=fit_lightgbm(self.index,self.events,min_training=80)
        if model is None:
            self.skipTest("LightGBM is not installed; acceptance workflow tests this")
        self.assertGreater(model.training_matches,80)
        p=model.predict(self.fixture,self.index)
        self.assertTrue(.01<=p<=.99)
        bad=dict(self.events[35],event_date="2026-02-02T00:00:00+00:00")
        with self.assertRaises(ValueError):
            fit_lightgbm(self.index,[bad],min_training=1)

    def test_ensemble_weights_and_market_isolation(self):
        class Constant:
            def __init__(self,p):self.p=p
            def predict(self,*args):return self.p
        class ZipConstant:
            def predict(self,*args):return {"btts_yes":.40}
        class Bivariate:
            def predict(self,*args):return .58
        ensemble=EnsembleBTTS(Constant(.70),Bivariate(),ZipConstant(),
                               (.5,.2,.2,.1),300,200,220)
        self.assertAlmostEqual(ensemble.predict(self.fixture,self.index,.60),.596)
        model=BTTSModel((.5,)+(0.,)*(FEATURE_COUNT-1),.5,300,200,
                        ensemble_model=ensemble)
        baselines=markets_from_matrix(score_matrix(1.5,1.2))
        result=btts_candidates(self.fixture,self.index,baselines,model)
        before={c.key:c for c in baselines}
        after={c.key:c for c in result}
        self.assertAlmostEqual(after["BTTS_YES"].probability+after["BTTS_NO"].probability,1.)
        for key in before:
            if not key.startswith("BTTS_"):
                self.assertEqual(after[key],before[key])

    def test_ensemble_split_rejects_train_validation_leak(self):
        bad=dict(self.events[50],event_date="2026-05-01T12:00:00+00:00")
        base=BTTSModel((0.,)*FEATURE_COUNT,0.)
        with self.assertRaises(ValueError):
            fit_ensemble(self.index,[bad],[],[],base)
        with self.assertRaises(ValueError):
            fit_ensemble(self.index,[],[bad],[],base)
        with self.assertRaises(ValueError):
            fit_ensemble(self.index,[],[],[bad],base)


if __name__=="__main__":
    unittest.main()
