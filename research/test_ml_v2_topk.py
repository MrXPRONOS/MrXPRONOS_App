"""Synthetic fixtures only: no provider data or model scores are invented as evidence."""
import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from ml_v2_topk import WINDOWS, KS, MODELS, from_predictions, pooled, _validate_period_report


def fake_rows(start, end):
    first=date.fromisoformat(start)
    length=(date.fromisoformat(end)-first).days+1
    rows=[]
    for day_offset in range(length):
        d=str(first+timedelta(days=day_offset))
        prev=str(first+timedelta(days=day_offset-1))
        for model in MODELS:
            for i in range(25):
                confidence=round(.25-i*.005,7)
                is_correct=(i%6==0)
                predicted="1:1"
                actual="1:1" if is_correct else "2:0"
                from math import log
                # Prob mass at actual must not exceed top-1 confidence.
                p=confidence if is_correct else .02
                rows.append({
                    "date":d, "id":f"{d}-fixture-{i:03d}",
                    "model":model, "history_latest_day":prev,
                    "model_fit_latest_day":prev,
                    "predicted_score":predicted,"actual_score":actual,
                    "hit":int(is_correct),"top3_hit":int(is_correct),
                    "top_probability":confidence,"actual_probability":p,
                    "log_loss":-log(p),"quoted_odds":"",
                })
    return rows


def make_csv(rows,path):
    with open(path,"w",encoding="utf8",newline="") as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class TopKTests(unittest.TestCase):
    def test_confidence_selection_nested_and_correct_without_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            start,end=WINDOWS[0]
            path=Path(temp)/"fixtures.csv"
            make_csv(fake_rows(start,end),path)
            report=from_predictions(path,start=start,end=end)
            for model in MODELS:
                self.assertEqual([r["n"] for r in report["daily_selected_aggregates"][model]["5"]],[5]*31)
                self.assertEqual(report["daily_selected_aggregates"][model]["5"][0]["hits"],1)
                self.assertEqual(report["daily_selected_aggregates"][model]["10"][0]["hits"],2)
                self.assertEqual(report["daily_selected_aggregates"][model]["20"][0]["hits"],4)
            _validate_period_report(report)

    def test_csv_rounding_of_tiny_actual_probability_is_not_a_failed_match(self):
        with tempfile.TemporaryDirectory() as temp:
            from math import log
            start,end=WINDOWS[0]
            rows=fake_rows(start,end)
            # The chosen score differs from the actual here. CSV export
            # rounds tiny mass to 0, but its log loss is still finite.
            rows[1]["actual_probability"]=0.
            rows[1]["log_loss"]=-log(1e-15)
            path=Path(temp)/"rounded.csv"
            make_csv(rows,path)
            result=from_predictions(path,start=start,end=end)
            _validate_period_report(result)
            self.assertEqual(result["daily_selected_aggregates"][MODELS[0]]["5"][0]["hits"],1)

    def test_argpartition_tie_does_not_reject_a_correct_modal_score(self):
        with tempfile.TemporaryDirectory() as temp:
            start,end=WINDOWS[0]
            rows=fake_rows(start,end)
            rows[0]["top3_hit"]=0  # legacy argpartition can drop tied argmax
            path=Path(temp)/"top3-tie.csv"
            make_csv(rows,path)
            out=from_predictions(path,start=start,end=end)
            self.assertEqual(out["daily_selected_aggregates"][MODELS[0]]["5"][0]["hits"],1)
            self.assertGreaterEqual(out["daily_selected_aggregates"][MODELS[0]]["5"][0]["top3_hits"],1)

    def test_reject_future_train(self):
        with tempfile.TemporaryDirectory() as temp:
            start,end=WINDOWS[0]
            rows=fake_rows(start,end)
            rows[0]["model_fit_latest_day"]=start
            path=Path(temp)/"bad.csv"
            make_csv(rows,path)
            with self.assertRaisesRegex(ValueError,"provenance"):
                from_predictions(path,start=start,end=end)

    def test_reject_label_change_across_models(self):
        with tempfile.TemporaryDirectory() as temp:
            start,end=WINDOWS[0]
            rows=fake_rows(start,end)
            rows[25]["actual_score"]="3:0"
            rows[25]["hit"]=0
            path=Path(temp)/"bad.csv"
            make_csv(rows,path)
            with self.assertRaisesRegex(ValueError,"Outcome labels differ"):
                from_predictions(path,start=start,end=end)

    def test_all_four_months_required_and_paired_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[]
            for i,(start,end) in enumerate(WINDOWS):
                raw=Path(temp)/f"matches-{i}.csv"
                make_csv(fake_rows(start,end),raw)
                result=from_predictions(raw,start=start,end=end)
                p=Path(temp)/f"month-{i}.json"
                p.write_text(json.dumps(result),encoding="utf8")
                paths.append(p)
            with self.assertRaisesRegex(ValueError,"All four months required"):
                pooled(paths[:3],reps=10)
            report=pooled(paths,reps=30)
            self.assertEqual(report["months"],4)
            self.assertEqual(report["days"],122)
            self.assertEqual(report["eligible_matches"],3050)
            self.assertEqual(report["overall"]["5"][MODELS[0]]["selected"],610)
            self.assertEqual(report["overall"]["10"][MODELS[0]]["successes"],244)
            self.assertEqual(report["overall"]["20"][MODELS[0]]["successes"],488)
            self.assertEqual(len(report["bootstrap_paired_utc_days"]["difference_vs_histgb_pp_ci95"]["5"]),4)


if __name__=="__main__":
    unittest.main()
