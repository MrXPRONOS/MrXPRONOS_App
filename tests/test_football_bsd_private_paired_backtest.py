import unittest
from scripts.football_bsd_private_paired_backtest import score, probabilities, evaluate


class PairedBSDPrivateResearchTests(unittest.TestCase):
    def test_score_consistency_and_normalization(self):
        prob=probabilities(1.3,1.1)
        self.assertAlmostEqual(sum(prob[k] for k in ("home","draw","away")),1,places=5)
        metrics=score(prob,2,1)
        self.assertTrue(all(x>=0 for x in metrics.values()))

    def test_unavailable_archive_explicitly_never_promotes_production(self):
        report=evaluate([],max_fixtures=10)
        self.assertEqual(report["identical_fixtures_evaluated"],0)
        self.assertTrue(report["insufficient_samples"])
        self.assertFalse(report["compared_to_production_calibrated_bsd_v2"])
        self.assertFalse(report["publication_enabled"])
        self.assertFalse(report["private_match_rows_exposed"])

    def test_fixed_sampling_bound(self):
        with self.assertRaises(ValueError):
            evaluate([],max_fixtures=9)
        with self.assertRaises(ValueError):
            evaluate([],max_fixtures=5000)

if __name__=="__main__":
    unittest.main()
