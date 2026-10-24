import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_direct import (direct_score_features,exact_score_class,
                                train_direct_score,direct_grid,DIRECT_MODEL_ID)
from single_ml_v2 import poisson_grid, FEATURE_NAMES


class DirectScoreClassifierTests(unittest.TestCase):
    def test_class_indices_and_rare(self):
        self.assertEqual(exact_score_class(0,0),0)
        self.assertEqual(exact_score_class(1,2),8)
        self.assertEqual(exact_score_class(5,5),35)
        self.assertEqual(exact_score_class(6,0),36)
        with self.assertRaises(ValueError):
            exact_score_class(-1,2)

    def test_prematch_features_not_finals(self):
        vector=np.linspace(0,1,len(FEATURE_NAMES))
        grid=poisson_grid(1.3,1.1)
        values,scores=direct_score_features(vector,grid)
        self.assertEqual(len(values),len(FEATURE_NAMES)+37)
        self.assertEqual(len(scores),37)
        self.assertAlmostEqual(sum(values[-37:]),1.,places=12)
        self.assertEqual(scores[-1],(-1,-1))

    def test_train_and_predict_37_class_grid(self):
        grid=poisson_grid(1.5,1.0)
        base=np.arange(len(FEATURE_NAMES),dtype=float)/len(FEATURE_NAMES)
        rows=[]
        for i in range(96):
            x=base.copy()
            x[0]=i%7
            # Include rare (>5) outcomes and varied known classes.
            rows.append((x,grid,i%7,(i//7)%5))
        model=train_direct_score(rows,min_samples=30,max_iter=8,
                                 max_leaf_nodes=5)
        self.assertIsNotNone(model)
        self.assertEqual(model.samples,96)
        pred=direct_grid(model,base,grid)
        self.assertEqual(pred.shape,grid.shape)
        self.assertTrue(np.isfinite(pred).all())
        self.assertTrue((pred>=0).all())
        self.assertAlmostEqual(float(pred.sum()),1.,places=10)
        self.assertGreater(float(pred[10,10]),0.)
        self.assertGreater(float(pred[0,0]),0.)  # prior smoothing
        self.assertEqual(DIRECT_MODEL_ID,"machine_learning_direct")

    def test_not_trained_until_minimum_and_single_class(self):
        grid=poisson_grid(1.5,1.0)
        x=np.ones(len(FEATURE_NAMES))
        self.assertIsNone(train_direct_score([(x,grid,1,1)],min_samples=2))
        rows=[(x,grid,1,1)]*30
        self.assertIsNone(train_direct_score(rows,min_samples=20))
        self.assertIsNone(direct_grid(None,x,grid))

    def test_fail_closed_schema(self):
        grid=poisson_grid(1.5,1.0)
        with self.assertRaises(ValueError):
            direct_score_features(np.ones((2,3)),grid)
        with self.assertRaises(ValueError):
            direct_score_features(np.array([float("nan")]),grid)
        with self.assertRaises(ValueError):
            direct_score_features(np.ones(5),np.zeros((11,11)))
        rows=[(np.ones(len(FEATURE_NAMES)+i%2),grid,i%3,1)]*16
        with self.assertRaises(ValueError):
            train_direct_score(rows,min_samples=8,max_iter=4)

    def test_model_main_runner_is_connected(self):
        import inspect
        import single_ml_v2 as main
        code=inspect.getsource(main.backtest)
        self.assertIn("train_direct_score(direct_training)",code)
        self.assertIn("forecasts[DIRECT_MODEL_ID]",code)
        self.assertIn("direct_training.append",code)
        self.assertIn("states.add_day(daily)",code)

if __name__=="__main__":
    unittest.main()
