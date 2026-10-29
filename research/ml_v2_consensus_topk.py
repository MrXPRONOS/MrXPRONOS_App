#!/usr/bin/env python3
"""Six systems: five unchanged exact-score models plus strict HistGB/Hybrid consensus.

Select each UTC day BEFORE reading match outcomes: individual models rank all
eligible games by their own top-score probability. Consensus requires the
SAME predicted exact score on the SAME fixture; among agreements it ranks by
MIN(p_HistGB,p_Hybrid) descending, stable fixture-ID tie break.
No forcing 5/10/20 selections if insufficient agreements. Replay only.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from ml_v2_topk import _check_row, _safe_output, MODELS, KS
from single_ml_v2_validation import wilson

WINDOWS = (
    ("2025-11-01", "2025-11-30"),
    ("2026-02-01", "2026-02-28"),
    ("2026-06-01", "2026-06-30"),
)
CONSENSUS = "histgb_hybrid_agreement"
ALL = (*MODELS, CONSENSUS)
REFERENCE = "machine_learning"
HYBRID = "machine_learning_hybrid"


def dates(start, end):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return [str(d0+timedelta(days=i)) for i in range((d1-d0).days+1)]


def make_day(rows, *, k, candidate_count, agreement_count):
    n=len(rows)
    hits=sum(int(r["hit"]) for r in rows)
    return {
        "n":n,"k":k,"candidate_count":candidate_count,
        "agreement_count":agreement_count,
        "hits":hits,"hit_ge_1":int(hits>=1),
        "hit_ge_2":int(hits>=2),"hit_ge_3":int(hits>=3),
        "confidence_sum":round(sum(float(r["confidence"]) for r in rows),9),
        "modal_11":sum(r["predicted_score"]=="1:1" for r in rows),
        "full_quota":int(n==k),
    }


def month_from_csv(path, *, start, end):
    if (start,end) not in WINDOWS:
        raise ValueError("Window must be one of three previously registered months")
    data=defaultdict(dict)
    with open(path, encoding="utf8",newline="") as stream:
        for source in csv.DictReader(stream):
            item=_check_row(source,start=start,end=end)
            if item is None:
                continue
            key=(item["date"],item["model"])
            if item["id"] in data[key]:
                raise ValueError(f"Duplicate model/day/fixture: {key}")
            data[key][item["id"]]=item
    output={name:{str(k):[] for k in KS} for name in ALL}
    days=dates(start,end)
    coverage=[]
    for day in days:
        fixture_ids=None
        actuals=None
        for model in MODELS:
            predictions=data[(day,model)]
            if len(predictions)<max(KS):
                raise ValueError(f"Incomplete daily model universe {day} {model}")
            if fixture_ids is None:
                fixture_ids=set(predictions)
                actuals={x:r["actual_score"] for x,r in predictions.items()}
            if set(predictions)!=fixture_ids:
                raise ValueError(f"Model candidate sets differ: {day} {model}")
            if any(actuals[x]!=r["actual_score"] for x,r in predictions.items()):
                raise ValueError(f"Unequal true outcome labels across models: {day}")
            ranked=sorted(predictions.values(), key=lambda r:(-r["confidence"],r["id"]))
            for k in KS:
                entry=make_day(ranked[:k], k=k,
                               candidate_count=len(fixture_ids),agreement_count=None)
                if entry["n"]!=k:
                    raise ValueError("Individual daily top-K incompletely filled")
                output[model][str(k)].append(entry)
        hist=data[(day,REFERENCE)]
        hybrid=data[(day,HYBRID)]
        consensus=[]
        for fixture in sorted(fixture_ids):
            a,b=hist[fixture],hybrid[fixture]
            if a["predicted_score"]!=b["predicted_score"]:
                continue
            # MIN confidence penalizes an optimistic model when the other is
            # uncertain; no use of ground truth in either eligibility or rank.
            consensus.append({
                "id":fixture, "confidence":min(a["confidence"],b["confidence"]),
                "predicted_score":a["predicted_score"],
                "hit":a["hit"], "actual_score":a["actual_score"],
            })
            if a["hit"]!=b["hit"]:
                raise ValueError("Identical exact-score forecast with unequal settled outcome")
        ranked=sorted(consensus,key=lambda r:(-r["confidence"],r["id"]))
        for k in KS:
            output[CONSENSUS][str(k)].append(make_day(
                ranked[:k], k=k, candidate_count=len(fixture_ids),
                agreement_count=len(consensus)))
        coverage.append({"date":day,"eligible_matches":len(fixture_ids),
                         "matching_exact_scores":len(consensus)})
    report={
        "period":[start,end],"days":days,"models":list(ALL),
        "individual_models":list(MODELS),"ks":list(KS),
        "method":"Agreement only when HistGB and hybrid predict identical exact score for same fixture. Rank by min of their modal probabilities; stable ID ties; no filling from disagreements.",
        "research_only":True,
        "warning":"Retrospective replay with known historical daily fixture universe, not genuine timestamped prematch forecasts; no ROI or odds.",
        "coverage":coverage,"daily":output,
    }
    validate_month(report)
    return report


def validate_month(report):
    period=tuple(report["period"])
    if period not in WINDOWS or report.get("models")!=list(ALL) or report.get("ks")!=list(KS) or not report.get("research_only"):
        raise ValueError("Unexpected period or changed predeclared registry")
    dd=dates(*period)
    if report["days"]!=dd or [x["date"] for x in report["coverage"]]!=dd:
        raise ValueError("Incomplete daily coverage")
    if set(report["daily"])!=set(ALL):raise ValueError("Missing model")
    for idx,day in enumerate(dd):
        cov=report["coverage"][idx]
        universe,agree=cov["eligible_matches"],cov["matching_exact_scores"]
        if universe<20 or not 0<=agree<=universe:
            raise ValueError("Invalid same-day universe or agreement count")
        for model in ALL:
            if set(report["daily"][model])!=set(map(str,KS)):
                raise ValueError("Missing K")
            previous=None
            for k in KS:
                rows=report["daily"][model][str(k)]
                if len(rows)!=len(dd):raise ValueError("Missing daily K result")
                row=rows[idx]
                n=row["n"]
                expected=k if model!=CONSENSUS else min(k,agree)
                if (n!=expected or row["k"]!=k or row["candidate_count"]!=universe
                    or row["agreement_count"]!=(agree if model==CONSENSUS else None)):
                    raise ValueError("Incorrect daily selection count")
                if row["full_quota"]!=int(n==k):
                    raise ValueError("Wrong full quota status")
                if not 0<=row["hits"]<=n or not 0<=row["modal_11"]<=n:
                    raise ValueError("Incorrect daily hits")
                for threshold in (1,2,3):
                    if row[f"hit_ge_{threshold}"]!=int(row["hits"]>=threshold):
                        raise ValueError("Incorrect daily success threshold")
                if not math.isfinite(row["confidence_sum"]) or not 0<=row["confidence_sum"]<=n+1e-6:
                    raise ValueError("Incorrect confidence total")
                if previous:
                    if not previous["hits"]<=row["hits"]<=previous["hits"]+(n-previous["n"]):
                        raise ValueError("Non-nested Top-K selected outcomes")
                    if row["confidence_sum"]+1e-6 < previous["confidence_sum"]:
                        raise ValueError("Non-nested cumulative confidence")
                previous=row


def metrics(rows):
    days=len(rows)
    n=sum(r["n"] for r in rows)
    hits=sum(r["hits"] for r in rows)
    full=sum(r["full_quota"] for r in rows)
    if not days or not n: return {"days":days,"selected":n,"scores_correct":hits,"hit_rate_pct":None,
        "days_at_least_1":0,"days_at_least_2":0,"days_at_least_3":0,"days_full_quota":full}
    return {
        "days":days,"selected":n,"scores_correct":hits,
        "hit_rate_pct":round(100*hits/n,4),
        "wilson_95_pct":wilson(hits,n),
        "average_scores_correct_per_day":round(hits/days,4),
        "days_at_least_1":sum(r["hit_ge_1"] for r in rows),
        "days_at_least_2":sum(r["hit_ge_2"] for r in rows),
        "days_at_least_3":sum(r["hit_ge_3"] for r in rows),
        "days_at_least_1_pct":round(100*sum(r["hit_ge_1"] for r in rows)/days,4),
        "days_at_least_2_pct":round(100*sum(r["hit_ge_2"] for r in rows)/days,4),
        "days_full_quota":full,
        "quota_fill_rate_pct":round(100*n/(days*rows[0]["k"]),4),
        "days_with_zero_agreements":sum(r["agreement_count"]==0 for r in rows if r["agreement_count"] is not None),
        "modal_1_1_selected_pct":round(100*sum(r["modal_11"] for r in rows)/n,4),
        "distribution_exact_hits_per_day":{
            str(i):sum(r["hits"]==i for r in rows)
            for i in range(rows[0]["k"]+1)
        },
    }


def _bootstrap(periods, *, iterations=3000, block=1):
    """Stratified by month; same resampled days for 6 systems, unequal daily n."""
    rng=np.random.default_rng(20261029+block)
    sequences={k:{m:[] for m in ALL} for k in KS}
    diff={k:{m:[] for m in (REFERENCE,HYBRID)} for k in KS}
    # Counts success-day differences and conditional hit-rate differences.
    quota={k:[] for k in KS}
    groups=[]
    for period in periods:
        length=len(period["days"])
        groups.append([(period,list(range(i,min(i+block,length)))) for i in range(0,length,block)])
    for _ in range(iterations):
        samples=[]
        for blocks in groups:
            for draw in rng.integers(0,len(blocks),size=len(blocks)):
                period,indices=blocks[int(draw)]
                samples.extend((period,i) for i in indices)
        for k in KS:
            for model in ALL:
                rows=[period["daily"][model][str(k)][i] for period,i in samples]
                sequences[k][model].append(100*sum(r["hit_ge_1"] for r in rows)/len(rows))
            for model in (REFERENCE,HYBRID):
                diff[k][model].append(sequences[k][CONSENSUS][-1]-sequences[k][model][-1])
            cr=[p["daily"][CONSENSUS][str(k)][i] for p,i in samples]
            quota[k].append(100*sum(r["full_quota"] for r in cr)/len(cr))
    q=lambda data:[round(float(x),4) for x in np.quantile(data,[.025,.975])]
    return {
        "iterations":iterations,"unit":"UTC day" if block==1 else "non-overlapping 7-day block within month",
        "success_day_rate_95pct":{str(k):{m:q(sequences[k][m]) for m in ALL} for k in KS},
        "consensus_minus_base_success_day_pp_95pct":{str(k):{m:q(diff[k][m]) for m in (REFERENCE,HYBRID)} for k in KS},
        "consensus_full_quota_day_pct_95pct":{str(k):q(quota[k]) for k in KS},
    }


def pool(paths, *, reps=3000):
    if len(paths)!=len(WINDOWS):raise ValueError("All three predeclared months are required")
    by_period={}
    for path in paths:
        item=json.loads(Path(path).read_text(encoding="utf8"))
        validate_month(item)
        period=tuple(item["period"])
        if period in by_period:raise ValueError("Duplicate period")
        by_period[period]=item
    if set(by_period)!=set(WINDOWS):
        raise ValueError("One predeclared month missing")
    period_reports=[by_period[w] for w in WINDOWS]
    monthly=[]
    for item in period_reports:
        monthly.append({
          "month":item["period"][0][:7],"days":len(item["days"]),
          "eligible_matches":sum(r["eligible_matches"] for r in item["coverage"]),
          "average_daily_agreements":round(sum(r["matching_exact_scores"] for r in item["coverage"])/len(item["days"]),3),
          "topk":{str(k):{m:metrics(item["daily"][m][str(k)]) for m in ALL} for k in KS},
        })
    pooled={str(k):{m:metrics([r for period in period_reports for r in period["daily"][m][str(k)]]) for m in ALL} for k in KS}
    result={
        "method":"Strict same-score HistGB+Hybrid consensus versus original 5 models, pre-outcome ranking only",
        "research_only":True,
        "months":list(map(list,WINDOWS)),
        "utc_days":sum(len(x["days"]) for x in period_reports),
        "eligible_matches":sum(x["eligible_matches"] for x in monthly),
        "monthly":monthly,"overall":pooled,
        "bootstrap_paired_days":_bootstrap(period_reports,iterations=reps,block=1),
        "bootstrap_7day_sensitivity":_bootstrap(period_reports,iterations=reps,block=7),
        "interpretation":"The consensus may return <K fixtures/day; its hit rate conditional on selections is NOT directly comparable to fixed-quota models. Daily >=1/2 rates include zero/agreement-scarce days. Retrospective, not independently timestamped before kickoff.",
        "financial_claims":"None: without certified actual prematch odds, no ROI can be estimated.",
    }
    return result


def main():
    a=argparse.ArgumentParser()
    commands=a.add_subparsers(dest="mode",required=True)
    m=commands.add_parser("month")
    for flag in ("predictions","start","end","out"):m.add_argument("--"+flag,required=True)
    p=commands.add_parser("pool")
    p.add_argument("--inputs",nargs="+",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--resamples",type=int,default=3000)
    args=a.parse_args()
    if args.mode=="month":
        report=month_from_csv(args.predictions,start=args.start,end=args.end)
        _safe_output(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        print("CONSENSUS_MONTH_AGGREGATE",json.dumps({
            "month":args.start[:7],"days":len(report["days"]),
            "match_candidates":sum(r["eligible_matches"] for r in report["coverage"]),
            "agreements_mean":round(sum(r["matching_exact_scores"] for r in report["coverage"])/len(report["days"]),3),
            "topk":{str(k):{model:metrics(report["daily"][model][str(k)]) for model in ALL} for k in KS},
        },ensure_ascii=False),flush=True)
    else:
        report=pool(args.inputs,reps=args.resamples)
        _safe_output(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        print("CONSENSUS_3MONTH_POOLED",json.dumps({
            "months":len(report["monthly"]),"days":report["utc_days"],
            "eligible_matches":report["eligible_matches"],"monthly":report["monthly"],
            "overall":report["overall"],
            "bootstrap_paired_days":report["bootstrap_paired_days"]["consensus_minus_base_success_day_pp_95pct"],
            "sensitivity_7day":report["bootstrap_7day_sensitivity"]["consensus_minus_base_success_day_pp_95pct"],
        },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
