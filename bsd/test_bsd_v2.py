"""Regression tests for isolated prediction V2."""
import unittest
from datetime import datetime,timezone
from bsd_v2_core import V2History,score_matrix,markets_from_matrix,choose_market,predict_v2,estimate_goals
from bsd_v2_evaluate import run_evaluation, BASELINE_KEYS


def game(i,dt,h=1,a=2,hs=2,aws=1,league=99):
    return {"id":i,"event_date":dt,"status":"finished","home_team_id":h,
            "away_team_id":a,"home_score":hs,"away_score":aws,"league_id":league}


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.history=[game(i,"2026-09-%02dT12:00:00Z"%(i+1)) for i in range(12)]
        self.future={"id":999,"event_date":"2026-10-20T20:00:00Z",
                     "status":"notstarted","home_team_id":1,"away_team_id":2,"league_id":99}

    def test_score_matrix_normalizes(self):
        for rho in (-.08,0,.08):
            matrix=score_matrix(1.6,1.1,rho)
            self.assertAlmostEqual(sum(matrix.values()),1,places=8)
            self.assertTrue(all(p>=0 for p in matrix.values()))

    def test_reliability_is_true_probability_not_fair_odds(self):
        candidates=markets_from_matrix(score_matrix(2.3,.5))
        pick,rows=choose_market(candidates,min_probability=.5)
        self.assertEqual(pick["candidate"].key,rows[0]["candidate"].key)
        self.assertEqual(pick["calibrated_probability"],max(r["calibrated_probability"] for r in rows))

    def test_value_mode_requires_real_odds(self):
        c=markets_from_matrix(score_matrix(1.7,1.1))
        best,_=choose_market(c,mode="value")
        self.assertIsNone(best)

    def test_no_future_leakage(self):
        historical=V2History(self.history+[game(50,"2026-10-21T12:00:00Z",hs=0,aws=21)])
        before=V2History(self.history)
        h1,_=estimate_goals(self.future,historical)
        h2,_=estimate_goals(self.future,before)
        self.assertEqual(h1,h2)

    def test_settlement_delay(self):
        index=V2History([game(1,"2026-10-08T12:00:00Z")])
        at=datetime(2026,10,8,13,tzinfo=timezone.utc)
        self.assertEqual(index.team(1,at),[])

    def test_single_output(self):
        pred,reason=predict_v2(self.future,V2History(self.history),
            clock=datetime(2026,10,8,tzinfo=timezone.utc))
        self.assertEqual(reason,"ok")
        self.assertIsNotNone(pred["prediction"]["key"])
        self.assertIsNone(pred["prediction"]["bookmaker_selection_code"])
        self.assertFalse(pred["published"])

    def test_fair_baseline_includes_under_45(self):
        self.assertIn('UNDER_45', BASELINE_KEYS)
        report = run_evaluation(V2History(self.history), None, 0.0, year=2026, max_matches=10)
        self.assertIn('fixed_baselines_same_fixtures', report)
        self.assertIn('paired_vs_fixed_baselines_on_same_selected_fixtures', report)

    def test_missing_form_refuses(self):
        pred,reason=predict_v2(self.future,V2History([]))
        self.assertIsNone(pred)
        self.assertEqual(reason,"insufficient_form")


if __name__=="__main__":
    unittest.main()
