import sys
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import single_ml_v2 as m
import single_ml_v2_experiments as x

class ExactScoreMLV2Tests(unittest.TestCase):
    def mk(self, d, hg, ag):
        return m.Match(key=f"test:{d}:{hg}:{ag}",day=d,league="Verified league",
                       home="A",away="B",hg=hg,ag=ag)
    def test_strict_sport(self):
        # Ingestion must reject missing sportId and other sports.
        from tempfile import NamedTemporaryFile
        import json
        def row(sport):
            r={"id":str(sport),"date":"2026-09-01","home_team":"A","away_team":"B",
               "competition":"Test","is_finished":True,"home_score":1,"away_score":0}
            if sport is not None:r["sportId"]=sport
            return r
        with NamedTemporaryFile("w+",suffix=".json",encoding="utf8") as f:
            json.dump([row(None),row(3),row(1)],f);f.flush()
            data=m.load_matches(f.name,date(2026,9,1))
            self.assertEqual(len(data),1)
    def test_pregame_features_immutable(self):
        state=m.FormState();d=date(2026,9,1);fixture=self.mk(d,2,1)
        before=state.features(fixture)["vector"].copy()
        self.assertEqual(len(before),len(m.FEATURE_NAMES))
        state.add(fixture)
        after=state.features(self.mk(d+timedelta(days=1),0,0))["vector"]
        self.assertGreater(after[13],0)
        self.assertNotEqual(before.tolist(),after.tolist())
    def test_hybrid_normalized(self):
        class Dummy:
            def predict(self, X):return [1.5]
        p=m.ml_hybrid_grid([Dummy(),Dummy()],np.ones(34))
        self.assertAlmostEqual(float(p.sum()),1)
        self.assertTrue(np.isfinite(p).all())
    def test_direct_score_mass(self):
        b=m.poisson_grid(1.3,1.1)
        f,s=x.direct_score_features(np.ones(34),b)
        self.assertEqual(len(s),37)
        self.assertAlmostEqual(sum(f[-37:]),1.,places=6)
        self.assertIsNone(x.train_direct_score([],min_samples=1))
    def test_abstains_without_reliability(self):
        self.assertEqual(x.select_forecast(m.poisson_grid(1,1),None,0.8,0.11)["status"],"ABSTAIN")
    def test_missing_market_roi(self):
        self.assertIsNone(x.flat_roi(True,None))
        self.assertEqual(x.flat_roi(False,10),-1)
if __name__=="__main__":unittest.main()
