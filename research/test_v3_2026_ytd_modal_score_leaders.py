"""Full 2026 Jan 1-Nov 3 offline checks: unique genuine modal pick per score/day."""
import unittest
from datetime import date, timedelta
from backtest_v3_2026_ytd_modal_score_leaders import START, END, SCORES, summarize

DAYS = (END-START).days+1

def record(day, score, actual, probability=.15):
    return {
        "day": str(day), "score": score,
        "match_id": f"{day}:{score}",
        "league": "Synthetic test only",
        "home": "Home", "away": "Away",
        "probability": probability,
        "modal_score": score,
        "actual_score": actual,
        "hit": int(score==actual),
        "history_latest_day": str(day-timedelta(days=1)),
        "model_fit_latest_day": str(day-timedelta(days=1)),
    }

class YTDModalLeadersTests(unittest.TestCase):
    def fixture_rows(self):
        return [
            record(START+timedelta(days=i), score,
                   score if i % (j+3)==0 else "4:3",
                   probability=.13+.01*j)
            for i in range(DAYS)
            for j, score in enumerate(("1:1","1:0","2:0"))
        ]

    def test_full_year_to_nov3_calendar_coverage_and_months(self):
        self.assertEqual(START, date(2026,1,1))
        self.assertEqual(END, date(2026,11,3))
        self.assertEqual(DAYS,307)
        self.assertEqual(len(SCORES),121)
        rows=self.fixture_rows()
        d=summarize(rows,count_all_matches=79000)
        self.assertEqual(d["days_with_completed_history"],307)
        self.assertEqual(d["score_categories"],3)
        self.assertEqual(d["score_categories_theoretical"],121)
        self.assertEqual(d["total_selections_across_independent_scores"],921)
        self.assertEqual(d["days_with_at_least_one_hit"]+d["days_without_hit"],307)
        self.assertEqual(set(d["by_month"]),{f"2026-{i:02d}" for i in range(1,12)})
        self.assertEqual(d["by_month"]["2026-02"]["days"],28)
        self.assertEqual(d["by_month"]["2026-10"]["days"],31)
        self.assertEqual(d["by_month"]["2026-11"]["days"],3)
        self.assertEqual(sum(m["selections"] for m in d["by_month"].values()),921)
        self.assertEqual(sum(m["hits"] for m in d["by_month"].values()),d["total_hits_across_independent_scores"])
        self.assertTrue(all(r["distinct_matches_selected"]==3 for r in d["by_day"].values()))

    def test_no_double_pick_of_same_score(self):
        rows=self.fixture_rows()
        rows.append(dict(rows[-1]))
        with self.assertRaisesRegex(ValueError,"More than one selected fixture"):
            summarize(rows,count_all_matches=79000)

    def test_no_different_score_on_same_fixture(self):
        rows=self.fixture_rows()
        rows[1]["match_id"]=rows[0]["match_id"]
        with self.assertRaisesRegex(ValueError,"Same fixture reused"):
            summarize(rows,count_all_matches=79000)

    def test_nonmodal_score_and_future_data_are_rejected(self):
        rows=self.fixture_rows()
        rows[0]["modal_score"]="0:1"
        with self.assertRaisesRegex(ValueError,"genuine first-ranked"):
            summarize(rows,count_all_matches=79000)
        rows=self.fixture_rows()
        rows[0]["history_latest_day"]=rows[0]["day"]
        with self.assertRaisesRegex(ValueError,"future-data leakage"):
            summarize(rows,count_all_matches=79000)

    def test_partial_dates_and_false_wins_are_rejected(self):
        rows=self.fixture_rows()
        with self.assertRaisesRegex(ValueError,"Missing an authenticated 2026 UTC day"):
            summarize([r for r in rows if r["day"]!="2026-05-13"],count_all_matches=79000)
        rows=self.fixture_rows()
        rows[1]["hit"]=1-rows[1]["hit"]
        with self.assertRaisesRegex(ValueError,"Inconsistent selected-score settlement"):
            summarize(rows,count_all_matches=79000)

if __name__=="__main__":
    unittest.main()
