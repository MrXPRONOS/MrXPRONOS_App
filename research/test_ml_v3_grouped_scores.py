"""Tests of 1xBet-STYLE FIXED proxy grouping on frozen Hybrid V3 selection."""
from __future__ import annotations
import csv
import json
import math
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

from single_ml_v3 import HYBRID_NAME
from ml_v3_grouped_scores import (WINDOWS,KS,GROUPS,SCORE_TO_GROUP,settle,
                                   month,pool,totals,validate_month)


def records(start,end,*,n=24):
    day=date.fromisoformat(start);final=date.fromisoformat(end)
    while day<=final:
        prior=str(day-timedelta(days=1))
        for i in range(n):
            predicted=("1:0","3:1","1:1","0:2","0:4")[i%5]
            actual=("2:1","0:0","1:1","1:2","0:4")[i%5]
            yield {
                "model":HYBRID_NAME,"date":str(day),"id":f"{day}-f{i:03d}",
                "predicted_score":predicted,"actual_score":actual,
                "top_probability":str(round(.25-.004*i,7)),
                "actual_probability":".12",
                "log_loss":str(-math.log(.12)),
                "top3_hit":int(predicted==actual),"hit":int(predicted==actual),
                "history_latest_day":prior,"model_fit_latest_day":prior,
                "quoted_odds":"",
            }
        day+=timedelta(days=1)


def make(path,rows):
    rows=list(rows)
    with Path(path).open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)


class GroupedV3Tests(unittest.TestCase):
    def test_exact_prematch_mapping_and_1x2_constraints(self):
        self.assertEqual(len(GROUPS),5)
        self.assertEqual(len(SCORE_TO_GROUP),15)
        self.assertEqual(set(map(len,GROUPS.values())),{3})
        case=settle("1:0","2:1")
        self.assertEqual(case["group"],"H_LOW")
        self.assertTrue(case["win"])
        self.assertFalse(case["exact"])
        self.assertTrue(case["result_1x2_win"])
        other=settle("1:0","0:2")
        self.assertFalse(other["win"])
        # Never claim that an unlisted exact score is an offered group.
        unknown=settle("0:4","0:4")
        self.assertFalse(unknown["covered"])
        self.assertFalse(unknown["win"])
        self.assertTrue(unknown["exact"])

    def test_original_topk_preserved_with_abstention_and_1x2_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0]
            p=Path(tmp)/"predictions.csv";make(p,records(a,b))
            r=month(p,start=a,end=b)
            validate_month(r)
            self.assertEqual(len(r["daily"]["5"]),31)
            first=r["daily"]["5"][0]
            self.assertEqual(first["exact_hits_full_k"],2) # 1-1 and ungrouped 0-4
            self.assertEqual(first["grouped_hits"],3) # 1-0, 1-1, 0-2
            self.assertEqual(first["abstentions"],1) # score 0-4
            self.assertEqual(first["result_1x2_hits_full_k"],4)
            self.assertGreater(first["group_extra_hits_vs_covered_exact"],0)
            self.assertEqual(first["grouped_hits"],first["group_counts"]["H_LOW"]+
              first["group_counts"]["A_LOW"]+first["group_counts"]["DRAW_LOW"])
            self.assertEqual(totals(r["daily"]["5"])["selection_slots"],31*5)

    def test_future_fit_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];r=list(records(a,b))
            r[0]["model_fit_latest_day"]=a
            p=Path(tmp)/"bad.csv";make(p,r)
            with self.assertRaisesRegex(ValueError,"provenance"):
                month(p,start=a,end=b)

    def test_missing_model_day_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];r=list(records(a,b))
            r=[x for x in r if x["date"]!=a]
            p=Path(tmp)/"bad.csv";make(p,r)
            with self.assertRaisesRegex(ValueError,"fewer than 20"):
                month(p,start=a,end=b)

    def test_duplicate_match_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];r=list(records(a,b));r.append(dict(r[0]))
            p=Path(tmp)/"bad.csv";make(p,r)
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                month(p,start=a,end=b)

    def test_all_ten_periods_and_october_partial_stay_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for i,(a,b) in enumerate(WINDOWS):
                f=Path(tmp)/f"history{i}.csv";make(f,records(a,b))
                r=month(f,start=a,end=b)
                p=Path(tmp)/f"period{i}.json"
                p.write_text(json.dumps(r),encoding="utf8")
                paths.append(p)
            with self.assertRaisesRegex(ValueError,"exactly 10"):
                pool(paths[:-1])
            result=pool(paths)
            self.assertEqual(result["primary"]["10"]["days"],273)
            self.assertEqual(result["october_partial_1_to_24"]["10"]["days"],24)
            self.assertEqual(result["all_available_2026_descriptive"]["10"]["days"],297)
            self.assertTrue(result["monthly"][-1]["partial"])
            self.assertEqual(result["primary"]["10"]["selection_slots"],2730)
            self.assertGreater(result["primary"]["10"]["grouped_hits"],result["primary"]["10"]["exact_score_hits"])
            self.assertLess(result["primary"]["10"]["group_mapping_coverage_pct"],100)

    def test_group_outcome_change_cannot_modify_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0]
            original=list(records(a,b))
            first=Path(tmp)/"before.csv";make(first,original)
            report1=month(first,start=a,end=b)
            for row in original:
                row["actual_score"]="10:10"
                row["hit"]=0
                row["top3_hit"]=0
            second=Path(tmp)/"after.csv";make(second,original)
            report2=month(second,start=a,end=b)
            for k in KS:
                self.assertEqual(
                    [r["group_counts"] for r in report1["daily"][str(k)]],
                    [r["group_counts"] for r in report2["daily"][str(k)]])
                self.assertNotEqual(
                    [r["grouped_hits"] for r in report1["daily"][str(k)]],
                    [r["grouped_hits"] for r in report2["daily"][str(k)]])


if __name__=="__main__":unittest.main()
