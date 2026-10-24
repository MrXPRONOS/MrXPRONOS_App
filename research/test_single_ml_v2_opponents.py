import sys,unittest
from datetime import date,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
import single_ml_v2 as ml
from single_ml_v2_opponents import OpponentStrengthState,OPPONENT_FEATURE_NAMES

class OpponentStrengthTests(unittest.TestCase):
    def game(self,d,h="A",a="B",league="L",gh=1,ga=0,key=None,hid=None,aid=None,comp=None):
        return ml.Match(key or f"{d}:{h}:{a}:{league}",d,league,h,a,gh,ga,
                        home_id=hid,away_id=aid,competition_id=comp)
    def test_original_pregame_rating_and_update(self):
        s=OpponentStrengthState();d=date(2026,9,1)
        before,_=s.features(self.game(d))
        self.assertEqual(len(before),len(OPPONENT_FEATURE_NAMES))
        self.assertAlmostEqual(before[-1],.592,places=2)
        s.add_day([self.game(d)])
        after,q=s.features(self.game(d+timedelta(days=1)))
        self.assertGreater(after[0],before[0])
        self.assertEqual(q["home"]["opponents_last10_n"],1)
        with self.assertRaises(ValueError):s.features(self.game(d))
    def test_competition_local_fallback_and_verified_cross_league(self):
        s=OpponentStrengthState();d=date(2026,9,1)
        s.add_day([self.game(d,league="League1",hid="h101",aid="a202",comp="c1")])
        same=s.features(self.game(d+timedelta(days=1),h="A",a="C",league="Cup",
                                  hid="h101",aid="c303",comp="cup"))[1]
        self.assertEqual(same["home"]["prior_games"],1)
        self.assertTrue(same["home"]["verified_global_id"])
        s.add_day([self.game(d+timedelta(days=1),h="A",a="C",league="Cup",
                             hid="h101",aid="c303",comp="cup")])
        later=s.features(self.game(d+timedelta(days=2),h="A",a="D",league="League1",
                                   hid="h101",aid="d404",comp="c1"))[1]
        self.assertEqual(later["home"]["cross_competition_prior_games"],1)
        fallback=OpponentStrengthState()
        fallback.add_day([self.game(d,league="League1")])
        q=fallback.features(self.game(d+timedelta(days=1),h="A",a="C",league="Cup"))[1]
        self.assertEqual(q["home"]["prior_games"],0)
    def test_same_day_freeze_and_duplicate_guard(self):
        s=OpponentStrengthState();d=date(2026,9,1)
        a=self.game(d,"A","B",gh=8,key="1")
        b=self.game(d,"A","C",gh=0,ga=3,key="2")
        s.add_day([a,b])
        history=s.history[("local-team",("league","l"),"a")]
        self.assertEqual(len(history),2)
        self.assertEqual(history[0][1],1500.)
        self.assertEqual(history[1][1],1500.)
        with self.assertRaises(ValueError):s.add_day([a])
    def test_invalid_id_collision_raises_without_day_mutation(self):
        s=OpponentStrengthState();d=date(2026,9,1)
        with self.assertRaises(ValueError):
            s.add_day([self.game(d,h="A",a="B",hid="same",aid="same")])
        self.assertIsNone(s.last_ingested_day)
    def test_features_wired_and_finite(self):
        st=ml.FormState();d=date(2026,9,1)
        m=self.game(d,hid="a1",aid="b1")
        f=st.features(m)
        self.assertEqual(f["vector"].shape,(len(ml.FEATURE_NAMES),))
        self.assertEqual(len(ml.FEATURE_NAMES),160)
        self.assertTrue(np.isfinite(f["vector"]).all())
        st.add_day([m])
        later=st.features(self.game(d+timedelta(days=1),hid="a1",aid="c1",a="C"))
        self.assertEqual(later["opponent_quality"]["home"]["prior_games"],1)
if __name__=="__main__":unittest.main()
