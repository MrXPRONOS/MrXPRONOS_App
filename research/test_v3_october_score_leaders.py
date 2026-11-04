"""Offline controls for the October daily best-per-score research backtest."""
import unittest
from datetime import date, timedelta

from backtest_v3_october_daily_score_leaders import (
    START, END, SCORES, summarize,
)


def synthetic(day, score, *, probability, actual, model_previous=True):
    previous = day - timedelta(days=1)
    return {
        "day": str(day),
        "score": score,
        "match_id": f"fixtures-{day}-{score}",
        "league": "Only a local synthetic fixture",
        "home": "A", "away": "B",
        "probability": probability,
        "modal_score": score if score == "1:1" else "1:1",
        "actual_score": actual,
        "hit": int(score == actual),
        "history_latest_day": str(previous if model_previous else day),
        "model_fit_latest_day": str(previous),
    }


class DailyBestScoreStudyTests(unittest.TestCase):
    def test_independent_score_selection_summary_for_all_31_days(self):
        self.assertEqual(len(SCORES),121)
        rows = []
        for offset in range(31):
            day = START + timedelta(days=offset)
            rows.extend([
                synthetic(day, "1:1", probability=.15,
                          actual="1:1" if offset < 5 else "0:0"),
                synthetic(day, "1:0", probability=.21,
                          actual="1:0" if offset < 10 else "0:0"),
                synthetic(day, "3:1", probability=.06,
                          actual="3:1" if offset < 2 else "0:0"),
            ])
        x = summarize(rows, count_all_matches=2000)
        self.assertEqual(x["days_with_completed_history"],31)
        self.assertEqual(x["score_categories"],121)
        self.assertEqual(x["total_selections_across_independent_scores"],93)
        self.assertEqual(x["total_hits_across_independent_scores"],17)
        self.assertEqual(x["by_score"]["1:1"]["hits"],5)
        self.assertEqual(x["by_score"]["1:0"]["hits"],10)
        self.assertEqual(x["by_score"]["3:1"]["hits"],2)
        self.assertEqual(x["by_score"]["2:0"]["days_selected"],0)
        self.assertEqual(x["by_score"]["1:0"]["hit_rate_percent"],round(1000/31,4))
        self.assertAlmostEqual(x["by_score"]["1:1"]["expected_hits_from_model"],4.65)
        self.assertEqual(x["scores_ranked_by_hits"][0],"1:0")
        self.assertTrue(all(day in x["by_day"] for day in
                            [(START+timedelta(days=i)).isoformat() for i in range(31)]))

    def test_duplicate_day_score_is_rejected(self):
        rows = [synthetic(START+timedelta(days=i), "1:1",
                          probability=.12,actual="1:1")
                for i in range(31)]
        rows.append(dict(rows[0]))
        with self.assertRaisesRegex(ValueError,"More than one"):
            summarize(rows, count_all_matches=100)

    def test_malformed_or_future_provenance_rejected(self):
        rows = [synthetic(START+timedelta(days=i), "1:1",
                          probability=.12,actual="1:1")
                for i in range(31)]
        rows[-1]["history_latest_day"]=rows[-1]["day"]
        with self.assertRaisesRegex(ValueError,"future-data leakage"):
            summarize(rows, count_all_matches=100)

    def test_study_must_cover_all_31_days(self):
        rows = [synthetic(START+timedelta(days=i), "1:0",
                          probability=.12,actual="1:1")
                for i in range(30)]
        with self.assertRaisesRegex(ValueError,"Missing an authenticated October UTC day"):
            summarize(rows, count_all_matches=100)

    def test_wrong_hit_is_rejected(self):
        rows = [synthetic(START+timedelta(days=i), "1:0",
                          probability=.12,actual="1:1")
                for i in range(31)]
        rows[1]["hit"]=1
        with self.assertRaisesRegex(ValueError,"Inconsistent"):
            summarize(rows, count_all_matches=100)

    def test_invalid_zero_probability_rejected(self):
        rows = [synthetic(START+timedelta(days=i), "1:0",
                          probability=.12,actual="1:1")
                for i in range(31)]
        rows[12]["probability"]=0
        with self.assertRaisesRegex(ValueError,"Invalid probability"):
            summarize(rows, count_all_matches=100)


if __name__ == "__main__":
    unittest.main()
