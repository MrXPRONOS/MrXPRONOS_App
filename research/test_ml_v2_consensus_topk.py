"""Test synthetic score consensus, strict scarcity and date leakage."""
import csv
import json
import math
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

from ml_v2_consensus_topk import WINDOWS, MODELS, CONSENSUS, REFERENCE, HYBRID,      month_from_csv, pool, validate_month


def fixture(start,end):
    dates=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
    rows=[]
    for j in range(dates):
        day=str(date.fromisoformat(start)+timedelta(days=j))
        prior=str(date.fromisoformat(start)+timedelta(days=j-1))
        agreed=[4,12,25][j%3]
        for model in MODELS:
            for i in range(25):
                prediction="1:1"
                if model==HYBRID and i>=agreed:
                    prediction="2:0"
                actual="1:1" if i%5==0 else "0:0"
                confidence=round(.28-.004*i,7)
                rows.append({
                    "model":model,"date":day,"id":f"{day}-fixture-{i:02}",
                    "predicted_score":prediction,"actual_score":actual,
                    "top_probability":confidence,"actual_probability":0.01,
                    "log_loss":-math.log(.01),
                    "history_latest_day":prior,"model_fit_latest_day":prior,
                    "hit":int(prediction==actual),"top3_hit":int(prediction==actual),
                    "quoted_odds":"",
                })
    return rows


def save(rows,path):
    with path.open("w",encoding="utf8",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


class ConsensusTopKTests(unittest.TestCase):
    def test_consensus_filters_exact_same_score_and_does_not_fill(self):
        with tempfile.TemporaryDirectory() as d:
            start,end=WINDOWS[0]
            path=Path(d)/"rows.csv"
            save(fixture(start,end),path)
            result=month_from_csv(path,start=start,end=end)
            validate_month(result)
            first=result["daily"][CONSENSUS]
            self.assertEqual(first["5"][0]["n"],4)
            self.assertEqual(first["10"][0]["n"],4)
            self.assertEqual(first["20"][0]["n"],4)
            self.assertEqual(first["5"][1]["n"],5)
            self.assertEqual(first["10"][1]["n"],10)
            self.assertEqual(first["20"][1]["n"],12)
            self.assertEqual(first["20"][2]["n"],20)
            self.assertEqual(result["daily"][REFERENCE]["20"][0]["n"],20)
            self.assertEqual(result["coverage"][0]["matching_exact_scores"],4)
            self.assertEqual(first["5"][0]["hits"],1)

    def test_label_changes_cannot_affect_pre_result_ranking_or_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            start,end=WINDOWS[0]
            rows=fixture(start,end)
            one=Path(d)/"first.csv"
            save(rows,one)
            a=month_from_csv(one,start=start,end=end)
            # All models' labels change together; pre-kickoff agreement count
            # and model confidence ranking must not change.
            for row in rows:
                row["actual_score"]="8:8"
                row["hit"]=0
                row["top3_hit"]=0
            two=Path(d)/"changed.csv"
            save(rows,two)
            b=month_from_csv(two,start=start,end=end)
            self.assertEqual(a["coverage"],b["coverage"])
            self.assertEqual(
                [x["n"] for x in a["daily"][CONSENSUS]["10"]],
                [x["n"] for x in b["daily"][CONSENSUS]["10"]])
            self.assertNotEqual(a["daily"][CONSENSUS]["10"][0]["hits"],
                                b["daily"][CONSENSUS]["10"][0]["hits"])

    def test_reject_future_fit_and_corrupted_model_labels(self):
        with tempfile.TemporaryDirectory() as d:
            start,end=WINDOWS[0]
            rows=fixture(start,end)
            rows[0]["model_fit_latest_day"]=start
            path=Path(d)/"bad.csv"
            save(rows,path)
            with self.assertRaisesRegex(ValueError,"provenance"):
                month_from_csv(path,start=start,end=end)

    def test_three_periods_mandatory_and_bootstrap(self):
        with tempfile.TemporaryDirectory() as folder:
            reports=[]
            for j,(start,end) in enumerate(WINDOWS):
                path=Path(folder)/f"input-{j}.csv"
                save(fixture(start,end),path)
                report=month_from_csv(path,start=start,end=end)
                p=Path(folder)/f"report-{j}.json"
                p.write_text(json.dumps(report),encoding="utf8")
                reports.append(p)
            with self.assertRaisesRegex(ValueError,"All three"):
                pool(reports[:2],reps=4)
            summary=pool(reports,reps=20)
            self.assertEqual(summary["utc_days"],88)
            self.assertEqual(summary["eligible_matches"],2200)
            self.assertLess(summary["overall"]["20"][CONSENSUS]["selected"],1760)
            self.assertEqual(summary["overall"]["5"][REFERENCE]["selected"],440)
            self.assertEqual(len(summary["bootstrap_paired_days"]["consensus_minus_base_success_day_pp_95pct"]["5"][REFERENCE]),2)


if __name__=="__main__":
    unittest.main()
