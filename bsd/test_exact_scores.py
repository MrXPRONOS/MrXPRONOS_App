"""Deterministic exact-score smoke and anti-leakage tests."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from exact_scores import (matrix_for, top_scores, score_metrics, fit_rho_2024,
                          fit_goal_scales_2025, make_preview)

class ExactScoreTests(unittest.TestCase):
    def test_probabilities_sum_to_one(self):
        m=matrix_for(1.4,1.1,rho=-.08)
        self.assertAlmostEqual(sum(m.values()),1.0,places=10)
        self.assertTrue(all(v>=0 for v in m.values()))

    def test_top3_sorted(self):
        top=top_scores(matrix_for(1.6,1.1))
        self.assertEqual(len(top),3)
        self.assertGreaterEqual(top[0][1],top[1][1])
        self.assertGreaterEqual(top[1][1],top[2][1])

    def test_metrics_actual_hits(self):
        m=matrix_for(1.6,1.1)
        correct=top_scores(m)[0][0]
        r=score_metrics([(1.6,1.1,correct)])
        self.assertEqual(r['top1_hits'],1)
        self.assertEqual(r['top3_hits'],1)
        self.assertEqual(r['evaluated'],1)

    def test_train_small_dataset_fallback(self):
        rows=[(1.1,1.0,(1,0))]*10
        self.assertEqual(fit_rho_2024(rows)[0],0)
        self.assertEqual(fit_goal_scales_2025(rows,0)[:2],(1.0,1.0))

    def test_preview_never_publishes_or_includes_past(self):
        feed={'matches':[{'id':'old','event_date':'2025-01-01T00:00:00+00:00',
                          'estimated_goals':{'home':1.1,'away':1.1}},
                         {'id':'future','event_date':'2028-01-01T00:00:00+00:00',
                          'estimated_goals':{'home':1.6,'away':1.1}}]}
        params={'rho':0,'scale_home':1,'scale_away':1}
        preview=make_preview(feed,params,clock=datetime(2026,10,19,tzinfo=timezone.utc))
        self.assertEqual(len(preview['matches']),1)
        self.assertEqual(preview['matches'][0]['id'],'future')
        self.assertFalse(preview['published'])

if __name__=='__main__':
    unittest.main()


from exact_scores_h2h import H2HIndex, h2h_signal, blended_goals
from bsd_v2_core import V2History
from exact_scores_full_2026 import evaluate_all

class H2HStrictHistoryTests(unittest.TestCase):
    def test_stable_low_scores_priority(self):
        p=h2h_signal([(1,0),(2,0),(1,1),(0,0)])
        self.assertTrue(p["prioritized"])
        self.assertEqual(p["meetings"],4)
        self.assertFalse(h2h_signal([(1,0),(2,0)])["prioritized"])
        self.assertFalse(h2h_signal([(4,1),(0,0),(1,0)])["prioritized"])

    def test_no_future_or_current_match_in_h2h(self):
        def fixture(num,date,h,a):
            return {"id":num,"event_date":date,"status":"finished",
                    "home_team_id":10,"away_team_id":20,
                    "home_score":h,"away_score":a}
        past=fixture(1,"2025-08-01T15:00:00Z",1,0)
        current=fixture(2,"2026-04-01T15:00:00Z",9,9)
        future=fixture(3,"2026-04-02T15:00:00Z",0,0)
        index=H2HIndex(V2History([past,current,future]))
        history=index.past_scores(current)
        self.assertEqual(history,[(1,0)])
        self.assertEqual(index.past_scores(past),[])

    def test_priority_only_without_weight_keeps_model(self):
        s=h2h_signal([(1,0),(0,0),(1,1)])
        self.assertEqual(blended_goals(1.7,1.1,s,influence=0),(1.7,1.1))
        a,b=blended_goals(1.7,1.1,s,influence=.5)
        self.assertLess(a+b,2.8)

    def test_full_year_empty_history_explicitly_reports_zero(self):
        report, audit=evaluate_all([],max_2025=1)
        self.assertEqual(report["total_finished_2026"],0)
        self.assertEqual(audit,[])


from exact_scores_under25 import probability_under25, reweight_scores, fused_probability

class Under25FusionTests(unittest.TestCase):
    def test_under25_counts_only_two_or_fewer(self):
        m={(0,0):.2,(1,1):.3,(2,1):.5}
        self.assertAlmostEqual(probability_under25(m),.5)

    def test_fusion_normalized_and_exact_under_probability(self):
        m=matrix_for(1.3,1.4)
        r=reweight_scores(m,.7)
        self.assertAlmostEqual(sum(r.values()),1.,places=10)
        self.assertAlmostEqual(probability_under25(r),.7,places=10)
        self.assertTrue(all(v>=0 for v in r.values()))

    def test_zero_blend_keeps_poisson(self):
        self.assertAlmostEqual(fused_probability(.48,.75,0),.48)

    def test_blend_one_uses_bsd_specialist(self):
        self.assertAlmostEqual(fused_probability(.48,.75,1),.75)


from exact_scores_h2h_v2 import meetings_before,profile

class H2HPhaseOneTests(unittest.TestCase):
    def test_h2h_orientation_and_no_leakage(self):
        def f(i,dt,h,a,hs,aw):
            return {"id":i,"event_date":dt,"home_team_id":h,"away_team_id":a,
                    "home_score":hs,"away_score":aw,"status":"finished"}
        old=f(1,"2025-01-01T14:00:00Z",20,10,2,0)
        target=f(2,"2026-01-01T14:00:00Z",10,20,9,9)
        from exact_scores_h2h import H2HIndex
        index=V2History([old,target])
        rows=meetings_before(target,H2HIndex(index))
        self.assertEqual([r["score"] for r in rows],[(0,2)])
        self.assertFalse(rows[0]["same_venue"])
    def test_recent_unsettled_score_not_used(self):
        def f(i,dt,h,a,hs,aw):
            return {"id":i,"event_date":dt,"home_team_id":h,"away_team_id":a,
                    "home_score":hs,"away_score":aw,"status":"finished"}
        past=f(1,"2026-05-01T12:00:00Z",10,20,1,0)
        same_day=f(2,"2026-05-01T15:00:00Z",10,20,0,0)
        index=V2History([past,same_day])
        self.assertEqual(meetings_before(same_day,H2HIndex(index)),[])
    def test_phase1_ablation_has_stable_keys(self):
        from exact_scores_phase1_backtest import evaluate
        result,audit=evaluate([])
        self.assertEqual(result["finished_2026"],0)
        self.assertEqual(result["variants"]["combined"]["n"],0)
        self.assertEqual(audit,[])

class H2HStandaloneVariantTests(unittest.TestCase):
    def test_legacy_rejection_does_not_force_v2_rejection(self):
        from exact_scores_phase1_backtest import VARIANTS
        self.assertIn("v2_standalone",VARIANTS)
        self.assertIn("legacy",VARIANTS)
    def test_exact_settlement_four_hour_delay(self):
        from exact_scores_h2h_v2 import meetings_before
        from exact_scores_h2h import H2HIndex
        def ev(i,t,s):
            return {"id":i,"event_date":t,"status":"finished",
                    "home_team_id":100,"away_team_id":200,
                    "home_score":s,"away_score":0}
        old=ev(11,"2026-05-01T09:00:00Z",1)
        too_soon=ev(12,"2026-05-01T12:59:00Z",2)
        settled=ev(13,"2026-05-01T13:01:00Z",3)
        idx=V2History([old,too_soon,settled])
        self.assertEqual(meetings_before(too_soon,H2HIndex(idx)),[])
        self.assertEqual(len(meetings_before(settled,H2HIndex(idx))),1)


from exact_scores_under25_v2 import fit_logistic,Under25V2,features

class PhaseTwoUnder25Tests(unittest.TestCase):
    def test_regularized_training_simple_data(self):
        x=(1.,.2,0.,0.,0.,0.,0.,0.,0.,0.,0.)
        rows=[(x,1,.5)]*40+[(tuple([-1.]+[0.]*10),0,.5)]*40
        weights=fit_logistic(rows,epochs=15)
        self.assertEqual(len(weights),11)
        self.assertTrue(all(abs(w)<100 for w in weights))
    def test_disabled_blend_keeps_existing_probability(self):
        m=Under25V2((0.,)*11,blend=0.)
        self.assertEqual(m.predict((1.,)*11,.47),.47)
    def test_v2_no_history_returns_no_features(self):
        self.assertIsNone(features({"id":1,"event_date":"2026-10-25T12:00:00Z",
                                    "home_team_id":111,"away_team_id":222},
                                   V2History([]),.5))

from exact_scores_phase3 import coherent_fusion,btts_probability,decision
class PhaseThreeTests(unittest.TestCase):
    def test_joint_fusion_marginals(self):
        m=matrix_for(1.25,1.14)
        x=coherent_fusion(m,.69,.42)
        self.assertAlmostEqual(sum(x.values()),1,places=8)
        self.assertAlmostEqual(probability_under25(x),.69,places=5)
        self.assertAlmostEqual(btts_probability(x),.42,places=5)
    def test_abstention_is_explainable(self):
        m=matrix_for(1.25,1.14)
        d=decision(m,under_v1=.40,under_v2=.70,h2h_prioritized=True)
        self.assertFalse(d["selected"])
        self.assertIn("model_disagreement",d["reasons"])
    def test_low_h2h_is_not_forced_to_publish(self):
        m=matrix_for(1.15,.9)
        d=decision(m,under_v1=.70,under_v2=.70,h2h_prioritized=False)
        self.assertFalse(d["selected"])
        self.assertIn("h2h_not_stable",d["reasons"])
