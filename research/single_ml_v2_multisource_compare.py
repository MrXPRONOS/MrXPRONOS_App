#!/usr/bin/env python3
"""Independent same-fixture, leakage-checked exact-score ML V2 evaluation.

Daily aggregated counts enable a second, cross-period DAY-cluster bootstrap.
The candidate's 1-1 top-1 frequency is NOT treated as miscalibration: compare
MEAN predicted P(1-1) with empirical P(actual=1-1) instead.
No plaintext fixture CSV is uploaded or committed. Retrospective replay only.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from single_ml_v2_validation import metrics, bootstrap_difference, checked_date

MODELS = (
    "machine_learning", "machine_learning_hybrid",
    "machine_learning_lightgbm", "machine_learning_catboost",
    "machine_learning_direct",
)
MARGINS = (0.005, 0.01, 0.02)


def diagnostic(rows):
    n = len(rows)
    actual = sum(r["actual_score"] == "1:1" for r in rows)
    predictions = [r for r in rows if r["predicted_score"] == "1:1"]
    hits_11 = sum(r["actual_score"] == "1:1" for r in predictions)
    sum_p11 = sum(float(r["p_1_1"]) for r in rows)
    brier = sum((float(r["p_1_1"])-int(r["actual_score"]=="1:1"))**2 for r in rows)/n
    groups = []
    for lo, hi in ((0.,.05),(.05,.10),(.10,.15),(.15,.20),(.20,1.0000001)):
        sub = [r for r in rows if lo <= float(r["p_1_1"]) < hi]
        if sub:
            groups.append({"probability_bin":[lo,hi],"n":len(sub),
                           "mean_predicted":round(sum(float(r["p_1_1"]) for r in sub)/len(sub),5),
                           "observed":round(sum(r["actual_score"]=="1:1" for r in sub)/len(sub),5)})
    # Counterfactual-only diagnostic, NOT optimized or deployed. A different
    # modal score is selected only when 1-1 was top-1 and margin was tiny.
    alternatives = {}
    for cutoff in MARGINS:
        switched = [r for r in predictions if float(r["top2_margin"]) <= cutoff]
        old_hits = sum(r["actual_score"]=="1:1" for r in switched)
        alt_hits = sum(r["runner_up_score"]==r["actual_score"] for r in switched)
        alternatives[str(cutoff)]={"switches":len(switched),
             "baseline_correct":old_hits,"runnerup_correct":alt_hits,
             "net_hit_change":alt_hits-old_hits}
    return {
        "matches":n, "actual_1_1_n":actual,
        "actual_1_1_pct":round(100*actual/n,4),
        "top1_1_1_n":len(predictions),
        "top1_1_1_pct":round(100*len(predictions)/n,4),
        "top1_1_1_correct_n":hits_11,
        "hit_pct_given_top1_1_1":round(100*hits_11/len(predictions),4) if predictions else None,
        "mean_assigned_p_1_1_pct":round(100*sum_p11/n,4),
        "p11_probability_calibration_gap_pp":round(100*(sum_p11-actual)/n,4),
        "p11_binary_brier":round(brier,7),
        "p11_probability_bins":groups,
        "unoptimized_runnerup_diagnostics": alternatives,
    }


def daily_aggregate(day, rows):
    n=len(rows)
    return {
        "day": day, "n": n, "hits": sum(int(r["hit"]) for r in rows),
        "top3_hits": sum(int(r["top3_hit"]) for r in rows),
        "log_loss_sum": round(sum(float(r["log_loss"]) for r in rows),9),
        "top_probability_sum":round(sum(float(r["top_probability"]) for r in rows),9),
        "brier_top_sum":round(sum((int(r["hit"])-float(r["top_probability"]))**2 for r in rows),9),
        "p11_sum":round(sum(float(r["p_1_1"]) for r in rows),9),
        "p11_brier_sum":round(sum((float(r["p_1_1"])-int(r["actual_score"]=="1:1"))**2 for r in rows),9),
        "actual_11":sum(r["actual_score"]=="1:1" for r in rows),
        "top1_11":sum(r["predicted_score"]=="1:1" for r in rows),
        "correct_top1_11":sum(r["predicted_score"]=="1:1" and r["actual_score"]=="1:1" for r in rows),
    }


def paired_report(path, *, test_start, test_end, min_matches=75):
    start,end = checked_date(test_start),checked_date(test_end)
    if not start<=end:
        raise ValueError("Invalid evaluation period")
    groups=defaultdict(dict)
    seen=set()
    with open(path,encoding="utf8",newline="") as stream:
        for row in csv.DictReader(stream):
            model=row.get("model")
            if model not in MODELS:
                continue
            day=checked_date(row["date"])
            if not start<=day<=end:
                continue
            key=(row["date"],row["id"])
            if (model,*key) in seen:
                raise ValueError("Duplicated model match prediction")
            seen.add((model,*key))
            history=row.get("history_latest_day")
            fitted=row.get("model_fit_latest_day")
            if not history or checked_date(history)>=day:
                raise ValueError("Leaked or unproven previous-day fixture history")
            if model.startswith("machine_learning") and (not fitted or checked_date(fitted)>=day):
                raise ValueError("Missing/invalid model cutoff")
            expected_hit=int(row["predicted_score"]==row["actual_score"])
            if int(row["hit"]) != expected_hit:
                raise ValueError("Wrong exact-score settlement")
            p11=float(row["p_1_1"])
            top=float(row["top_probability"])
            second=float(row["runner_up_probability"])
            margin=float(row["top2_margin"])
            if (not all(math.isfinite(v) for v in (p11,top,second,margin))
                or not 0<=p11<=top+1e-5<=1.00001
                or not 0<=second<=top+1e-5
                or not -1e-6<=margin<=1
                or abs((top-second)-margin)>1e-5):
                raise ValueError("Invalid or inconsistent pre-match 1-1 score probability")
            if row["predicted_score"]=="1:1" and abs(p11-top)>1e-5:
                raise ValueError("1-1 is top-1 but p11 differs from top probability")
            if row["runner_up_score"]==row["predicted_score"]:
                raise ValueError("Runner-up must differ from top-1 score")
            if row.get("quoted_odds") not in ("",None,"None"):
                raise ValueError("Unexpected odds: this offline research cohort has no certified pre-match odds")
            groups[model][key]=row
    if any(not groups[model] for model in MODELS):
        raise ValueError("Five model outputs are not all available")
    common=set.intersection(*(set(groups[name]) for name in MODELS))
    if len(common)<min_matches:
        raise ValueError(f"Insufficient five-way same-fixture cohort: {len(common)}")
    dates=sorted({key[0] for key in common})
    if len(dates)<2:
        raise ValueError("At least 2 separate UTC evaluation dates required")
    ordered=sorted(common)
    cohort={name:[groups[name][key] for key in ordered] for name in MODELS}
    anchor=cohort[MODELS[0]]
    digest=hashlib.sha256(json.dumps(ordered,separators=(",",":")).encode("utf8")).hexdigest()
    report={
        "research_only":True,
        "interpretation":"Predeclared chronological retrospective replay; NOT independently archived prematch predictions",
        "test_start":str(start), "test_end":str(end), "model_names":list(MODELS),
        "same_fixture_cohort_n":len(common),
        "cohort_digest_sha256":digest, "utc_days":dates,
        "available_matches_by_model":{name:len(groups[name]) for name in MODELS},
        "metrics":{name:metrics(rows) for name,rows in cohort.items()},
        "score_1_1_diagnostics":{name:diagnostic(rows) for name,rows in cohort.items()},
        "daily_aggregates":{
            name:[daily_aggregate(day,[r for r in cohort[name] if r["date"]==day])
                  for day in dates] for name in MODELS
        },
        "paired_vs_histgb":{
            name:bootstrap_difference(anchor,cohort[name],resamples=2000)
            for name in MODELS[1:]
        },
        "historical_odds":"No certified correct-score pre-match odds; ROI not evaluable",
    }
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--predictions",required=True)
    p.add_argument("--start",required=True)
    p.add_argument("--end",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--minimum",type=int,default=75)
    args=p.parse_args()
    report=paired_report(args.predictions,test_start=args.start,
                         test_end=args.end,min_matches=args.minimum)
    destination=Path(args.out)
    if not destination.resolve().is_relative_to(Path("/tmp").resolve()):
        raise ValueError("Aggregate report may only be written to temporary runner storage")
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("FIVE_MODEL_LONG_PERIOD_AUDIT",json.dumps({
        "matches":report["same_fixture_cohort_n"],"days":len(report["utc_days"]),
        "metrics":{name:{s:v[s] for s in ("n","exact_hits","hit_rate_pct","mean_log_loss")}
                   for name,v in report["metrics"].items()},
        "p11":{name:{s:v[s] for s in ("actual_1_1_pct","top1_1_1_pct","mean_assigned_p_1_1_pct","p11_probability_calibration_gap_pp")}
               for name,v in report["score_1_1_diagnostics"].items()},
    },ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
