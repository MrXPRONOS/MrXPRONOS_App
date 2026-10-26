"""Synthetic-only checks for pre-registered four-window paired aggregation."""
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from single_ml_v2_multisource_compare import MODELS
from single_ml_v2_multiperiod_aggregate import WINDOWS, pool


class FourPeriodPooledTests(unittest.TestCase):
    def reports(self,folder):
        paths=[]
        for index,(start,end) in enumerate(WINDOWS):
            first=date.fromisoformat(start)
            dates=[str(first+timedelta(days=i)) for i in range(28)]
            daily={}
            for m_i,m in enumerate(MODELS):
                daily[m]=[{
                    "day":d, "n":20, "hits":2+(m_i==3),
                    "top3_hits":6, "log_loss_sum":70.0-m_i*.04,
                    "top_probability_sum":2.1, "brier_top_sum":1.9,
                    "p11_sum":2.2, "p11_brier_sum":1.85,
                    "actual_11":2, "top1_11":10, "correct_top1_11":1
                } for d in dates]
            report={
                "test_start":start,"test_end":end,"research_only":True,
                "cohort_digest_sha256":"f"*64,
                "same_fixture_cohort_n":560,
                "utc_days":dates,"model_names":list(MODELS),
                "daily_aggregates":daily,
                "metrics":{m:{"n":560} for m in MODELS},
            }
            path=Path(folder)/f"{index}.json"
            path.write_text(json.dumps(report),encoding="utf8")
            paths.append(path)
        return paths

    def test_frozen_pool_and_stratified_day_bootstrap(self):
        with tempfile.TemporaryDirectory() as dirname:
            paths=self.reports(dirname)
            result=pool(paths,resamples=50)
            self.assertEqual(result["aggregate_matches"],2240)
            self.assertEqual(result["aggregate_utc_days"],112)
            self.assertEqual(result["overall"]["machine_learning"]["hits"],224)
            self.assertEqual(result["overall"]["machine_learning_catboost"]["hits"],336)
            self.assertAlmostEqual(result["overall"]["machine_learning"]["mean_prob_1_1_pct"],11.0)
            self.assertAlmostEqual(result["overall"]["machine_learning"]["actual_1_1_pct"],10.0)
            intervals=result["confidence_by_utc_day"]["paired_vs_histgb"]["machine_learning_catboost"]
            self.assertEqual(len(intervals["hit_rate_difference_pp_95pct"]),2)
            self.assertEqual(len(result["sensitivity_by_7day_blocks"]["hit_rate_95pct"]),5)

    def test_no_period_cherry_picking(self):
        with tempfile.TemporaryDirectory() as dirname:
            paths=self.reports(dirname)
            with self.assertRaisesRegex(ValueError,"four predeclared"):
                pool(paths[:3],resamples=10)

    def test_reject_unpaired_day(self):
        with tempfile.TemporaryDirectory() as dirname:
            paths=self.reports(dirname)
            payload=json.loads(paths[0].read_text())
            payload["daily_aggregates"]["machine_learning_catboost"][2]["n"]=21
            paths[0].write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"cohort differs"):
                pool(paths,resamples=10)


if __name__=="__main__":
    unittest.main()
