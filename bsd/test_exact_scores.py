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
