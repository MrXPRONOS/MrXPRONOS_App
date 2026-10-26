"""Unit tests for five-model paired fixture/date comparison: synthetic rows only."""
import csv
import tempfile
import unittest
from pathlib import Path
from single_ml_v2_multisource_compare import MODELS, paired_report


def fixture(date, key, model):
    return {
        "model": model, "date": date, "id": key, "league": "TEST",
        "history_latest_day": "2026-10-18",
        "model_fit_latest_day": "2026-10-18",
        "predicted_score": "1:1", "actual_score": "1:1",
        "hit": "1", "top3_hit": "1", "top_probability": "0.2",
        "actual_probability": "0.2", "log_loss": "1.609437912434",
        "p_1_1": "0.2", "runner_up_score": "1:0",
        "runner_up_probability": "0.18", "top2_margin": "0.02",
        "quoted_odds": "",
    }


class PairedResearchTests(unittest.TestCase):
    def write(self, rows, path):
        with open(path, "w", encoding="utf8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def data(self):
        return [fixture(day, f"synthetic-{i}", model)
                for day, i in (("2026-10-20", 1), ("2026-10-21", 2))
                for model in MODELS]

    def test_identical_paired_cohort_and_past_history(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "predictions.csv"
            self.write(self.data(), path)
            report = paired_report(path, test_start="2026-10-20",
                                   test_end="2026-10-21", min_matches=2)
            self.assertEqual(report["same_fixture_cohort_n"], 2)
            d = report["score_1_1_diagnostics"]["machine_learning"]
            self.assertEqual(d["top1_1_1_n"], 2)
            self.assertEqual(d["mean_assigned_p_1_1_pct"], 20)
            self.assertEqual(len(report["daily_aggregates"]["machine_learning"]), 2)
            self.assertEqual(set(report["metrics"]), set(MODELS))
            self.assertEqual(report["metrics"]["machine_learning"]["n"], 2)
            self.assertIsNone(report["metrics"]["machine_learning"]["flat_stake_roi_pct"])

    def test_reject_future_history(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "predictions.csv"
            data = self.data()
            data[0]["history_latest_day"] = "2026-10-20"
            self.write(data, path)
            with self.assertRaisesRegex(ValueError, "Leaked"):
                paired_report(path, test_start="2026-10-20",
                              test_end="2026-10-21", min_matches=2)

    def test_missing_candidate_refuses_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "predictions.csv"
            self.write([row for row in self.data()
                        if row["model"] != "machine_learning_direct"], path)
            with self.assertRaisesRegex(ValueError, "not all available"):
                paired_report(path, test_start="2026-10-20",
                              test_end="2026-10-21", min_matches=2)

    def test_reject_p11_inconsistent_with_top1(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"predictions.csv"
            data=self.data()
            data[0]["p_1_1"]="0.08"
            self.write(data,path)
            with self.assertRaisesRegex(ValueError,"1-1 is top-1"):
                paired_report(path,test_start="2026-10-20",test_end="2026-10-21",min_matches=2)

    def test_reject_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "predictions.csv"
            data = self.data()
            self.write(data + [dict(data[0])], path)
            with self.assertRaisesRegex(ValueError, "Duplicated"):
                paired_report(path, test_start="2026-10-20",
                              test_end="2026-10-21", min_matches=2)


if __name__ == "__main__":
    unittest.main()
