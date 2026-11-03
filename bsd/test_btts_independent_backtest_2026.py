"""Statistical and threshold regression checks for BTTS out-of-sample analysis."""
import unittest

from bsd_btts_independent_backtest_2026 import (
    BINS,KEYS,THRESHOLDS,summarize,wilson,markdown,
)
class IndependentBTTSAnalysisTests(unittest.TestCase):
    def test_btts_two_sides_and_thresholds(self):
        self.assertEqual(KEYS,("BTTS_YES","BTTS_NO"))
        self.assertEqual(THRESHOLDS,(.50,.55,.60,.65,.70,.75,.79,.80,.85,.90))
        self.assertEqual(len(set(THRESHOLDS)),10)
    def test_rates_are_from_finished_outcomes_only(self):
        rows=[
            {"probability":.8,"won":1,"honest_indicative_odds":1.179},
            {"probability":.6,"won":0,"honest_indicative_odds":1.572},
        ]
        s=summarize(rows)
        self.assertEqual(s["n"],2)
        self.assertEqual(s["wins"],1)
        self.assertAlmostEqual(s["hit_rate"],.5)
        self.assertAlmostEqual(s["mean_forecast"],.7)
        self.assertAlmostEqual(s["calibration_gap_pp"],20)
        self.assertAlmostEqual(s["brier"],(.2**2+.6**2)/2)
        self.assertEqual(s["pct_fair_margin6_odds_at_least_120"],50.)
    def test_empty_is_never_presented_as_success(self):
        s=summarize([])
        self.assertEqual(s["n"],0)
        self.assertIsNone(s["hit_rate"])
        self.assertIsNone(s["brier"])
        self.assertIsNone(wilson(0,0))
    def test_confidence_interval(self):
        low,high=wilson(8,10)
        self.assertLess(low,.8)
        self.assertGreater(high,.8)
        self.assertGreater(low,0)
        self.assertLess(high,1)
    def test_bucket_coverage_is_complete(self):
        for p in [0.0,.49,.50,.59,.69,.75,.78,.79,.80,.89,.90,.99]:
            self.assertEqual(sum(int(a<=p<b) for a,b in BINS),1)
    def test_report_discloses_no_historical_bookmaker_odds(self):
        self.assertTrue(any("bookmaker" in x for x in [
            "Historical bookmaker quotes are unavailable; no real-bet ROI can be inferred."
        ]))
if __name__=="__main__":unittest.main()
