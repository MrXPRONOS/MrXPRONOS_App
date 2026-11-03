"""Safe, deterministic unit tests for retrospective no-1:1 policy accounting."""
import unittest
from backtest_hybrid_v3_no11_2026 import aggregate


class ScorePolicyTests(unittest.TestCase):
    def test_two_different_policies_and_coverage(self):
        data = [
            ("2026-01-01", 1,1, 1,0, 1,1, .16,.14), # modal 1:1 hits; replacement loses
            ("2026-01-02", 1,1, 2,1, 2,1, .18,.15), # modal misses; replacement wins
            ("2026-01-03", 0,1, 1,0, 0,1, .19,.18), # untouched correct
            ("2026-02-01", 2,0, 1,0, 0,0, .22,.18), # untouched incorrect
        ]
        r=aggregate(data)
        a=r["baseline"]
        dropped=r["scenario_1_remove_entire_1_1_modal_matches"]
        swapped=r["scenario_2_replace_modal_1_1_with_best_other_score"]
        self.assertEqual(a["predictions"], 4)
        self.assertEqual(a["hits"], 2)
        self.assertEqual(a["exact_hit_rate_pct"],50.0)
        self.assertEqual(dropped["predictions"],2)
        self.assertEqual(dropped["excluded"],2)
        self.assertEqual(dropped["hits"],1)
        self.assertEqual(dropped["coverage_pct"],50.0)
        self.assertEqual(dropped["exact_hit_rate_pct"],50.0)
        self.assertEqual(swapped["predictions"],4)
        self.assertEqual(swapped["replaced"],2)
        self.assertEqual(swapped["hits"],2)
        self.assertEqual(swapped["exact_hit_rate_pct"],50.0)
        self.assertEqual(swapped["alternative_successes_on_replaced_matches"],1)
        self.assertEqual(r["diagnostics"]["replacement_lost_1_1_hits"],1)
        self.assertEqual(r["diagnostics"]["replacement_gained_non_1_1_hits"],1)
        self.assertEqual(r["diagnostics"]["net_additional_hits_scenario_2"],0)
        self.assertEqual(r["monthly"]["2026-01"]["eligible"],3)
        self.assertEqual(r["monthly"]["2026-02"]["eligible"],1)

    def test_skip_11_has_zero_coverage_when_all_modal_11(self):
        r=aggregate([("2026-05-01",1,1,0,1,0,1,.2,.18)])
        self.assertEqual(r["scenario_1_remove_entire_1_1_modal_matches"]["predictions"],0)
        self.assertIsNone(r["scenario_1_remove_entire_1_1_modal_matches"]["exact_hit_rate_pct"])
        self.assertEqual(r["scenario_2_replace_modal_1_1_with_best_other_score"]["hits"],1)

    def test_invalid_alt_11_rejected(self):
        with self.assertRaises(AssertionError):
            aggregate([("2026-01-01",1,1,1,1,1,1,.2,.19)])

    def test_empty_is_not_a_backtest_result(self):
        with self.assertRaises(ValueError):
            aggregate([])

    def test_scenario_2_keeps_non_11_modal_even_if_an_alternative_is_better_in_outcome(self):
        r=aggregate([("2026-01-01",2,1,1,0,1,0,.2,.19)])
        self.assertEqual(r["scenario_2_replace_modal_1_1_with_best_other_score"]["hits"],0)
        self.assertEqual(r["scenario_2_replace_modal_1_1_with_best_other_score"]["replaced"],0)


if __name__ == "__main__":
    unittest.main()
