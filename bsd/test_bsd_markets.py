"""Tests des marchés résultat/buts et du choix unique calibré."""
import unittest
from bsd_markets import candidates_from_goals, realized, select_best, MarketCalibrator


class MultiMarketTests(unittest.TestCase):
    def setUp(self):
        self.options = candidates_from_goals(1.5, 1.1)

    def test_all_16_markets(self):
        self.assertEqual(len(self.options), 16)
        self.assertEqual(len({x.key for x in self.options}), 16)
        by = {x.key: x for x in self.options}
        self.assertAlmostEqual(sum(by[k].probability for k in ("1", "X", "2")), 1.0, places=5)
        self.assertAlmostEqual(by["BTTS_YES"].probability + by["BTTS_NO"].probability, 1.0, places=5)
        self.assertAlmostEqual(by["OVER_25"].probability + by["UNDER_25"].probability, 1.0, places=5)

    def test_results_and_goals(self):
        by = {x.key: x for x in self.options}
        self.assertEqual(realized(by["1X"], 2, 2), 1)
        self.assertEqual(realized(by["12"], 2, 2), 0)
        self.assertEqual(realized(by["BTTS_YES"], 2, 2), 1)
        self.assertEqual(realized(by["OVER_25"], 2, 1), 1)
        self.assertEqual(realized(by["UNDER_25"], 0, 2), 1)

    def test_filter_rejects_unreasonable_fair_odds(self):
        best, ranking = select_best(self.options)
        self.assertIsNotNone(best)
        self.assertEqual(best, ranking[0])
        self.assertTrue(all(1.32 <= r["model_fair_odds"] <= 3.50 for r in ranking))

    def test_can_reject_all(self):
        best, ranking = select_best(self.options, min_probability=.99)
        self.assertIsNone(best)
        self.assertEqual(ranking, [])

    def test_calibration_serialization(self):
        c = MarketCalibrator()
        option = self.options[0]
        c.observe(option, 1)
        clone = MarketCalibrator.from_dict(c.to_dict())
        self.assertEqual(clone.score(option), c.score(option))


if __name__ == "__main__":
    unittest.main()
