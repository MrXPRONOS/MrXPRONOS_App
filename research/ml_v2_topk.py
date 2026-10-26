#!/usr/bin/env python3
"""Offline ML V2 exact-score Top-K daily selection and four-month pooled tests.

PRE-MATCH ranking: highest top_probability (the model's modal score mass).
Post-match labels are used ONLY to settle frozen selections. No retrospective
optimization, no bookmaker odds, no source fixtures exported. 5 models
independently choose 5 / 10 / 20 from an IDENTICAL daily candidate universe.
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

from single_ml_v2_multisource_compare import MODELS
from single_ml_v2_validation import wilson

WINDOWS = (
    ("2025-10-01", "2025-10-31"),
    ("2026-01-01", "2026-01-31"),
    ("2026-04-01", "2026-04-30"),
    ("2026-09-01", "2026-09-30"),
)
KS = (5, 10, 20)
SEED = 20261026
BOOTSTRAPS = 4000


def _safe_output(path):
    p = Path(path)
    if not p.resolve().is_relative_to(Path("/tmp").resolve()):
        raise ValueError("Only ephemeral /tmp aggregate research output permitted")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _check_row(row, *, start, end):
    name = row.get("model")
    day = row.get("date", "")
    if name not in MODELS or day < start or day > end:
        return None
    try:
        d = date.fromisoformat(day)
        confidence = float(row["top_probability"])
        actual_probability = float(row["actual_probability"])
        log_loss = float(row["log_loss"])
        top3 = int(row["top3_hit"])
        hit = int(row["hit"])
        prediction = row["predicted_score"]
        actual = row["actual_score"]
        history = row["history_latest_day"]
        fitted = row["model_fit_latest_day"]
        key = row["id"]
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError("Invalid research prediction fields") from e
    if (not key or not prediction or not actual or not history
        or date.fromisoformat(history) >= d):
        raise ValueError("Missing match or prior-day freeze / label leakage")
    if not fitted or date.fromisoformat(fitted) >= d:
        raise ValueError("Missing fitted model provenance or future model")
    for score in (prediction, actual):
        pieces = score.split(":")
        if (len(pieces) != 2
            or any(not p.isdigit() or not 0 <= int(p) <= 10 for p in pieces)):
            raise ValueError("Invalid goal score")
    # The source exporter rounds each floating value to 7 decimal places.
    # A genuine tiny actual-score probability (<5e-8) becomes exactly 0.0
    # in its CSV, while its original loss still encodes that probability.
    # Compare exp(-loss) with the unrounded probability INTERVAL instead
    # of taking log(0) or rejecting valid high-loss score observations.
    probability_from_loss = math.exp(-log_loss) if math.isfinite(log_loss) and 0<=log_loss<=35 else -1.
    if (not all(map(math.isfinite,(confidence,actual_probability,log_loss)))
        or not 0 < confidence <= 1 or not 0 <= actual_probability <= confidence+1e-6
        or hit not in (0,1) or top3 not in (0,1)
        or hit != int(prediction == actual) or top3 < hit
        or probability_from_loss < 0
        or abs(probability_from_loss - actual_probability) > 0.000000055):
        raise ValueError("Invalid probability / inconsistent settled prediction")
    if row.get("quoted_odds") not in ("", "None", None):
        raise ValueError("Historical score odds unsupported in these research cohorts")
    return {
        "date":day, "id":str(key), "model":name,
        "confidence":confidence, "actual_probability":actual_probability,
        "hit":hit, "top3":top3,
        "predicted_score":prediction, "actual_score":actual,
        "log_loss":log_loss,
    }


def from_predictions(path, *, start, end):
    if (start,end) not in WINDOWS:
        raise ValueError("Only four pre-registered full months are accepted")
    grouped=defaultdict(dict)
    with open(path,newline="",encoding="utf8") as stream:
        for raw in csv.DictReader(stream):
            row=_check_row(raw,start=start,end=end)
            if row is None:continue
            key=(row["date"],row["model"])
            if row["id"] in grouped[key]:
                raise ValueError("Duplicate candidate for model/day")
            grouped[key][row["id"]]=row
    days=[str(date.fromisoformat(start)+timedelta(days=i))
          for i in range((date.fromisoformat(end)-date.fromisoformat(start)).days+1)]
    aggregates={name:{str(k):[] for k in KS} for name in MODELS}
    audit_days=[]
    for day in days:
        day_ids=None
        observed_labels=None
        for model in MODELS:
            candidates=grouped[(day,model)]
            if len(candidates)<max(KS):
                raise ValueError(f"{day} {model}: insufficient daily football games ({len(candidates)})")
            if day_ids is None:
                day_ids=set(candidates)
                observed_labels={key:row["actual_score"] for key,row in candidates.items()}
            if set(candidates)!=day_ids:
                raise ValueError(f"Candidates not identical across models on {day}")
            if any(observed_labels[key]!=row["actual_score"] for key,row in candidates.items()):
                raise ValueError(f"Outcome labels differ across models on {day}")
            ordered=sorted(candidates.values(),
                           key=lambda x:(-x["confidence"], x["id"]))
            if len({x["id"] for x in ordered})!=len(ordered):
                raise ValueError("Duplicate fixture ID in daily ranking")
            for k in KS:
                # Freeze strictly with confidence/ID; never use label in rank.
                chosen=ordered[:k]
                if len(chosen)!=k:raise ValueError("Top-K did not select exactly K")
                aggregates[model][str(k)].append({
                    "date":day,"candidate_count":len(ordered), "n":k,
                    "hits":sum(x["hit"] for x in chosen),
                    "top3_hits":sum(x["top3"] for x in chosen),
                    "days_any_hit":int(any(x["hit"] for x in chosen)),
                    "confidence_sum":round(sum(x["confidence"] for x in chosen),9),
                    "loss_sum":round(sum(x["log_loss"] for x in chosen),9),
                    "modal_11_count":sum(x["predicted_score"]=="1:1" for x in chosen),
                    "actual_11_count":sum(x["actual_score"]=="1:1" for x in chosen),
                })
        audit_days.append({"date":day,"eligible_match_count":len(day_ids)})
    result={
        "pre_registered_month":[start,end],
        "research_only":True,
        "interpretation":"Chronological retrospective replay, not time-stamped real pre-kickoff betting signals",
        "model_names":list(MODELS), "ks":list(KS), "days":days,
        "daily_candidates":audit_days, "daily_selected_aggregates":aggregates,
        "ranking_rule":"Sort each day independently by modal exact-score probability descending, stable ID tie-break. Labels never enter selection.",
        "selection_disclosures":"Different models may select different fixtures, but same eligible daily candidate universe. No price, odds, or profitability evaluation.",
    }
    return result


def _values(rows):
    num=sum(int(r["n"]) for r in rows)
    hits=sum(int(r["hits"]) for r in rows)
    top3=sum(int(r["top3_hits"]) for r in rows)
    days=len(rows)
    return {
        "selected":num, "days":days, "successes":hits,
        "hit_rate_pct":round(100*hits/num,4),
        "wilson_95_pct":wilson(hits,num),
        "top3_hit_rate_pct":round(100*top3/num,4),
        "average_exact_hits_per_day":round(hits/days,4),
        "days_with_one_or_more_exact":sum(int(r["days_any_hit"]) for r in rows),
        "at_least_one_hit_day_pct":round(100*sum(int(r["days_any_hit"]) for r in rows)/days,4),
        "avg_top_confidence_pct":round(100*sum(float(r["confidence_sum"]) for r in rows)/num,4),
        "mean_log_loss":round(sum(float(r["loss_sum"]) for r in rows)/num,6),
        "selected_modal_11_pct":round(100*sum(int(r["modal_11_count"]) for r in rows)/num,4),
    }


def _validate_period_report(item):
    pair=tuple(item.get("pre_registered_month") or [])
    if pair not in WINDOWS:raise ValueError("Not pre-registered month")
    if item.get("model_names")!=list(MODELS) or item.get("ks")!=list(KS):
        raise ValueError("Changed model or topK registry")
    if not item.get("research_only"):raise ValueError("Unverified retrospective report")
    expected_days=[str(date.fromisoformat(pair[0])+timedelta(days=i))
                   for i in range((date.fromisoformat(pair[1])-date.fromisoformat(pair[0])).days+1)]
    if item["days"]!=expected_days:
        raise ValueError("Calendar coverage incomplete")
    candidates=item["daily_candidates"]
    if [r["date"] for r in candidates]!=expected_days:
        raise ValueError("Candidate day coverage incomplete")
    if any(int(x["eligible_match_count"])<20 for x in candidates):
        raise ValueError("Insufficient daily candidate count")
    data=item.get("daily_selected_aggregates") or {}
    if set(data)!=set(MODELS):raise ValueError("Model missing from period report")
    for model in MODELS:
        if set(data[model])!=set(map(str,KS)):raise ValueError("TopK missing")
        for k in KS:
            rows=data[model][str(k)]
            if [r["date"] for r in rows]!=expected_days:raise ValueError("Selected day mismatch")
            for d,row in enumerate(rows):
                if row["n"]!=k or row["candidate_count"]!=candidates[d]["eligible_match_count"]:
                    raise ValueError("Selected count not fixed at K or different candidate universe")
                if any(not 0<=int(row[v])<=k for v in ("hits","top3_hits","modal_11_count","actual_11_count")):
                    raise ValueError("Invalid aggregate count")
                if row["top3_hits"]<row["hits"] or row["days_any_hit"]!=int(row["hits"]>0):
                    raise ValueError("Inconsistent top-K statistics")
                if k>5:
                    prior=data[model][str(5)][d]
                    if not prior["hits"]<=row["hits"]<=prior["hits"]+k-5:
                        raise ValueError("Top-K success counts violate nested selection")
                    if not prior["top3_hits"]<=row["top3_hits"]<=prior["top3_hits"]+k-5:
                        raise ValueError("Top-K top3 count violates nesting")
                    if row["confidence_sum"]+1e-7<prior["confidence_sum"]:
                        raise ValueError("Nested probability sums must increase")
                for f in ("confidence_sum","loss_sum"):
                    value=float(row[f])
                    if not math.isfinite(value) or value<0:
                        raise ValueError("Invalid daily probability statistic")
                if row["confidence_sum"]>k+1e-6:
                    raise ValueError("Confidence total exceeds 1 per match")


def _bootstrap(months, *, block_days, reps=BOOTSTRAPS):
    rng=np.random.default_rng(SEED + block_days)
    clusters=[]
    for item in months:
        # Month-stratified resampling; calendar days are units. Sensitivity
        # uses chronological 7-day blocks, without crossing month boundary.
        ndays=len(item["days"])
        clusters.append([(item, list(range(i,min(i+block_days,ndays))))
                         for i in range(0,ndays,block_days)])
    fields=[(model,k) for k in KS for model in MODELS]
    dist={p:[] for p in fields}
    diffs={(k,model):[] for k in KS for model in MODELS[1:]}
    cross_k={(model,k):[] for model in MODELS for k in (10,20)}
    for _ in range(reps):
        hits={p:0 for p in fields}
        n={p:0 for p in fields}
        for blocks in clusters:
            for index in rng.integers(0,len(blocks),size=len(blocks)):
                report,selected_indexes=blocks[int(index)]
                for model,k in fields:
                    data=report["daily_selected_aggregates"][model][str(k)]
                    for pos in selected_indexes:
                        hits[(model,k)]+=data[pos]["hits"]
                        n[(model,k)]+=k
        for model,k in fields:
            dist[(model,k)].append(100*hits[(model,k)]/n[(model,k)])
        for k in KS:
            base=dist[(MODELS[0],k)][-1]
            for model in MODELS[1:]:
                diffs[(k,model)].append(dist[(model,k)][-1]-base)
        for model in MODELS:
            for k in (10,20):
                cross_k[(model,k)].append(dist[(model,k)][-1]-dist[(model,5)][-1])
    q=lambda vals:[round(float(v),4) for v in np.quantile(vals,[.025,.975])]
    return {
        "cluster_size_days":block_days, "resamples":reps,
        "paired_by":"UTC calendar days within months; same daily universe, model-selected fixture subsets may differ",
        "hit_rate_pct_ci95":{str(k):{name:q(dist[(name,k)]) for name in MODELS} for k in KS},
        "difference_vs_histgb_pp_ci95":{
            str(k):{name:q(diffs[(k,name)]) for name in MODELS[1:]} for k in KS
        },
        "difference_vs_top5_rate_pp_ci95":{
            model:{str(k):q(cross_k[(model,k)]) for k in (10,20)} for model in MODELS
        },
    }


def pooled(paths, *, reps=BOOTSTRAPS):
    if len(paths)!=len(WINDOWS):raise ValueError("All four months required")
    by_month={}
    for path in paths:
        report=json.loads(Path(path).read_text(encoding="utf8"))
        _validate_period_report(report)
        period=tuple(report["pre_registered_month"])
        if period in by_month:raise ValueError("Duplicated month")
        by_month[period]=report
    if set(by_month)!=set(WINDOWS):
        raise ValueError("Missing pre-registered month")
    months=[by_month[p] for p in WINDOWS]
    by_model={model:{} for model in MODELS}
    by_period=[]
    for p,report in zip(WINDOWS,months):
        by_period.append({
            "month":p[0][:7], "days":len(report["days"]),
            "eligible_matches":sum(x["eligible_match_count"] for x in report["daily_candidates"]),
            "topk":{
                str(k):{model:_values(report["daily_selected_aggregates"][model][str(k)])
                        for model in MODELS}
                for k in KS
            },
        })
    overall={
        str(k):{model:_values([r for m in months for r in m["daily_selected_aggregates"][model][str(k)]])
                for model in MODELS}
        for k in KS
    }
    out={
        "research_only":True,
        "rank_rule":"Pre-outcome highest model modal exact-score probability per UTC day",
        "windows":[list(x) for x in WINDOWS],
        "months":len(WINDOWS), "days":sum(len(m["days"]) for m in months),
        "eligible_matches":sum(x["eligible_matches"] for x in by_period),
        "pre_registered_topk":list(KS), "models":list(MODELS),
        "monthly":by_period, "overall":overall,
        "bootstrap_paired_utc_days":_bootstrap(months,block_days=1,reps=reps),
        "bootstrap_7day_block_sensitivity":_bootstrap(months,block_days=7,reps=reps),
        "limits":"Retrospective; different selected matches by model; full day known retrospectively; no verified pre-kickoff market odds; do not assume positive financial ROI.",
    }
    return out


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="action",required=True)
    day=sub.add_parser("month")
    day.add_argument("--predictions",required=True)
    day.add_argument("--start",required=True)
    day.add_argument("--end",required=True)
    day.add_argument("--out",required=True)
    pooling=sub.add_parser("pool")
    pooling.add_argument("--inputs",nargs="+",required=True)
    pooling.add_argument("--out",required=True)
    pooling.add_argument("--resamples",type=int,default=BOOTSTRAPS)
    args=ap.parse_args()
    if args.action=="month":
        item=from_predictions(args.predictions,start=args.start,end=args.end)
        _validate_period_report(item)
        _safe_output(args.out).write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding="utf8")
        print("ML_V2_DAILY_TOPK_MONTH",json.dumps({
            "month":args.start[:7],
            "days":len(item["days"]),
            "candidate_matches":sum(v["eligible_match_count"] for v in item["daily_candidates"]),
            "topk":{str(k):{m:_values(item["daily_selected_aggregates"][m][str(k)])
                             for m in MODELS} for k in KS},
        },ensure_ascii=False),flush=True)
    else:
        out=pooled(args.inputs,reps=args.resamples)
        _safe_output(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
        print("ML_V2_DAILY_TOPK_POOLED",json.dumps({
            "months":out["months"],"days":out["days"],
            "eligible_matches":out["eligible_matches"],
            "overall":out["overall"],
            "paired_difference_ci95":out["bootstrap_paired_utc_days"]["difference_vs_histgb_pp_ci95"],
            "seven_day_sensitivity_ci95":out["bootstrap_7day_block_sensitivity"]["difference_vs_histgb_pp_ci95"],
        },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
