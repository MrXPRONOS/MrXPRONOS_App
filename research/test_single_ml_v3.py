"""Synthetic-only no-hindsight V3 algorithm and actual pipeline integration tests.

No bookmaker feed, historical downloads, ML V3 holdout or production access.
"""
import csv
import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import single_ml_v3 as v3
import single_ml_v2 as ml
from single_ml_v2_direct import train_direct_score, direct_grid
from single_ml_v2_hybrid import PastHybridForecast


class DummyGoalModel:
    def __init__(self,mean):self.mean=mean
    def predict(self,x):return np.asarray([self.mean]*len(x))


def quality(level):
    n=int(5*level)
    return {team:{"overall_last5":n,"venue_last5":n}
            for team in ("home","away")}


class ModelV3Tests(unittest.TestCase):
    def test_hist_v3_configuration_receives_strict_utc_cutoff(self):
        earlier=date(2026,1,20)
        with patch.object(v3,"fit_histgb",return_value=["h","a"]) as mocked:
            output=v3.fit_hist_v3([],asof=earlier,feature_count=130)
        self.assertEqual(output,["h","a"])
        self.assertEqual(mocked.call_args.kwargs["config"].half_life_days,180)
        self.assertEqual(mocked.call_args.kwargs["config"].max_rows,65000)
        self.assertEqual(mocked.call_args.kwargs["asof"],earlier)

    def test_sparse_form_shrinks_to_earlier_day_poisson_baseline(self):
        base=ml.poisson_grid(.5,2.0)
        features=np.zeros(len(ml.FEATURE_NAMES))
        models=[DummyGoalModel(1.2),DummyGoalModel(1.2)]
        full=v3.hist_v3_grid(models,features,base,form_samples=quality(1.))
        weak=v3.hist_v3_grid(models,features,base,form_samples=quality(0.))
        self.assertAlmostEqual(float(full.sum()),1,places=10)
        self.assertAlmostEqual(float(weak.sum()),1,places=10)
        self.assertGreater(float(weak[0,2]),float(full[0,2]))

    def test_calibration_p11_uses_only_prior_oos_dates(self):
        start=date(2026,1,1)
        prior=[v3.PastEleven(start+timedelta(days=i),str(i),.12,int(i%15==0)) for i in range(210)]
        factor=v3.eleven_multiplier(prior,asof=date(2026,8,1))
        self.assertGreaterEqual(factor,.75)
        self.assertLess(factor,1.)
        before=ml.poisson_grid(1.3,1.2)
        after=v3.calibrate_eleven_cell(before,factor)
        self.assertLess(float(after[1,1]),float(before[1,1]))
        self.assertAlmostEqual(float(after.sum()),1.,places=9)
        with self.assertRaisesRegex(ValueError,"current-day"):
            v3.eleven_multiplier(prior,asof=prior[-1].day)

    def test_p11_is_neutral_when_insufficient(self):
        p=[v3.PastEleven(date(2026,1,1),str(i),.12,0) for i in range(200)]
        self.assertEqual(v3.eleven_multiplier(p,asof=date(2026,2,2)),1.)

    def test_v3_hybrid_cannot_exploit_future_calibration(self):
        p=ml.poisson_grid(1,1)
        q=ml.poisson_grid(1.8,.7)
        prior=[PastHybridForecast(date(2026,1,1)+timedelta(days=i),
                  str(i),p,q,0,0) for i in range(25)]
        weight,setting=v3.hybrid_v3_weight(prior,asof=date(2026,2,1))
        self.assertEqual(weight,.35)
        self.assertFalse(setting.calibrated)
        with self.assertRaisesRegex(ValueError,"Future/current-day"):
            v3.hybrid_v3_weight(prior,asof=prior[-1].day)

    def test_hybrid_disagreement_attenuates_dc_weight_and_normalizes(self):
        a=ml.poisson_grid(.6,2.5)
        b=ml.poisson_grid(2.8,.3)
        p=v3.hybrid_v3_grid(a,b,dc_weight=.5)
        full=(a+b)/2
        self.assertAlmostEqual(float(p.sum()),1.,places=9)
        self.assertLess(float(np.abs(p-a).sum()),float(np.abs(full-a).sum()))
        with self.assertRaises(ValueError):
            v3.hybrid_v3_grid(a,b,dc_weight=-1)

    def test_class_imbalance_weights_and_longer_history_config(self):
        self.assertEqual(v3.DIRECT_CONFIG["max_rows"],65000)
        self.assertGreater(v3.DIRECT_CONFIG["class_weight_power"],0)
        b=ml.poisson_grid(1.3,1.1)
        rows=[]
        for i in range(90):
            vector=np.ones(len(ml.FEATURE_NAMES));vector[0]=i%7
            rows.append((vector,b,1 if i%4 else 2,1 if i%5 else 0))
        candidate=train_direct_score(rows,min_samples=30,max_iter=4,
                    max_leaf_nodes=4,class_weight_power=.25,prior_weight=0.)
        self.assertIsNotNone(candidate)
        grid=direct_grid(candidate,np.ones(len(ml.FEATURE_NAMES)),b)
        self.assertAlmostEqual(float(grid.sum()),1.,places=9)
        with self.assertRaisesRegex(ValueError,"class_weight_power"):
            train_direct_score(rows,min_samples=30,class_weight_power=1.0)

    def test_direct_prior_is_prior_only_and_normalized(self):
        prior=ml.poisson_grid(1.2,1.)
        another=ml.poisson_grid(2.3,.5)
        weight,fit=v3.direct_v3_prior([],asof=date(2026,2,1))
        self.assertEqual(weight,.20)
        self.assertFalse(fit.calibrated)
        observations=[v3.freeze_blend(date(2026,1,1)+timedelta(days=i),
                f"fixture{i}",prior,another,1,0) for i in range(25)]
        with self.assertRaisesRegex(ValueError,"Future/current-day"):
            v3.direct_v3_prior(observations,asof=observations[-1].day)
        merged=v3.hybrid_v3_grid(prior,another,dc_weight=.25)
        self.assertAlmostEqual(float(merged.sum()),1.,places=10)

    def test_both_v3_blend_calibrators_use_sufficient_prior_oos_history(self):
        # 150 genuinely prior-day frozen probability grids over 25 dates.
        first=date(2026,1,1)
        a=ml.poisson_grid(1.0,1.0)
        b=ml.poisson_grid(2.1,.55)
        earlier=[v3.freeze_blend(first+timedelta(days=i//6),
                   f"settled-{i}",a,b,0,0) for i in range(150)]
        asof=date(2026,2,1)
        hw,hs=v3.hybrid_v3_weight(earlier,asof=asof,previous=.35)
        dw,ds=v3.direct_v3_prior(earlier,asof=asof)
        self.assertTrue(hs.calibrated)
        self.assertTrue(ds.calibrated)
        self.assertEqual(hs.training_games,150)
        self.assertGreaterEqual(hs.training_days,12)
        self.assertGreaterEqual(hw,.10)
        self.assertLessEqual(hw,.65)
        self.assertGreaterEqual(dw,.05)
        self.assertLessEqual(dw,.65)
        # The fallback and calibrated weights use ONLY pre-asof observations.
        with self.assertRaisesRegex(ValueError,"Future/current-day"):
            v3.direct_v3_prior(earlier,asof=earlier[-1].day)

    def test_real_v3_histgb_fit_on_prior_dated_synthetic_matches(self):
        first=date(2026,1,1)
        records=[]
        for i in range(365):
            vec=np.zeros(len(ml.FEATURE_NAMES))
            vec[0]=.8+(i%7)*.08
            vec[1]=1.1+(i%9)*.06
            vec[7]=i%5
            records.append((vec,i%4,(i//3)%4,first+timedelta(days=i//20)))
        asof=date(2026,2,10)
        models=v3.fit_hist_v3(records,asof=asof,feature_count=len(ml.FEATURE_NAMES))
        self.assertEqual(len(models),2)
        predictions=[float(m.predict(records[-1][0][None,:])[0]) for m in models]
        self.assertTrue(all(np.isfinite(predictions)))
        self.assertTrue(all(x>0 for x in predictions))
        with self.assertRaisesRegex(ValueError,"Current/future"):
            v3.fit_hist_v3(records,asof=records[-1][3],
                           feature_count=len(ml.FEATURE_NAMES))

    def test_real_v3_direct_fits_large_synthetic_prior_cohort(self):
        base=ml.poisson_grid(1.2,1.)
        records=[]
        for i in range(850):
            vec=np.zeros(len(ml.FEATURE_NAMES))
            vec[0]=(i%9)/9.
            vec[5]=(i%7)/7.
            vec[16]=i%4
            records.append((vec,base,1 if i%5 else 2,1 if i%5 else 0))
        fitted=v3.fit_direct_v3(records)
        self.assertIsNotNone(fitted)
        self.assertEqual(fitted.samples,850)
        self.assertEqual(fitted.prior_weight,0.)
        p=v3.direct_v3_grid(fitted,records[-1][0],base,prior_weight=.2)
        self.assertEqual(p.shape,(11,11))
        self.assertAlmostEqual(float(p.sum()),1.,places=9)
        self.assertTrue(np.isfinite(p).all())

    def test_opt_in_pipeline_writes_three_v3_forecast_rows_and_prior_history(self):
        d0=date(2026,1,1)
        games=[]
        for d in range(3):
            for i in range(4):
                games.append(ml.Match(
                    key=f"synthetic:{d}:{i}",day=d0+timedelta(days=d),
                    league="SYNTHETIC_LEAGUE",
                    home=f"Home_{i}",away=f"Away_{i}",
                    hg=(i+d)%3,ag=(i+d+1)%3))
        p=ml.poisson_grid(1.4,1.)
        models=[DummyGoalModel(1.25),DummyGoalModel(.95)]
        with tempfile.TemporaryDirectory() as temp:
            with (patch.object(ml,"fit_hist_v3",return_value=models),
                  patch.object(ml,"fit_direct_v3",return_value=SimpleNamespace(samples=0)),
                  patch.object(ml,"direct_grid",return_value=p),
                  patch.object(ml,"direct_v3_grid",return_value=p)):
                ml.backtest(games,d0+timedelta(days=1),d0+timedelta(days=2),
                            temp,max_eval=0,retrain_days=30,auto_tune=False,
                            v3_models=True)
            report=json.loads((Path(temp)/"summary.json").read_text())
            self.assertTrue(report["v3_experimental_enabled"])
            self.assertEqual(report["v3_version"],v3.VERSION)
            for name in v3.V3_MODELS:
                self.assertEqual(report["results"][name]["n"],8)
            self.assertEqual(report["v3_hist_11_prior_rows"],8)
            with (Path(temp)/"all_predictions.csv").open(newline="") as f:
                entries=list(csv.DictReader(f))
            for name in v3.V3_MODELS:
                self.assertEqual(sum(row["model"]==name for row in entries),8)

    def test_v2_mode_is_independent_and_never_trains_v3(self):
        d0=date(2026,1,1)
        games=[ml.Match(key=f"x:{i}",day=d0+timedelta(days=i),
                   league="X",home="Team A",away="Team B",hg=1,ag=0)
               for i in range(2)]
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(ml,"fit_hist_v3") as not_called:
                ml.backtest(games,d0+timedelta(days=1),
                            d0+timedelta(days=1),temp,
                            auto_tune=False,v3_models=False)
            not_called.assert_not_called()
            r=json.loads((Path(temp)/"summary.json").read_text())
            self.assertFalse(r["v3_experimental_enabled"])
            self.assertEqual(r["results"][v3.HIST_NAME]["status"],"NOT_EVALUABLE")


if __name__=="__main__":
    unittest.main()
