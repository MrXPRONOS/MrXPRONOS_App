"""Top 3 grouped goals strict research regression and calendar tests (synthetic only)."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from test_ml_v3_grouped_scores import records,make
from ml_v3_grouped_top3 import (
 WINDOWS,KS,GROUPS,SCORE_TO_GROUP,VERSION,
 month,pool,totals,settle,validate_month
)

class Top3GroupedScoreTests(unittest.TestCase):
    def test_top3_is_frozen_and_nested_in_top5(self):
        self.assertEqual(KS,(3,5,10,20))
        self.assertEqual(len(SCORE_TO_GROUP),15)
        self.assertEqual(set(map(len,GROUPS.values())),{3})
        self.assertIn("top3",VERSION)
        with tempfile.TemporaryDirectory() as temp:
            a,b=WINDOWS[0];f=Path(temp)/"p.csv";make(f,records(a,b))
            report=month(f,start=a,end=b);validate_month(report)
            t3=totals(report["daily"]["3"]);t5=totals(report["daily"]["5"])
            self.assertEqual(t3["selection_slots"],93)
            self.assertEqual(t5["selection_slots"],155)
            self.assertEqual(report["daily"]["3"][0]["exact_hits_full_k"],1)
            self.assertEqual(report["daily"]["3"][0]["grouped_hits"],2)
            self.assertEqual(report["daily"]["5"][0]["exact_hits_full_k"],2)
            self.assertEqual(report["daily"]["5"][0]["grouped_hits"],3)
            self.assertLessEqual(t3["grouped_hits"],t5["grouped_hits"])
            for i in range(31):
                for name in ("exact_hits_full_k","grouped_hits","covered"):
                    self.assertLessEqual(report["daily"]["3"][i][name],report["daily"]["5"][i][name])

    def test_group_only_depends_on_predicted_score_not_actual(self):
        before=settle("1:0","2:1")
        after=settle("1:0","0:2")
        self.assertEqual(before["group"],after["group"])
        self.assertTrue(before["win"])
        self.assertFalse(after["win"])

    def test_no_leakage_when_actual_scores_change(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=WINDOWS[0];data=list(records(a,b))
            original=Path(temp)/"original.csv";make(original,data)
            r1=month(original,start=a,end=b)
            for row in data:
                row["actual_score"]="9:9";row["hit"]=0;row["top3_hit"]=0
            changed=Path(temp)/"changed.csv";make(changed,data)
            r2=month(changed,start=a,end=b)
            for k in KS:
                self.assertEqual([day["group_counts"] for day in r1["daily"][str(k)]],
                                 [day["group_counts"] for day in r2["daily"][str(k)]])
            self.assertNotEqual(r1["daily"]["3"][0]["grouped_hits"],r2["daily"]["3"][0]["grouped_hits"])

    def test_reject_future_model_fit(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=WINDOWS[0];data=list(records(a,b));data[0]["model_fit_latest_day"]=a
            f=Path(temp)/"future.csv";make(f,data)
            with self.assertRaisesRegex(ValueError,"provenance"):
                month(f,start=a,end=b)

    def test_coverage_and_missing_days_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=WINDOWS[0];data=[row for row in records(a,b) if row["date"]!=a]
            f=Path(temp)/"missing.csv";make(f,data)
            with self.assertRaisesRegex(ValueError,"fewer than 20"):
                month(f,start=a,end=b)

    def test_calendar_all_2026_and_october_partial(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[]
            for i,(a,b) in enumerate(WINDOWS):
                f=Path(temp)/f"p{i}.csv";make(f,records(a,b))
                d=month(f,start=a,end=b)
                path=Path(temp)/f"m{i}.json";path.write_text(json.dumps(d),encoding="utf8")
                paths.append(path)
            with self.assertRaisesRegex(ValueError,"exactly 10"):
                pool(paths[:9])
            result=pool(paths)
            self.assertEqual(result["primary"]["3"]["days"],273)
            self.assertEqual(result["primary"]["3"]["selection_slots"],819)
            self.assertEqual(result["october_partial_1_to_24"]["3"]["days"],24)
            self.assertEqual(result["all_available_2026_descriptive"]["3"]["days"],297)
            self.assertEqual(result["all_available_2026_descriptive"]["3"]["selection_slots"],891)
            self.assertEqual(result["primary"]["5"]["selection_slots"],1365)

if __name__=="__main__":unittest.main()
