import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
import single_ml_v2 as m
from single_ml_v2_form import team_form, window_features, FORM_FEATURE_NAMES

class FormFeatureTests(unittest.TestCase):
    def mk(self, day, gh, ga, home="A", away="B", league="L", key=None):
        return m.Match(key or f"{day}-{home}-{away}",day,league,home,away,gh,ga)
    def test_empty_is_explicit(self):
        arr=team_form([],"home",date(2026,10,10))
        self.assertEqual(len(arr),4*14)
        self.assertEqual(arr[13],1.)
        self.assertEqual(arr[0],0.)
    def test_5_and_10_and_venue(self):
        s=m.FormState();start=date(2026,9,1)
        for i in range(10):
            d=start+timedelta(days=i)
            # Team A plays 5 games at home, 5 away; wins every home game.
            if i%2==0: game=self.mk(d,2,0,"A","B")
            else: game=self.mk(d,1,0,"B","A")
            s.add_day([game])
        future=self.mk(start+timedelta(days=11),0,0,"A","B")
        f=s.features(future)
        self.assertEqual(len(f["vector"]),len(m.FEATURE_NAMES))
        self.assertTrue(np.isfinite(f["vector"]).all())
        features=dict(zip(m.FEATURE_NAMES,f["vector"]))
        self.assertEqual(features["home_overall_last10_games"],10.)
        self.assertEqual(features["home_venue_last10_games"],5.)
        self.assertEqual(features["home_venue_last5_points_per_game"],3.)
        self.assertEqual(features["home_overall_last10_win_rate"],0.5)
        self.assertEqual(features["home_venue_last5_goals_for_avg"],2.)
        self.assertEqual(features["home_overall_last10_goals_for_avg"],1.)
        self.assertEqual(features["home_overall_last10_rest_days"],2.)
        self.assertEqual(f["form_samples"]["home"]["overall_last10"],10)
        self.assertEqual(f["form_samples"]["home"]["venue_last10"],5)
        self.assertEqual(features["home_venue_last10_missing"],0.)
    def test_same_day_not_leaked(self):
        s=m.FormState()
        d=date(2026,10,2)
        first=self.mk(d,5,0,"A","B","L",key="x")
        second=self.mk(d,0,3,"A","C","L",key="y")
        before=s.features(first)["vector"].copy()
        same_day=s.features(second)["vector"].copy()
        self.assertEqual(dict(zip(m.FEATURE_NAMES,before))["home_overall_last5_games"],0)
        self.assertEqual(dict(zip(m.FEATURE_NAMES,same_day))["home_overall_last5_games"],0)
        s.add_day([first,second])
        future=s.features(self.mk(d+timedelta(days=1),0,0,"A","D","L",key="z"))
        self.assertEqual(dict(zip(m.FEATURE_NAMES,future["vector"]))["home_overall_last5_games"],2.)
        with self.assertRaises(ValueError):s.features(second)
        with self.assertRaises(ValueError):s.add_day([second])
    def test_league_isolation(self):
        s=m.FormState();d=date(2026,10,3)
        s.add_day([self.mk(d,7,0,"A","B","L1",key="L1")])
        nxt=self.mk(d+timedelta(days=1),0,0,"A","C","L2",key="L2")
        f=dict(zip(m.FEATURE_NAMES,s.features(nxt)["vector"]))
        self.assertEqual(f["home_overall_last5_games"],0.)
        self.assertEqual(f["home_overall_last5_missing"],1.)
    def test_reject_bad_batch_without_modifying_state(self):
        s=m.FormState();d=date(2026,10,5)
        with self.assertRaises(ValueError):
            s.add_day([self.mk(d,1,0,key="a"),
                       self.mk(d+timedelta(days=1),2,0,key="b")])
        self.assertIsNone(s.last_ingested_day)
        self.assertEqual(len(s.seen_match_ids),0)
    def test_incomplete_sample_and_rates(self):
        sample=[(date(2026,10,1),1,1,0.,"home"),
                (date(2026,10,2),0,2,0.,"away")]
        f=window_features(sample,date(2026,10,5))
        self.assertEqual(f[0],2)
        self.assertEqual(f[4],0.5)
        self.assertEqual(f[6],0.5)
        self.assertEqual(f[9],0.5)
        self.assertEqual(f[12],3)
        self.assertEqual(f[13],0)
        with self.assertRaises(ValueError):
            window_features(sample,date(2026,10,2))
    def test_form_schema_stable(self):
        self.assertEqual(len(FORM_FEATURE_NAMES),112)
        self.assertEqual(len(m.FEATURE_NAMES),160)
        self.assertEqual(len(set(m.FEATURE_NAMES)),len(m.FEATURE_NAMES))
if __name__=="__main__":unittest.main()
