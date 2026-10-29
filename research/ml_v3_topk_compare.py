#!/usr/bin/env python3
"""V2 versus V3 Top-5/10/20 daily exact-score comparison — research ONLY.

No retrospective selection using outcomes. Compare eight individually ranked
models on exactly the same daily eligible fixture universe. Publish only
daily/model aggregates. All evaluation windows MUST be frozen before use.
No external network, bookmaker odds, or production side effects.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from ml_v2_topk import _check_row, _safe_output, KS, MODELS as V2_MODELS
from single_ml_v3 import V3_MODELS
from single_ml_v2_validation import wilson

MODELS=(*V2_MODELS,*V3_MODELS)
PAIRINGS=(
    ("machine_learning","machine_learning_v3_histgb"),
    ("machine_learning_hybrid","machine_learning_v3_hybrid"),
    ("machine_learning_direct","machine_learning_v3_direct"),
)
# Frozen now; DO NOT inspect results before choosing these whole-calendar months.
WINDOWS=(
    ("2025-05-01","2025-05-31"),
    ("2025-08-01","2025-08-31"),
    ("2026-05-01","2026-05-31"),
    ("2026-08-01","2026-08-31"),
)
BOOTSTRAPS=4000
SEED=20261029


def days_in_period(start,end):
    first,last=date.fromisoformat(start),date.fromisoformat(end)
    if last<first:raise ValueError("Reversed evaluation window")
    return [str(first+timedelta(days=i)) for i in range((last-first).days+1)]


def month_from_predictions(path, *, start, end):
    if (start,end) not in WINDOWS:
        raise ValueError("Unregistered V3 holdout window")
    grouped=defaultdict(dict)
    with open(path,encoding="utf8",newline="") as fd:
        for raw in csv.DictReader(fd):
            parsed=_check_row(raw,start=start,end=end,allowed_models=MODELS)
            if parsed is None:continue
            key=(parsed["date"],parsed["model"])
            if parsed["id"] in grouped[key]:
                raise ValueError("Duplicate model fixture/day")
            grouped[key][parsed["id"]]=parsed
    days=days_in_period(start,end)
    daily={name:{str(k):[] for k in KS} for name in MODELS}
    audits=[]
    for day in days:
        reference_ids=None
        reference_results=None
        for name in MODELS:
            records=grouped[(day,name)]
            if len(records)<20:
                raise ValueError(f"{day}: {name} has only {len(records)} eligible forecasts")
            if reference_ids is None:
                reference_ids=set(records)
                reference_results={k:v["actual_score"] for k,v in records.items()}
            if set(records)!=reference_ids:
                raise ValueError(f"{day}: unequal model fixture universe")
            if any(v["actual_score"]!=reference_results[k] for k,v in records.items()):
                raise ValueError(f"{day}: contradictory actual scores for same fixture")
            # No actual score/label/hit/logloss enters this ordering.
            ordered=sorted(records.values(),key=lambda row:(-row["confidence"],row["id"]))
            for k in KS:
                top=ordered[:k]
                if len(top)!=k:
                    raise ValueError("Cannot fill predeclared Top-K quota")
                hits=sum(v["hit"] for v in top)
                daily[name][str(k)].append({
                    "day":day,"n":k,"candidates":len(ordered),
                    "hits":hits,"top3_hits":sum(v["top3"] for v in top),
                    "ge1":int(hits>=1),"ge2":int(hits>=2),"ge3":int(hits>=3),
                    "confidence_sum":round(sum(v["confidence"] for v in top),9),
                    "logloss_sum":round(sum(v["log_loss"] for v in top),9),
                    "modal_11":sum(v["predicted_score"]=="1:1" for v in top),
                })
        digest=hashlib.sha256(("\n".join(sorted(reference_ids))).encode()).hexdigest()
        audits.append({"day":day,"eligible":len(reference_ids),"cohort_sha256":digest})
    report={
        "research_only":True,"period":[start,end],
        "model_names":list(MODELS),"pairings":[list(p) for p in PAIRINGS],
        "ks":list(KS),"days":days,"daily_candidates":audits,
        "selection":"Per model top-score probability descending; stable match ID tie-break; outcome never in ranking",
        "daily":daily,
        "limitation":"Retrospective chronological replay; no independent pre-kickoff archived forecasts, no certified odds/ROI.",
    }
    validate_month(report)
    return report


def validate_month(report):
    period=tuple(report.get("period") or ())
    if (period not in WINDOWS or not report.get("research_only")
        or report.get("model_names")!=list(MODELS)
        or report.get("pairings")!=[list(p) for p in PAIRINGS]
        or report.get("ks")!=list(KS)):
        raise ValueError("Changed preregistered registry")
    days=days_in_period(*period)
    if report.get("days")!=days:
        raise ValueError("Incomplete calendar-day coverage")
    audits=report.get("daily_candidates",[])
    if [a.get("day") for a in audits]!=days:
        raise ValueError("Calendar candidate audit mismatch")
    if any(a["eligible"]<20 or len(a["cohort_sha256"])!=64 for a in audits):
        raise ValueError("Insufficient / unidentified daily match universe")
    data=report.get("daily",{})
    if set(data)!=set(MODELS):
        raise ValueError("One or more model candidates missing")
    for model in MODELS:
        if set(data[model])!=set(map(str,KS)):
            raise ValueError("Model missing Top-K level")
        for k in KS:
            rows=data[model][str(k)]
            if [r.get("day") for r in rows]!=days:
                raise ValueError("Model not evaluated every day")
            for i,row in enumerate(rows):
                if row["n"]!=k or row["candidates"]!=audits[i]["eligible"]:
                    raise ValueError("Daily quota or common fixture cohort mismatch")
                hits=row["hits"]
                if not isinstance(hits,int) or not 0<=hits<=k:
                    raise ValueError("Incorrect exact-score hits")
                if not 0<=row["top3_hits"]<=k or row["top3_hits"]<hits:
                    raise ValueError("Inconsistent Top-3")
                for threshold in (1,2,3):
                    if row[f"ge{threshold}"]!=int(hits>=threshold):
                        raise ValueError("Inconsistent daily success threshold")
                if not (math.isfinite(row["confidence_sum"])
                        and 0<row["confidence_sum"]<=k+1e-7
                        and math.isfinite(row["logloss_sum"]) and row["logloss_sum"]>=0
                        and 0<=row["modal_11"]<=k):
                    raise ValueError("Invalid aggregate probability fields")
                if k>5:
                    before=data[model]["5"][i]
                    if not before["hits"]<=hits<=before["hits"]+(k-5):
                        raise ValueError("Non-nested Top-K exact-score counts")
                if k==20:
                    before=data[model]["10"][i]
                    if not before["hits"]<=hits<=before["hits"]+10:
                        raise ValueError("Non-nested Top-10/20 exact-score counts")


def summarize(rows):
    n=sum(r["n"] for r in rows)
    hits=sum(r["hits"] for r in rows)
    ndays=len(rows)
    if not ndays or not n:
        raise ValueError("No selected forecasts")
    return {
        "days":ndays,"selected":n,"exact_scores":hits,
        "hit_rate_pct":round(100*hits/n,4),
        "wilson_95_pct":wilson(hits,n),
        "top3_pct":round(100*sum(r["top3_hits"] for r in rows)/n,4),
        "mean_logloss":round(sum(r["logloss_sum"] for r in rows)/n,6),
        "mean_top_confidence_pct":round(100*sum(r["confidence_sum"] for r in rows)/n,4),
        "modal_11_pct":round(100*sum(r["modal_11"] for r in rows)/n,4),
        "hits_per_day":round(hits/ndays,4),
        "days_at_least_1":sum(r["ge1"] for r in rows),
        "days_at_least_2":sum(r["ge2"] for r in rows),
        "days_at_least_3":sum(r["ge3"] for r in rows),
        "days_at_least_1_pct":round(100*sum(r["ge1"] for r in rows)/ndays,4),
        "days_at_least_2_pct":round(100*sum(r["ge2"] for r in rows)/ndays,4),
        "days_at_least_3_pct":round(100*sum(r["ge3"] for r in rows)/ndays,4),
        "distribution_exact_hits_per_day":{
            str(h):sum(r["hits"]==h for r in rows)
            for h in range(rows[0]["n"]+1)
        },
    }


def intervals(reports, *, block_days=1, n_boot=BOOTSTRAPS):
    """Paired by UTC day, not by chosen fixtures (models may select different matches)."""
    rng=np.random.default_rng(SEED+block_days)
    blocks_by_period=[]
    for p in reports:
        size=len(p["days"])
        blocks_by_period.append([
            (p,list(range(i,min(i+block_days,size))))
            for i in range(0,size,block_days)
        ])
    metrics=("hit_rate_pct","days_ge1_pct","days_ge2_pct","days_ge3_pct")
    paired={str(k):{f"{v2}__vs__{v3}":{metric:[] for metric in metrics}
                     for v2,v3 in PAIRINGS} for k in KS}
    for _ in range(n_boot):
        samples=[]
        for blocks in blocks_by_period:
            for idx in rng.integers(0,len(blocks),size=len(blocks)):
                p,positions=blocks[int(idx)]
                samples.extend((p,i) for i in positions)
        for k in KS:
            for base,trial in PAIRINGS:
                def accum(name):
                    daily=[p["daily"][name][str(k)][i] for p,i in samples]
                    n=k*len(daily)
                    return (100*sum(r["hits"] for r in daily)/n,
                            *(100*sum(r[f"ge{t}"] for r in daily)/len(daily)
                              for t in (1,2,3)))
                original=accum(base);candidate=accum(trial)
                for metric,a,b in zip(metrics,original,candidate):
                    paired[str(k)][f"{base}__vs__{trial}"][metric].append(b-a)
    q=lambda values:[round(float(v),4) for v in np.quantile(values,[.025,.975])]
    return {"method":"Stratified paired daily clusters across four complete months",
        "block_days":block_days,"iterations":n_boot,"seed":SEED+block_days,
        "comparison":"V3 minus its corresponding V2 model (in percentage points)",
        "paired_v3_minus_v2_pp_ci95":{
            k:{pair:{metric:q(vals) for metric,vals in measure.items()}
               for pair,measure in bypair.items()}
            for k,bypair in paired.items()
        }}


def pool(monthly_paths, *, n_boot=BOOTSTRAPS):
    if len(monthly_paths)!=len(WINDOWS):
        raise ValueError("All four preregistered whole months are required")
    reports={}
    for path in monthly_paths:
        current=json.loads(Path(path).read_text(encoding="utf8"))
        validate_month(current)
        key=tuple(current["period"])
        if key in reports:raise ValueError("Duplicate registered month")
        reports[key]=current
    if set(reports)!=set(WINDOWS):raise ValueError("Missing preregistered month")
    ordered=[reports[key] for key in WINDOWS]
    monthly=[{
        "month":report["period"][0][:7],
        "days":len(report["days"]),
        "eligible_matches":sum(a["eligible"] for a in report["daily_candidates"]),
        "topk":{str(k):{name:summarize(report["daily"][name][str(k)])
                         for name in MODELS} for k in KS},
    } for report in ordered]
    overall={str(k):{name:summarize([
            row for period in ordered for row in period["daily"][name][str(k)]])
            for name in MODELS} for k in KS}
    return {
        "research_only":True,"status":"EVALUATION_ONLY",
        "windows":[list(w) for w in WINDOWS],
        "all_models":list(MODELS),"pairings":[list(p) for p in PAIRINGS],
        "days":sum(len(r["days"]) for r in ordered),
        "eligible_matches":sum(r["eligible_matches"] for r in monthly),
        "monthly":monthly,"overall":overall,
        "paired_daily_bootstrap":intervals(ordered,block_days=1,n_boot=n_boot),
        "seven_day_block_sensitivity":intervals(ordered,block_days=7,n_boot=n_boot),
        "interpretation":"Predictions replayed chronologically, not genuinely timestamped before kick-off. No ROI or certified prematch exact-score odds. Do not infer superiority from same holdout tuning.",
    }


def main():
    ap=argparse.ArgumentParser()
    cmd=ap.add_subparsers(dest="command",required=True)
    m=cmd.add_parser("month")
    for flag in ("predictions","start","end","out"):
        m.add_argument("--"+flag,required=True)
    p=cmd.add_parser("pool")
    p.add_argument("--inputs",nargs="+",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--resamples",type=int,default=BOOTSTRAPS)
    args=ap.parse_args()
    if args.command=="month":
        result=month_from_predictions(args.predictions,start=args.start,end=args.end)
        _safe_output(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
        print("V3_TOPK_MONTH_READY",json.dumps({
            "period":result["period"],"days":len(result["days"]),
            "eligible_matches":sum(x["eligible"] for x in result["daily_candidates"]),
            "models":len(MODELS),"ks":list(KS)},ensure_ascii=False),flush=True)
    else:
        result=pool(args.inputs,n_boot=args.resamples)
        _safe_output(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
        print("V3_TOPK_POOLED",json.dumps({
            "days":result["days"],"eligible_matches":result["eligible_matches"],
            "overall":result["overall"],
            "paired_ci95":result["paired_daily_bootstrap"]["paired_v3_minus_v2_pp_ci95"]},
            ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
