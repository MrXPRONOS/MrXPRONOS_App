import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import single_ml_v2 as ml
from single_ml_v2_candidates import (CANDIDATES,CANDIDATE_MODEL_NAMES,
                                     fit_pair,predict_grid,predicted_goal_means)

class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[]
        n=len(ml.FEATURE_NAMES)
        for i in range(48):
            x=np.full(n, 0.25+i/110.)
            x[0]=i%8
            cls.rows.append((x,i%4,(i//4)%3))
        cls.vector=cls.rows[-1][0]

    def test_lightgbm_real_model(self):
        model=fit_pair("lightgbm",self.rows,minimum=20)
        self.assertEqual(model.name,"lightgbm")
        self.assertIn("lightgbm",type(model.home_model).__module__)
        self.assertEqual(model.training_rows,48)
        self._assert_grid(model)

    def test_catboost_real_model(self):
        model=fit_pair("catboost",self.rows,minimum=20)
        self.assertEqual(model.name,"catboost")
        self.assertIn("catboost",type(model.away_model).__module__)
        self._assert_grid(model)

    def _assert_grid(self,model):
        home,away=predicted_goal_means(model,self.vector)
        self.assertTrue(0.12<=home<=5.)
        self.assertTrue(0.12<=away<=5.)
        grid=predict_grid(model,self.vector,ml.poisson_grid)
        self.assertEqual(grid.shape,(11,11))
        self.assertTrue(np.isfinite(grid).all())
        self.assertAlmostEqual(float(grid.sum()),1.,places=10)

    def test_minimum_and_invalid_schema(self):
        self.assertIsNone(fit_pair("lightgbm",self.rows[:2],minimum=5))
        with self.assertRaises(ValueError):
            fit_pair("catboost",self.rows,minimum=20,feature_count=3)
        with self.assertRaises(ValueError):
            fit_pair("wrong",self.rows,minimum=20)
        bad=list(self.rows)
        x=bad[-1][0].copy();x[0]=float("nan")
        bad[-1]=(x,1,1)
        with self.assertRaises(ValueError):
            fit_pair("lightgbm",bad,minimum=20)

    def test_equal_match_integration(self):
        import inspect
        source=inspect.getsource(ml.backtest)
        self.assertIn("candidate_models[candidate_name] = fit_pair",source)
        self.assertIn("forecasts[CANDIDATE_MODEL_NAMES[candidate_name]]",source)
        self.assertIn('paired_cohorts["all_goal_rate_ml_competitors"]',source)
        self.assertIn("states.add_day(daily)",source)
        for name in CANDIDATE_MODEL_NAMES.values():
            self.assertIn(name,ml.MODELS)

if __name__=="__main__": unittest.main()
