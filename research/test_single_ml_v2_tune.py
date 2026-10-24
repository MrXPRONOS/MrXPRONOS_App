import sys, unittest
from datetime import date, timedelta
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import single_ml_v2 as model
from single_ml_v2_tune import (BASELINE, MLConfig, recency_weights,
    inner_folds, fit_histgb, select_hyperparameters)

class TuningTests(unittest.TestCase):
    def rows(self,n=100,days=100):
        start=date(2026,1,1)
        data=[]
        for i in range(n):
            arr=np.full(len(model.FEATURE_NAMES),.1+(i%4)*.03)
            data.append((arr,int(i%3),int((i+1)%2),start+timedelta(days=i%days)))
        return sorted(data,key=lambda r:r[3])

    def test_reject_future_current_training(self):
        rows=self.rows(12)
        with self.assertRaises(ValueError):
            select_hyperparameters(rows,asof=rows[-1][3],feature_count=len(model.FEATURE_NAMES))
        with self.assertRaises(ValueError):
            recency_weights(rows,date(2026,1,1),30)

    def test_weight_decay(self):
        rows=self.rows(3)
        weights=recency_weights(rows,date(2026,2,1),14)
        self.assertGreater(weights[-1],weights[0])
        self.assertAlmostEqual(float(weights.mean()),1)

    def test_insufficient_past_abstains_from_tuning(self):
        rows=self.rows(50)
        choice,report=select_hyperparameters(rows,asof=date(2026,6,1),
                            feature_count=len(model.FEATURE_NAMES))
        self.assertEqual(choice,BASELINE)
        self.assertEqual(report["status"],"insufficient_history")
        self.assertEqual(report["results"],[])

    def test_fold_chronology_and_no_day_split(self):
        rows=self.rows(140)
        folds=inner_folds(rows,asof=date(2026,7,1),folds=2,validation_days=14,min_training=40)
        self.assertEqual(len(folds),2)
        for first,last,training,validation in folds:
            self.assertLess(max(r[3] for r in training),first)
            self.assertGreaterEqual(min(r[3] for r in validation),first)
            self.assertLessEqual(max(r[3] for r in validation),last)

    def test_real_weighted_fit(self):
        rows=self.rows(40)
        cfg=MLConfig(max_iter=5,max_leaf_nodes=6,half_life_days=30)
        fitted=fit_histgb(rows,config=cfg,asof=date(2026,7,1),
                         feature_count=len(model.FEATURE_NAMES),minimum=20)
        self.assertEqual(len(fitted),2)
        self.assertTrue(np.isfinite(fitted[0].predict(rows[0][0][None,:])).all())

    def test_invalid_feature_schema(self):
        rows=self.rows(35)
        with self.assertRaises(ValueError):
            fit_histgb(rows,asof=date(2026,7,1),feature_count=3,minimum=20)

    def test_runner_has_integrated_scheduler(self):
        import inspect
        source=inspect.getsource(model.backtest)
        self.assertIn("select_hyperparameters(",source)
        self.assertIn("fit_histgb(dated_training",source)
        self.assertIn("dated_training.append",source)
        self.assertIn("tuning_history.append",source)

if __name__=="__main__": unittest.main()
