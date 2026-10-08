"""Comparison test, no external football API calls."""
import unittest
from bsd_recent_backtest import paired_comparison


class PairedTests(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(paired_comparison(3, 3)["two_sided_exact_p_exploratory"], 1.0)

    def test_all_discordances_favor_one_side(self):
        self.assertEqual(paired_comparison(6, 0)["two_sided_exact_p_exploratory"], .03125)

    def test_no_disagreement(self):
        self.assertEqual(paired_comparison(0, 0)["discordant_matches"], 0)
        self.assertEqual(paired_comparison(0, 0)["two_sided_exact_p_exploratory"], 1.0)


if __name__ == "__main__":
    unittest.main()
