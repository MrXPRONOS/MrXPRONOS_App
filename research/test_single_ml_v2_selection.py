import sys
import unittest
from pathlib import Path
from datetime import date,timedelta
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_selection import (PastForecast,prediction_features,fit_reliability,
    decide,prematch_quality,report_selections,MIN_DATA_QUALITY,SELECTABLE_MODELS)
from single_ml_v2 import poisson_grid

class SelectorTests(unittest.TestCase):
    def rows(self,n=320):
        day=date(2025,1,1);out=[]
        for i in range(n):
            x=np.asarray([.10+(i%8)/100.,.04+(i%3)/100.,.40,1.,.1,.1,.13])
            out.append(PastForecast(day+timedelta(days=i),x,int(i%7==0)))
        return out
    def test_asof_guard(self):
        obs=self.rows(320)
        with self.assertRaises(ValueError):
            fit_reliability(obs,asof=obs[-1].day)
    def test_honest_abstention_and_fitted_gate(self):
        obs=self.rows()
        model=fit_reliability(obs,asof=date(2026,1,1))
        self.assertIsNotNone(model)
        self.assertEqual(model.fit_rows+model.calibration_rows,len(obs))
        self.assertGreaterEqual(model.calibration_selected,15)
        grid=poisson_grid(1.3,1.1)
        form={"home":{"overall_last5":5,"venue_last5":5},
              "away":{"overall_last5":5,"venue_last5":5}}
        decision=decide(model,grid,form_samples=form)
        self.assertIn(decision["status"],("SELECTED","ABSTAIN"))
        self.assertEqual(decide(None,grid,form_samples=form)["status"],"ABSTAIN")
    def test_reject_weak_form(self):
        obs=self.rows()
        model=fit_reliability(obs,asof=date(2026,1,1))
        form={"home":{"overall_last5":0,"venue_last5":0},
              "away":{"overall_last5":0,"venue_last5":0}}
        out=decide(model,poisson_grid(1,1),form_samples=form)
        self.assertEqual(out["status"],"ABSTAIN")
        self.assertIn("insufficient_team_form",out["reason"])
    def test_coverage_denominators(self):
        rows={"machine_learning":[
            {"status":"SELECTED","hit":1},
            {"status":"ABSTAIN","hit":0},
            {"status":"ABSTAIN","hit":0,"underlying_available":False},
        ]}
        report=report_selections(rows,total_matches=3,policy_coverage=.25)["machine_learning"]
        self.assertEqual(report["selected"],1)
        self.assertEqual(report["coverage_of_all_matches_pct"],33.333)
        self.assertEqual(report["selected_hit_rate_pct"],100.)
        self.assertEqual(report["unfiltered_hit_rate_pct"],50.)
        self.assertIsNone(report["roi_pct"])
    def test_quality_validation(self):
        with self.assertRaises(ValueError):
            prediction_features(np.zeros((11,11)),.7)
        self.assertEqual(len(SELECTABLE_MODELS),4)
    def test_runner_wired(self):
        import inspect, single_ml_v2
        code=inspect.getsource(single_ml_v2.backtest)
        self.assertIn("fit_reliability(reliability_history",code)
        self.assertIn("selection_rows[target_name].append",code)
        self.assertIn("selection_decisions.csv",code)
        self.assertIn("reliability_history[model_name].append",code)
if __name__=="__main__": unittest.main()
