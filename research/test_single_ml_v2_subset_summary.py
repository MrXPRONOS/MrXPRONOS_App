"""Subset-comparison regression test: no fabricated unavailable model scores."""
import unittest
from single_ml_v2 import summarize


class SummarySubsetTests(unittest.TestCase):
    def test_selected_models_do_not_require_all_other_models(self):
        rows=[{"hit":1,"log_loss":1.5,"top_probability":0.2,
               "roi":None,"top3_hit":1}]
        report=summarize({"machine_learning":rows,
                          "machine_learning_lightgbm":rows})
        self.assertEqual(report["machine_learning"]["n"],1)
        self.assertEqual(report["machine_learning_direct"]["status"],"NOT_EVALUABLE")
        self.assertEqual(report["machine_learning_direct"]["n"],0)
        self.assertEqual(report["dixon_coles"]["status"],"NOT_EVALUABLE")
        self.assertIsNone(report["machine_learning"]["flat_stake_roi_pct"])

if __name__=="__main__":
    unittest.main()
