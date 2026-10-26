#!/usr/bin/env python3
"""Pool FOUR frozen chronological retrospective windows; paired day-cluster CI.

Consumes ONLY one period's *daily aggregate* metrics per model, not raw
fixtures, not future-match odds or plaintext. All windows fixed in the repo
before any new run is examined. Do not call this prospective evidence.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
import numpy as np

from single_ml_v2_multisource_compare import MODELS
from single_ml_v2_validation import wilson

WINDOWS=(
    ("2025-03-01","2025-03-28"),
    ("2025-09-01","2025-09-28"),
    ("2026-03-01","2026-03-28"),
    ("2026-09-01","2026-09-28"),
)
SEED=20261026
N_RESAMPLES=3000
REFERENCE=MODELS[0]
NUMERIC=("n","hits","top3_hits","log_loss_sum","top_probability_sum",
         "brier_top_sum","p11_sum","p11_brier_sum","actual_11",
         "top1_11","correct_top1_11")
INTS={"n","hits","top3_hits","actual_11","top1_11","correct_top1_11"}


def read_reports(paths, *, windows=WINDOWS):
    expected=set(windows)
    reports={}
    for p in paths:
        report=json.loads(Path(p).read_text(encoding="utf8"))
        period=(report.get("test_start"),report.get("test_end"))
        if period not in expected or period in reports:
            raise ValueError("Unexpected or repeated period: "+repr(period))
        if report.get("model_names")!=list(MODELS):
            raise ValueError("Different model ordering/schema across periods")
        if not report.get("research_only") or not report.get("cohort_digest_sha256"):
            raise ValueError("Missing immutable research cohort audit")
        by_model=report.get("daily_aggregates",{})
        if set(by_model)!=set(MODELS):
            raise ValueError("Missing one or more models in daily aggregates")
        normalized={}
        for model in MODELS:
            observed={}
            for d in by_model[model]:
                day=d.get("day")
                if day in observed or not period[0]<=str(day)<=period[1]:
                    raise ValueError("Duplicate or out-of-period day")
                row={key:float(d[key]) for key in NUMERIC}
                if not all(np.isfinite(list(row.values()))):
                    raise ValueError("Nonfinite daily model totals")
                if any(abs(row[k]-round(row[k]))>1e-7 for k in INTS):
                    raise ValueError("Nonintegral score count")
                if not 0<row["n"] or any(row[k]<0 for k in NUMERIC):
                    raise ValueError("Invalid daily counts/sums")
                if any(row[k]>row["n"] for k in INTS if k!="n"):
                    raise ValueError("Impossible hit or 1-1 count")
                if row["correct_top1_11"]>min(row["actual_11"],row["top1_11"]):
                    raise ValueError("Impossible 1-1 correct count")
                if row["p11_sum"]>row["n"]+1e-7:
                    raise ValueError("Invalid assigned score probability")
                observed[day]=row
            normalized[model]=observed
        anchor=normalized[REFERENCE]
        if (set(anchor)!=set(report["utc_days"])
            or len(anchor)<20):
            raise ValueError("Insufficient distinct evaluation days or unverified day set")
        for name in MODELS[1:]:
            if set(normalized[name])!=set(anchor):
                raise ValueError("Models do not share all calendar dates")
            for day in anchor:
                if (normalized[name][day]["n"]!=anchor[day]["n"]
                    or normalized[name][day]["actual_11"]!=anchor[day]["actual_11"]):
                    raise ValueError("Period cohort differs across models")
        n=sum(int(d["n"]) for d in anchor.values())
        if n != report["same_fixture_cohort_n"] or n<500:
            raise ValueError("Period had too few common verified fixtures")
        for name in MODELS:
            if report["metrics"][name]["n"]!=n:
                raise ValueError("Published period model denominator differs")
        reports[period]=normalized
    if set(reports)!=expected:
        raise ValueError("All four predeclared research periods are mandatory")
    return reports


def totals(rows):
    acc=Counter()
    for r in rows:
        for field in NUMERIC:
            acc[field]+=r[field]
    n=int(acc["n"])
    return {
      "n":n,
      "hits":int(acc["hits"]),
      "exact_hit_rate_pct":round(100*acc["hits"]/n,4),
      "wilson_95_pct":wilson(int(acc["hits"]),n),
      "top3_hit_rate_pct":round(100*acc["top3_hits"]/n,4),
      "mean_log_loss":round(acc["log_loss_sum"]/n,6),
      "brier_top1":round(acc["brier_top_sum"]/n,6),
      "predicted_top1_1_1_pct":round(100*acc["top1_11"]/n,4),
      "actual_1_1_pct":round(100*acc["actual_11"]/n,4),
      "mean_prob_1_1_pct":round(100*acc["p11_sum"]/n,4),
      "probability_1_1_calibration_gap_pp":round(100*(acc["p11_sum"]-acc["actual_11"])/n,4),
      "binary_brier_1_1":round(acc["p11_brier_sum"]/n,6),
      "hit_pct_when_1_1_top1":round(100*acc["correct_top1_11"]/acc["top1_11"],4) if acc["top1_11"] else None,
    }


def resample_intervals(reports, *, resamples=N_RESAMPLES, seed=SEED, block_days=1):
    """Same resampled UTC dates for ALL models: preserve matched comparison."""
    rng=np.random.default_rng(seed)
    strata=[]
    for period in WINDOWS:
        days=sorted(reports[period][REFERENCE])
        # block_days=7 preserves correlations between nearby fixtures.
        blocks=[days[i:i+block_days] for i in range(0,len(days),block_days)]
        strata.append((period, blocks))
    values={name:[] for name in MODELS}
    diff={name:[] for name in MODELS[1:]}
    p11_gap={name:[] for name in MODELS}
    top1_excess={name:[] for name in MODELS}
    for _ in range(resamples):
        draw={name:Counter() for name in MODELS}
        for period,blocks in strata:
            for idx in rng.integers(0,len(blocks),len(blocks)):
                for day in blocks[int(idx)]:
                    for name in MODELS:
                        d=reports[period][name][day]
                        for field in ("n","hits","log_loss_sum","p11_sum","actual_11","top1_11"):
                            draw[name][field]+=d[field]
        ref=draw[REFERENCE]
        for name in MODELS:
            cur=draw[name]
            n=cur["n"]
            values[name].append(100*cur["hits"]/n)
            p11_gap[name].append(100*(cur["p11_sum"]-cur["actual_11"])/n)
            top1_excess[name].append(100*(cur["top1_11"]-cur["actual_11"])/n)
            if name!=REFERENCE:
                diff[name].append((100*(cur["hits"]/n-ref["hits"]/ref["n"]),
                                   cur["log_loss_sum"]/n-ref["log_loss_sum"]/ref["n"]))
    q=lambda vals:[round(float(a),4) for a in np.quantile(vals,[.025,.975])]
    return {
        "method": ("stratified paired UTC-day cluster bootstrap"
                   if block_days==1 else "stratified paired non-overlapping seven-day block bootstrap sensitivity"),
        "iterations":resamples,"seed":seed,
        "windows":len(WINDOWS),"cluster_unit":"UTC day" if block_days==1 else "7-day within-window block",
        "hit_rate_95pct":{name:q(x) for name,x in values.items()},
        "p11_probability_calibration_gap_pp_95pct":{name:q(x) for name,x in p11_gap.items()},
        "top1_1_1_frequency_minus_actual_pp_95pct":{name:q(x) for name,x in top1_excess.items()},
        "paired_vs_histgb":{
            name:{
                "hit_rate_difference_pp_95pct":q([x[0] for x in items]),
                "mean_log_loss_difference_95pct":q([x[1] for x in items]),
            } for name,items in diff.items()
        },
    }


def pool(paths, *, windows=WINDOWS, resamples=N_RESAMPLES):
    if windows!=WINDOWS:
        raise ValueError("Pooling requires predefined windows, no cherry picking")
    reports=read_reports(paths,windows=windows)
    daily={name:[] for name in MODELS}
    periods=[]
    for period in WINDOWS:
        current=reports[period]
        periods.append({
            "start":period[0],"end":period[1],
            "matches":sum(int(d["n"]) for d in current[REFERENCE].values()),
            "utc_days":len(current[REFERENCE]),
            "scores":{name:totals(current[name].values()) for name in MODELS},
        })
        for name in MODELS: daily[name].extend(current[name].values())
    final={
      "research_only":True,
      "interpretation":"Unmodified 5-model retrospective walk-forward, same-fixture within each of FOUR predeclared disjoint calendar windows. NOT real-time/prospective evidence.",
      "coverage":"Four distinct 28-day windows, no tune on evaluation outcomes; no genuine pre-kickoff prediction timestamps",
      "periods":periods,
      "aggregate_matches":sum(p["matches"] for p in periods),
      "aggregate_utc_days":sum(p["utc_days"] for p in periods),
      "model_names":list(MODELS),
      "overall":{name:totals(daily[name]) for name in MODELS},
      "confidence_by_utc_day":resample_intervals(reports,resamples=resamples,seed=SEED,block_days=1),
      "sensitivity_by_7day_blocks":resample_intervals(reports,resamples=resamples,seed=SEED+1,block_days=7),
      "decision_rule":"Do not select a winner from the same holdout; consider lower log-loss, paired CI and 1-1 cell calibration, then demand independently timestamped prospective confirmation",
      "odds_and_roi":"No verified prematch correct-score odds: ROI not evaluable",
    }
    return final


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",nargs="+",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    result=pool(args.inputs)
    dest=Path(args.out)
    if not dest.resolve().is_relative_to(Path("/tmp").resolve()):
        raise ValueError("Output restricted to temporary aggregate files")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print("FOUR_PERIOD_POOLED_COMPARISON",json.dumps({
       "matches":result["aggregate_matches"],"utc_days":result["aggregate_utc_days"],
       "overall":{name:{k:result["overall"][name][k] for k in
           ("exact_hit_rate_pct","mean_log_loss","predicted_top1_1_1_pct",
            "mean_prob_1_1_pct","actual_1_1_pct")}
           for name in MODELS},
       "paired_bootstrap_ci":result["confidence_by_utc_day"]["paired_vs_histgb"],
    },ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
