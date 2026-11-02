"""Synthetic-only regression tests: parallel Top1 & Top2 group scores 2026."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from test_ml_v3_grouped_scores import records,make
from ml_v3_grouped_top1_top2 import (
  WINDOWS,KS,GROUPS,VERSION,SCORE_TO_GROUP,settle,month,pool,totals,validate_month
)


class Top1Top2GroupedTests(unittest.TestCase):
    def test_registry_and_predicted_score_only_mapping(self):
        self.assertEqual(KS,(1,2,3,5,10,20))
        self.assertEqual(len(SCORE_TO_GROUP),15)
        self.assertEqual({len(v) for v in GROUPS.values()},{3})
        self.assertIn("top1top2",VERSION)
        self.assertEqual(settle("1:0","2:1")["group"],"H_LOW")
        self.assertTrue(settle("1:0","2:1")["win"])
        self.assertFalse(settle("1:0","0:2")["win"])
        self.assertEqual(settle("1:0","2:1")["group"],settle("1:0","0:2")["group"])
        self.assertFalse(settle("0:4","0:4")["covered"])

    def test_top1_and_top2_same_matches_as_top3_and_top5(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];path=Path(tmp)/"matches.csv";make(path,records(a,b))
            result=month(path,start=a,end=b);validate_month(result)
            first={k:result["daily"][str(k)][0] for k in KS}
            # Test data ranked in ID order. First five predict 1:0,3:1,1:1,0:2,0:4.
            self.assertEqual([first[k]["grouped_hits"] for k in (1,2,3,5)], [1,1,2,3])
            self.assertEqual([first[k]["exact_hits_full_k"] for k in (1,2,3,5)], [0,0,1,2])
            self.assertEqual(first[1]["days_group_ge2"],0)
            self.assertEqual(first[2]["days_group_ge3"],0)
            for i in range(31):
                for measure in ("grouped_hits","covered","exact_hits_full_k"):
                    for k,nxt in zip(KS,KS[1:]):
                        self.assertLessEqual(result["daily"][str(k)][i][measure],
                                             result["daily"][str(nxt)][i][measure])
            self.assertEqual(totals(result["daily"]["1"])["selection_slots"],31)
            self.assertEqual(totals(result["daily"]["2"])["selection_slots"],62)
            self.assertEqual(totals(result["daily"]["3"])["selection_slots"],93)
            self.assertEqual(totals(result["daily"]["5"])["selection_slots"],155)

    def test_outcome_label_cannot_change_group_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0]
            sample=list(records(a,b))
            f=Path(tmp)/"original.csv";make(f,sample)
            before=month(f,start=a,end=b)
            for row in sample:
                row["actual_score"]="9:9";row["hit"]=0;row["top3_hit"]=0
            f2=Path(tmp)/"changed.csv";make(f2,sample)
            after=month(f2,start=a,end=b)
            for k in KS:
                self.assertEqual([r["group_counts"] for r in before["daily"][str(k)]],
                                 [r["group_counts"] for r in after["daily"][str(k)]])
            self.assertNotEqual(before["daily"]["1"][0]["grouped_hits"],
                                after["daily"]["1"][0]["grouped_hits"])

    def test_rejects_future_fitting_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];rs=list(records(a,b))
            rs[0]["model_fit_latest_day"]=a
            f=Path(tmp)/"future.csv";make(f,rs)
            with self.assertRaisesRegex(ValueError,"provenance"):month(f,start=a,end=b)
            rs=list(records(a,b));rs.append(dict(rs[0]))
            f2=Path(tmp)/"duplicates.csv";make(f2,rs)
            with self.assertRaisesRegex(ValueError,"Duplicate"):month(f2,start=a,end=b)

    def test_rejects_days_missing_or_too_few_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];rs=[r for r in records(a,b) if r["date"]!=a]
            f=Path(tmp)/"missing.csv";make(f,rs)
            with self.assertRaisesRegex(ValueError,"fewer than 20"):month(f,start=a,end=b)

    def test_strict_273_day_selection_and_separate_october_24(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for i,(a,b) in enumerate(WINDOWS):
                f=Path(tmp)/f"p{i}.csv";make(f,records(a,b))
                val=month(f,start=a,end=b)
                out=Path(tmp)/f"m{i}.json"
                out.write_text(json.dumps(val),encoding="utf8")
                paths.append(out)
            with self.assertRaisesRegex(ValueError,"exactly 10"):pool(paths[:9])
            result=pool(paths)
            self.assertEqual(result["primary"]["1"]["days"],273)
            self.assertEqual(result["primary"]["1"]["selection_slots"],273)
            self.assertEqual(result["primary"]["2"]["selection_slots"],546)
            self.assertEqual(result["primary"]["3"]["selection_slots"],819)
            self.assertEqual(result["primary"]["5"]["selection_slots"],1365)
            self.assertEqual(result["october_partial_1_to_24"]["1"]["selection_slots"],24)
            self.assertEqual(result["october_partial_1_to_24"]["2"]["selection_slots"],48)
            self.assertEqual(result["all_available_2026_descriptive"]["1"]["selection_slots"],297)
            self.assertEqual(result["all_available_2026_descriptive"]["2"]["selection_slots"],594)


if __name__=="__main__":unittest.main()
