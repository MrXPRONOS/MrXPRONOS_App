"""Synthetic security/temporal/coverage tests of 2024/25-fitted 2026 holdout."""
from __future__ import annotations
import csv,json,math,tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
from ml_v3_topk_2026_frozen import WINDOWS, MODELS, KS, PAIRINGS, month_from_predictions, validate_month, pool
import single_ml_v2 as ml


def rows(start,end,n=24):
    start_dt=date.fromisoformat(start)
    days=(date.fromisoformat(end)-start_dt).days+1
    result=[]
    for d in range(days):
        day=str(start_dt+timedelta(days=d))
        prev=str(start_dt+timedelta(days=d-1))
        for name in MODELS:
            for i in range(n):
                predicted="1:1" if i%5==0 else "2:1"
                actual="1:1" if i%4==0 else "0:1"
                value=.4-.009*i
                result.append({
                    "model":name,"date":day,"id":f"{day}-fixture-{i}",
                    "predicted_score":predicted,"actual_score":actual,
                    "hit":int(predicted==actual),"top3_hit":int(predicted==actual),
                    "top_probability":round(value,7),
                    "actual_probability":.1,"log_loss":-math.log(.1),
                    "history_latest_day":prev,
                    "model_fit_latest_day":"2025-12-31","quoted_odds":"",
                })
    return result


def save(path, records):
    with Path(path).open("w",encoding="utf8",newline="") as fd:
        writer=csv.DictWriter(fd,fieldnames=list(records[0]))
        writer.writeheader();writer.writerows(records)


class Strict2026HoldoutTests(unittest.TestCase):
    def test_all_eight_models_and_topk_for_first_2026_month(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];f=Path(tmp)/"rows.csv"
            save(f,rows(a,b))
            data=month_from_predictions(f,start=a,end=b)
            validate_month(data)
            self.assertEqual(len(data["days"]),31)
            self.assertEqual(set(data["daily"]),set(MODELS))
            for model in MODELS:
                for k in KS:
                    self.assertEqual(len(data["daily"][model][str(k)]),31)
                    self.assertEqual(sum(x["n"] for x in data["daily"][model][str(k)]),31*k)

    def test_fit_provenance_rejects_any_2026_fit_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=WINDOWS[0];x=rows(a,b)
            x[0]["model_fit_latest_day"]="2026-01-01"
            f=Path(tmp)/"bad.csv";save(f,x)
            with self.assertRaisesRegex(ValueError,"2026 target label leakage"):
                month_from_predictions(f,start=a,end=b)

    def test_frozen_training_does_not_use_2026_results_even_for_later_month(self):
        # 380 earlier matches + two 2026 evaluation dates after 2026
        # form histories have been updated from earlier 2026 final scores.
        old=date(2025,10,1)
        sample=[]
        for i in range(390):
            dt=old+timedelta(days=i//15)
            sample.append(ml.Match(key=f"past-{i}",day=dt,
                    league="synthetic",home=f"H{i%11}",away=f"A{i%13}",
                    hg=i%3,ag=(i//4)%3))
        for dt in (date(2026,1,1),date(2026,1,2),date(2026,3,1),date(2026,3,2)):
            for i in range(2):
                sample.append(ml.Match(key=f"future-{dt}-{i}",day=dt,
                    league="synthetic",home=f"H{i}",away=f"A{i}",
                    hg=2,ag=0))
        observed_fit_lengths=[]
        def check_training(train, **kwargs):
            observed_fit_lengths.append(len(train))
            self.assertEqual(len(train),390)
            return None
        def check_hist(records, **kwargs):
            self.assertEqual(len(records),390)
            self.assertTrue(all(r[3] <= date(2025,12,31) for r in records))
            return None
        with tempfile.TemporaryDirectory() as tmp:
            with (patch.object(ml,"train_ml",side_effect=check_training),
                  patch.object(ml,"train_direct_score",side_effect=check_training),
                  patch.object(ml,"fit_pair",side_effect=lambda name,train,**kw: check_training(train)),
                  patch.object(ml,"fit_hist_v3",side_effect=check_hist),
                  patch.object(ml,"fit_direct_v3",side_effect=check_training),
                  patch.object(ml,"fit_reliability",side_effect=AssertionError("No selector fit 2026")),
                  patch.object(ml,"estimate_dc_rho",return_value=-.04),
                  patch.object(ml,"estimate_shared",return_value=.1)):
                ml.backtest(sample,date(2026,3,1),date(2026,3,2),
                    tmp,auto_tune=False,v3_models=True,
                    frozen_fit_cutoff=date(2025,12,31))
            report=json.loads((Path(tmp)/"summary.json").read_text())
            self.assertTrue(report["frozen_pre2026_fit"])
            self.assertTrue(report["no_2026_labels_for_coefficients"])
            self.assertEqual(report["frozen_fit_sample_count"],390)
            self.assertEqual(report["frozen_fit_latest_utc_date"],"2025-10-26")
            self.assertEqual(len(observed_fit_lengths),4) # HistGB, direct, two competitors + V3 direct? actually count
            self.assertEqual(len(report["hybrid_calibration_history"]),1)
            self.assertEqual(len(report["v3_calibration_audit"]),0)

    def test_frozen_mode_rejects_evaluation_within_2025_or_tuning(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"Frozen-fit"):
                ml.backtest([],date(2025,12,10),date(2026,1,1),tmp,
                            auto_tune=False,frozen_fit_cutoff=date(2025,12,31))
            with self.assertRaisesRegex(ValueError,"Frozen-fit"):
                ml.backtest([],date(2026,1,1),date(2026,1,2),tmp,
                            auto_tune=True,frozen_fit_cutoff=date(2025,12,31))

    def test_all_ten_months_and_297_days_pooled(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[]
            for j,(a,b) in enumerate(WINDOWS):
                f=Path(tmp)/f"input{j}.csv";save(f,rows(a,b))
                r=month_from_predictions(f,start=a,end=b)
                p=Path(tmp)/f"out{j}.json";p.write_text(json.dumps(r),encoding="utf8")
                files.append(p)
            with self.assertRaisesRegex(ValueError,"All ten"):
                pool(files[:-1],n_boot=3)
            full=pool(files,n_boot=12)
            self.assertEqual(full["days"],297)
            self.assertEqual(full["eligible_matches"],297*24)
            self.assertEqual(full["overall"]["5"][MODELS[0]]["selected"],297*5)
            self.assertEqual(len(full["monthly"]),10)
            self.assertEqual(full["holdout_through"],"2026-10-24")
            self.assertEqual(len(full["paired_daily_bootstrap"]["paired_v3_minus_v2_pp_ci95"]["5"]),len(PAIRINGS))


if __name__=="__main__":
    unittest.main()
