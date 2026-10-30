"""Synthetic-only tests of second pre-registered V2/V3 four-month TopK registry."""
from __future__ import annotations
import csv
import json
import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from ml_v3_topk_round2 import (
    WINDOWS, MODELS, KS, PAIRINGS,
    month_from_predictions, validate_month, summarize, pool,
)


def synthetic_rows(start,end, *, n_matches=25):
    begin=date.fromisoformat(start)
    count=(date.fromisoformat(end)-begin).days+1
    rows=[]
    for day_index in range(count):
        day=str(begin+timedelta(days=day_index))
        prior=str(begin+timedelta(days=day_index-1))
        for name in MODELS:
            for i in range(n_matches):
                # Deliberately different rankings by model, but identical
                # fixture sets and actual match results.
                confidence=round(.30-.007*((i+MODELS.index(name))%n_matches),7)
                truth="1:1" if i%4==0 else "0:1"
                score="1:1" if i%5==0 else "2:1"
                prob=.12 if truth=="1:1" else .02
                rows.append({
                    "model":name,"date":day,"id":f"{day}-f{i:03}",
                    "predicted_score":score,"actual_score":truth,
                    "hit":int(score==truth),"top3_hit":int(score==truth),
                    "top_probability":confidence,
                    "actual_probability":prob,
                    "log_loss":-math.log(prob),
                    "history_latest_day":prior,
                    "model_fit_latest_day":prior,
                    "quoted_odds":"",
                })
    return rows


def write_csv(path,records):
    with Path(path).open("w",encoding="utf8",newline="") as fd:
        out=csv.DictWriter(fd,fieldnames=list(records[0]))
        out.writeheader()
        out.writerows(records)


class V3TopKComparisonTests(unittest.TestCase):
    def test_all_eight_models_same_daily_universe_and_nested_topk(self):
        with tempfile.TemporaryDirectory() as tmp:
            start,end=WINDOWS[0]
            path=Path(tmp)/"all.csv"
            write_csv(path,synthetic_rows(start,end))
            result=month_from_predictions(path,start=start,end=end)
            validate_month(result)
            self.assertEqual(len(result["days"]),30)
            self.assertEqual(len(result["daily"]),8)
            self.assertEqual(set(result["daily"]),set(MODELS))
            self.assertEqual({x["eligible"] for x in result["daily_candidates"]},{25})
            self.assertEqual(len({x["cohort_sha256"] for x in result["daily_candidates"]}),30)
            for k in KS:
                for name in MODELS:
                    value=summarize(result["daily"][name][str(k)])
                    self.assertEqual(value["selected"],30*k)
                    self.assertEqual(value["days"],30)
                    self.assertEqual(sum(value["distribution_exact_hits_per_day"].values()),30)
                    self.assertLessEqual(value["days_at_least_2"],value["days_at_least_1"])

    def test_missing_or_future_fitted_models_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            start,end=WINDOWS[0]
            rows=synthetic_rows(start,end)
            rows[0]["model_fit_latest_day"]=start
            path=Path(tmp)/"bad.csv"
            write_csv(path,rows)
            with self.assertRaisesRegex(ValueError,"provenance"):
                month_from_predictions(path,start=start,end=end)

    def test_unmatched_fixture_universe_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            start,end=WINDOWS[0]
            rows=synthetic_rows(start,end)
            del rows[25]  # one model misses same-day fixture
            path=Path(tmp)/"bad.csv"
            write_csv(path,rows)
            with self.assertRaisesRegex(ValueError,"unequal model fixture"):
                month_from_predictions(path,start=start,end=end)

    def test_label_change_does_not_change_topk_confidence_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            start,end=WINDOWS[0]
            records=synthetic_rows(start,end)
            one=Path(tmp)/"before.csv";write_csv(one,records)
            a=month_from_predictions(one,start=start,end=end)
            for r in records:
                r["actual_score"]="3:3"
                r["hit"]=0;r["top3_hit"]=0
            two=Path(tmp)/"after.csv";write_csv(two,records)
            b=month_from_predictions(two,start=start,end=end)
            self.assertEqual(a["daily_candidates"],b["daily_candidates"])
            for name in MODELS:
                for k in KS:
                    left=a["daily"][name][str(k)]
                    right=b["daily"][name][str(k)]
                    self.assertEqual([d["confidence_sum"] for d in left],
                                     [d["confidence_sum"] for d in right])
            self.assertNotEqual(a["daily"][MODELS[0]]["20"][0]["hits"],
                                b["daily"][MODELS[0]]["20"][0]["hits"])

    def test_require_all_four_months_before_pooled_statistics(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[]
            for i,(start,end) in enumerate(WINDOWS):
                data=Path(tmp)/f"matches{i}.csv"
                write_csv(data,synthetic_rows(start,end))
                report=month_from_predictions(data,start=start,end=end)
                p=Path(tmp)/f"report{i}.json"
                p.write_text(json.dumps(report),encoding="utf8")
                paths.append(p)
            with self.assertRaisesRegex(ValueError,"All four"):
                pool(paths[:3],n_boot=10)
            result=pool(paths,n_boot=25)
            self.assertEqual(result["days"],123)
            self.assertEqual(result["eligible_matches"],123*25)
            self.assertEqual(result["overall"]["5"][MODELS[0]]["selected"],615)
            self.assertEqual(len(result["paired_daily_bootstrap"]["paired_v3_minus_v2_pp_ci95"]["10"]),3)
            for _,trial in PAIRINGS:
                self.assertIn(trial,result["overall"]["20"])

    def test_reject_an_outcome_corrupted_in_a_single_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            start,end=WINDOWS[0]
            records=synthetic_rows(start,end)
            records[25]["actual_score"]="8:8";records[25]["hit"]=0
            path=Path(tmp)/"bad.csv";write_csv(path,records)
            with self.assertRaisesRegex(ValueError,"contradictory actual scores"):
                month_from_predictions(path,start=start,end=end)


if __name__=="__main__":
    unittest.main()
