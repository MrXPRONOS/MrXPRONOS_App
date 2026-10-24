#!/usr/bin/env python3
"""Independent audit of chronologically replayed football exact-score predictions.

This module NEVER fits/retunes a model and NEVER picks the winner using the
final test results. It checks row-level leakage, compares identical fixtures,
estimates uncertainty with seeded day-cluster bootstrap, reports calibration
and 1-1 concentration, and hashes its inputs. A replay after full-time is
NOT a genuinely pre-kickoff stored forecast.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
import numpy as np

AUDIT_VERSION="strict_walkforward_validation_20261024_v1"
REFERENCE="machine_learning"
ALLOWED={"machine_learning","machine_learning_direct",
         "machine_learning_catboost","machine_learning_lightgbm"}
SEED=20261024

def checked_date(value):
    try:return date.fromisoformat(str(value))
    except (TypeError,ValueError) as e:raise ValueError("Invalid ISO date: "+str(value)) from e

def split_validate(validation_start,test_start,test_end):
    v,t,e=map(checked_date,(validation_start,test_start,test_end))
    if not v<t<=e:raise ValueError("Chronological split must be validation < test_start <= test_end")
    return v,t,e

def wilson(hits,n,z=1.9599639845):
    if n==0:return None
    p=hits/n
    d=1+z*z/n
    centre=(p+z*z/(2*n))/d
    margin=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(100*max(0,centre-margin),3),round(100*min(1,centre+margin),3)]

def metrics(rows):
    n=len(rows)
    if n==0:return {"status":"NOT_EVALUABLE","n":0}
    hits=sum(int(r["hit"]) for r in rows)
    top3=sum(int(r["top3_hit"]) for r in rows)
    probs=[float(r["top_probability"]) for r in rows]
    ll=[float(r["log_loss"]) for r in rows]
    counts=Counter(r["predicted_score"] for r in rows)
    actual=Counter(r["actual_score"] for r in rows)
    bins=defaultdict(list)
    for r in rows:bins[min(9,int(float(r["top_probability"])*10))].append(r)
    calibration=[]
    for b,part in sorted(bins.items()):
        conf=sum(float(r["top_probability"]) for r in part)/len(part)
        freq=sum(int(r["hit"]) for r in part)/len(part)
        calibration.append({"bin":b,"n":len(part),"confidence":round(conf,4),
                            "observed_hit_rate":round(freq,4)})
    ece=sum(abs(x["confidence"]-x["observed_hit_rate"])*x["n"] for x in calibration)/n
    odds=[r for r in rows if r.get("quoted_odds") not in (None,"","None")]
    units=[]
    for r in odds:
        odd=float(r["quoted_odds"])
        if math.isfinite(odd) and odd>1:
            units.append(odd-1 if int(r["hit"]) else -1)
    return {
        "status":"EVALUATED","n":n,"exact_hits":hits,
        "hit_rate_pct":round(100*hits/n,3),"hit_rate_wilson_95pct":wilson(hits,n),
        "top3_hit_pct":round(100*top3/n,3),
        "mean_log_loss":round(sum(ll)/n,6),
        "brier_top_score":round(sum((int(r["hit"])-float(r["top_probability"]))**2 for r in rows)/n,6),
        "expected_calibration_error":round(ece,6),
        "calibration":calibration,
        "predicted_1_1_share_pct":round(100*counts["1:1"]/n,3),
        "actual_1_1_share_pct":round(100*actual["1:1"]/n,3),
        "predicted_score_top5":counts.most_common(5),
        "verified_quoted_odds_matches":len(units),
        "flat_stake_roi_pct":round(100*sum(units)/len(units),3) if units else None,
    }

def bootstrap_difference(first,second,*,resamples=2000):
    """Paired differences [second minus reference], clustered by UTC date."""
    a={(r["date"],r["id"]):r for r in first}
    b={(r["date"],r["id"]):r for r in second}
    if set(a)!=set(b):
        raise ValueError("Bootstrap must compare identical fixture/date pairs")
    days=sorted({key[0] for key in a})
    if len(days)<2 or resamples<10:
        return {"status":"INSUFFICIENT_DAYS","distinct_dates":len(days)}
    byday=defaultdict(list)
    for key in a:
        byday[key[0]].append((int(b[key]["hit"])-int(a[key]["hit"]),
                             float(b[key]["log_loss"])-float(a[key]["log_loss"])))
    rng=np.random.default_rng(SEED)
    diffs=[];losses=[]
    for _ in range(resamples):
        chosen=rng.choice(days,size=len(days),replace=True)
        pairs=[pair for day in chosen for pair in byday[day]]
        diffs.append(100*sum(x for x,y in pairs)/len(pairs))
        losses.append(sum(y for x,y in pairs)/len(pairs))
    return {
        "status":"EVALUATED","distinct_dates":len(days),
        "difference_hit_rate_points_95pct":[round(float(v),3) for v in np.quantile(diffs,[.025,.975])],
        "difference_log_loss_95pct":[round(float(v),6) for v in np.quantile(losses,[.025,.975])],
        "interpretation":"Second model minus reference, clustered by day; retrospective uncertainty only",
    }

def read_predictions(path, *, validation_start,test_start,test_end):
    v,t,e=split_validate(validation_start,test_start,test_end)
    with open(path,newline="",encoding="utf8") as f:
        rows=list(csv.DictReader(f))
    if not rows or rows[0].get("model") is None:
        raise ValueError("Missing populated all_predictions.csv")
    observed=set();groups=defaultdict(list)
    for row in rows:
        when=checked_date(row.get("date"))
        if when<v or when>e:
            continue
        identity=(row.get("model"),row.get("date"),row.get("id"))
        if not all(identity) or identity in observed:
            raise ValueError("Duplicate/invalid prediction key: "+str(identity))
        observed.add(identity)
        for required in ("history_latest_day","model_fit_latest_day"):
            token=row.get(required)
            if token and checked_date(token)>=when:
                raise ValueError("LEAKAGE: "+required+" is not strictly before fixture date")
        if not row.get("history_latest_day"):
            raise ValueError("Cannot audit provenance without history_latest_day")
        predicted=row.get("predicted_score","")
        actual=row.get("actual_score","")
        if not predicted or not actual:raise ValueError("Missing score in retrospective replay")
        home,away=map(int,predicted.split(":"))
        ah,aa=map(int,actual.split(":"))
        if min(home,away,ah,aa)<0 or max(home,away,ah,aa)>10:
            raise ValueError("Invalid exact-score outcome")
        if int(row["hit"])!=int((home,away)==(ah,aa)):
            raise ValueError("Corrupt hit/actual score agreement")
        for key in ("top_probability","actual_probability"):
            p=float(row[key])
            if not (math.isfinite(p) and 0<=p<=1):
                raise ValueError("Invalid probability "+key)
        if not math.isfinite(float(row["log_loss"])):
            raise ValueError("Invalid log loss")
        if abs(float(row["log_loss"])+math.log(max(float(row["actual_probability"]),1e-15)))>2e-3:
            raise ValueError("Log-loss does not match claimed actual probability")
        bucket="validation" if when<t else "test"
        groups[(bucket,row["model"])].append(row)
    return groups

def independent_report(predictions,*,validation_start,test_start,test_end,bootstrap_resamples=2000,
                       expected_archive_digest=None):
    v,t,e=split_validate(validation_start,test_start,test_end)
    path=Path(predictions)
    if not path.is_file():raise FileNotFoundError(path)
    source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    grouped=read_predictions(path,validation_start=v,test_start=t,test_end=e)
    result={
        "version":AUDIT_VERSION,
        "evaluation_type":"POST_EVENT_CHRONOLOGICAL_REPLAY_NOT_IMMUTABLE_PREKICKOFF_FORECAST",
        "prediction_file_sha256":source_hash,
        "certified_archive_sha256":expected_archive_digest,
        "periods":{"validation_start":str(v),"test_start":str(t),"test_end":str(e)},
        "models":{},
        "paired_test_comparisons":{},
    }
    for phase in ("validation","test"):
        result["models"][phase]={model:metrics(rows) for (part,model),rows in grouped.items() if part==phase}
    reference={(r["date"],r["id"]):r for r in grouped[("test",REFERENCE)]}
    for challenger in sorted(ALLOWED-{REFERENCE}):
        competitor={(r["date"],r["id"]):r for r in grouped[("test",challenger)]}
        common=sorted(set(reference)&set(competitor))
        if not common:
            result["paired_test_comparisons"][challenger]={"status":"NOT_EVALUABLE","shared_games":0}
            continue
        baseline=[reference[k] for k in common]
        alternative=[competitor[k] for k in common]
        result["paired_test_comparisons"][challenger]={
            "status":"EVALUATED","shared_games":len(common),
            "reference":metrics(baseline),"challenger":metrics(alternative),
            "paired_day_bootstrap":bootstrap_difference(baseline,alternative,resamples=bootstrap_resamples),
        }
    result["warning"]="No gains claimed without source-verified, independent pre-kickoff archives and blind forward results."
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--predictions",required=True)
    parser.add_argument("--validation-start",required=True)
    parser.add_argument("--test-start",required=True)
    parser.add_argument("--test-end",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--archive-sha256",default=None)
    args=parser.parse_args()
    report=independent_report(args.predictions,validation_start=args.validation_start,
                              test_start=args.test_start,test_end=args.test_end,
                              expected_archive_digest=args.archive_sha256)
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("INDEPENDENT_CHRONOLOGICAL_AUDIT",json.dumps({
        "models":len(report["models"]["test"]),
        "paired":{k:v.get("shared_games") for k,v in report["paired_test_comparisons"].items()},
        "sha256":report["prediction_file_sha256"]}),flush=True)
if __name__=="__main__":main()
