import sys,unittest
from datetime import date,timedelta
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_hybrid import (PastHybridForecast,calibrate,blend,
                                 comparison_metrics,DEFAULT_DC_WEIGHT)
import single_ml_v2 as ml

class HybridTests(unittest.TestCase):
    def test_normalized_independent_fusion(self):
        p=ml.poisson_grid(1.3,.8)
        d=ml.dixon_coles(1.7,1.4,-.06)
        self.assertGreater(float(np.max(np.abs(p-d))),1e-4)
        self.assertTrue(np.allclose(blend(p,d,0),p))
        self.assertTrue(np.allclose(blend(p,d,1),d))
        self.assertAlmostEqual(float(blend(p,d,.35).sum()),1.)
        with self.assertRaises(ValueError):blend(p,d,1.5)
    def prior(self,n=100):
        start=date(2026,1,1)
        a=ml.poisson_grid(1.0,1.0);b=ml.poisson_grid(2.5,.2)
        return [PastHybridForecast(start+timedelta(days=i),str(i),a,b,0,0)
                for i in range(n)]
    def test_calibration_uses_only_old_games(self):
        previous=self.prior()
        out=calibrate(previous,asof=date(2026,5,1))
        self.assertTrue(out.calibrated)
        self.assertGreaterEqual(out.training_days,12)
        self.assertGreaterEqual(out.dc_weight,0.)
        self.assertLessEqual(out.dc_weight,1.)
        with self.assertRaisesRegex(ValueError,"Future/current-day"):
            calibrate(previous,asof=previous[-1].day)
    def test_insufficient_uses_declared_fallback(self):
        cfg=calibrate(self.prior(20),asof=date(2026,5,1))
        self.assertFalse(cfg.calibrated)
        self.assertEqual(cfg.dc_weight,DEFAULT_DC_WEIGHT)
    def test_frozen_copy(self):
        a=ml.poisson_grid(1,1);b=ml.poisson_grid(1.5,1.2)
        row=PastHybridForecast(date(2026,2,1),"i",a,b,0,1)
        original=float(row.ml_grid[0,0])
        a[0,0]=0.
        self.assertEqual(original,row.ml_grid[0,0])
        with self.assertRaises(ValueError):row.ml_grid[0,0]=1.
    def test_paired_metrics(self):
        rows={}
        for name in ("machine_learning","dixon_coles",
                     "machine_learning_hybrid","machine_learning_hybrid_fixed"):
            rows[name]=[{"date":"2026-03-01","id":"1","hit":1,"log_loss":1.4,"predicted_score":"1:1"}]
        summary=comparison_metrics(rows,tuple(rows))
        self.assertEqual(summary["common_match_count"],1)
        self.assertEqual(summary["models"]["machine_learning_hybrid"]["exact_hits"],1)
    def test_runner_wiring(self):
        import inspect
        source=inspect.getsource(ml.backtest)
        self.assertIn("calibrate_hybrid(hybrid_history",source)
        self.assertIn('forecasts["machine_learning_hybrid"] = blend_hybrid',source)
        self.assertIn("hybrid_history.append(PastHybridForecast",source)
        self.assertIn("hybrid_paired_comparison",source)

if __name__=="__main__":unittest.main()
