#!/usr/bin/env python3
"""Full-calendar 2026 walk-forward experiment, low/stable H2H priority.

All completed 2026 fixtures are evaluated in kickoff order, even if the
model declines one: coverage and rejection reason are audited.
H2H decisions use only previously settled matches (4h safety delay).
The optional probability adjustment is tuned on 2025, frozen for 2026.
"""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from math import log
from bsd_v2_core import V2History, estimate_goals, fixture_datetime, outcome_scores
from exact_scores import (matrix_for, top_scores, fit_rho_2024, fit_goal_scales_2025,
                          feature_rows)
from exact_scores_h2h import H2HIndex, h2h_signal, blended_goals


def metric_bucket():
    return {"n":0, "top1":0, "top3":0, "nll":0.0, "brier":0.0, "expected_top1":0.0}

def observe(bucket, probs, actual):
    t=top_scores(probs)
    p=probs.get(actual,0)
    bucket["n"]+=1
    bucket["top1"]+=int(actual==t[0][0])
    bucket["top3"]+=int(actual in [s for s,_ in t])
    bucket["nll"]-=log(max(p,1e-12))
    bucket["brier"]+=sum(x*x for x in probs.values()) -2*p+1
    bucket["expected_top1"]+=t[0][1]


def summary(b):
    n=b["n"]
    if not n: return {"evaluated":0}
    return {
        "evaluated":n, "top1_hits":b["top1"], "top3_hits":b["top3"],
        "top1_rate":round(b["top1"]/n,5),
        "top3_rate":round(b["top3"]/n,5),
        "mean_top1_probability":round(b["expected_top1"]/n,5),
        "log_loss":round(b["nll"]/n,5),
        "multiclass_brier":round(b["brier"]/n,5),
    }


def tune_influence(index, hindex, parameters, max_2025=1400):
    rows=[]
    checked=0
    for e in (e for _,e in index.global_games if fixture_datetime(e).year==2025):
        checked+=1
        if max_2025 and checked>max_2025:
            break
        f,reason=estimate_goals(e,index)
        if not f: continue
        signal=h2h_signal(hindex.past_scores(e))
        if not signal["prioritized"]: continue
        rows.append((f,signal,outcome_scores(e)))
    options=(0,.25,.5,.75,1.)
    losses={}
    for weight in options:
        b=metric_bucket()
        for f,s,actual in rows:
            home,away=blended_goals(f["home"]*parameters["scale_home"],
                                    f["away"]*parameters["scale_away"],s,influence=weight)
            observe(b,matrix_for(home,away,rho=parameters["rho"]),actual)
        losses[str(weight)]=summary(b).get("log_loss")
    selected=0.0
    valid={w:v for w,v in ((w,losses[str(w)]) for w in options) if v is not None}
    if valid:
        candidate=min(valid,key=lambda w:(valid[w],w))
        if valid[0.0]-valid[candidate]>=.002:
            selected=candidate
    return selected,{"training_year":2025,"qualifying_matches":len(rows),
                     "checked_fixtures":checked,"candidate_nll":losses,"chosen_influence":selected,
                     "gate":"only adopt if improvement >= .002 nll"}


def evaluate_all(events, *, up_to=None, max_2025=1400):
    index=V2History(events)
    hindex=H2HIndex(index)
    rows24,_=feature_rows(index,2024,650)
    rows25,_=feature_rows(index,2025,900)
    rho,rho_info=fit_rho_2024(rows24)
    sh,sa,scale_info=fit_goal_scales_2025(rows25,rho)
    params={"rho":rho,"scale_home":sh,"scale_away":sa}
    influence,tuning=tune_influence(index,hindex,params,max_2025=max_2025)
    fixtures=[e for _,e in index.global_games if fixture_datetime(e).year==2026
              and (up_to is None or fixture_datetime(e)<=up_to)]
    fixtures.sort(key=lambda e:(fixture_datetime(e),str(e["id"])))
    rejected=Counter()
    subgroups={k:{name:metric_bucket() for name in ("poisson","base","h2h")}
               for k in ("all_eligible","prioritized","not_prioritized")}
    by_month=defaultdict(lambda:{"fixtures":0,"eligible":0,"priority":0})
    per_match=[]
    for e in fixtures:
        date=fixture_datetime(e)
        month=date.strftime("%Y-%m")
        by_month[month]["fixtures"]+=1
        record={"match_id":str(e["id"]),"kickoff":date.isoformat(),
                "actual_score":list(outcome_scores(e))}
        f,reason=estimate_goals(e,index)
        if not f:
            rejected[reason]+=1
            record["status"]="not_predictable"
            record["reason"]=reason
            per_match.append(record)
            continue
        by_month[month]["eligible"]+=1
        s=h2h_signal(hindex.past_scores(e))
        prioritized=s["prioritized"]
        if prioritized:
            by_month[month]["priority"]+=1
        record.update({"status":"evaluated","h2h":s,"lambda_home":f["home"],
                       "lambda_away":f["away"],"priority":prioritized})
        ph=f["home"]*sh
        pa=f["away"]*sa
        hh,aa=blended_goals(ph,pa,s,influence=influence)
        distributions={
            "poisson":matrix_for(f["home"],f["away"]),
            "base":matrix_for(ph,pa,rho=rho),
            "h2h":matrix_for(hh,aa,rho=rho),
        }
        for key in ("all_eligible","prioritized" if prioritized else "not_prioritized"):
            for name,m in distributions.items():
                observe(subgroups[key][name],m,tuple(record["actual_score"]))
        record["forecasts"]={}
        for name,m in distributions.items():
            tops=top_scores(m)
            record["forecasts"][name]={
                "top1":list(tops[0][0]),"top1_probability":round(tops[0][1],6),
                "top1_hit":tops[0][0]==tuple(record["actual_score"]),
                "top3_hit":tuple(record["actual_score"]) in [x for x,_ in tops],
                "top3":[{"score":list(x),"probability":round(p,6)} for x,p in tops]
            }
        per_match.append(record)
    aggregates={
        k:{model:summary(bucket) for model,bucket in models.items()}
        for k,models in subgroups.items()
    }
    return {
        "format":"mrx-exact-score-h2h-full-2026-v1","generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "full_year_2026_to_date":True,"sample_cap_2026":None,
        "time_policy":"strict prior settled fixtures; 4 hours after kickoff",
        "retrospective":True,"published":False,"used_odds":False,
        "total_finished_2026":len(fixtures),"eligible":aggregates["all_eligible"]["base"]["evaluated"],
        "rejected":dict(rejected),
        "parameters":params,"training":{"rho":rho_info,"scales":scale_info,"h2h_influence":tuning},
        "h2h_rule":{"min_meetings":3,"max_mean_total":1.75,"min_share_2_or_fewer":0.75,
                    "max_historical_total":3,"max_total_stddev":1.0,
                    "lookback_years":4,"last_h2h":8},
        "month_coverage":dict(sorted(by_month.items())),
        "comparison":aggregates,
        "note":"Priority is a screening policy; compare its coverage & hit rates against SAME-match base and all-eligible baseline. Historic archives may be revised.",
    },per_match


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history",default="bsd/all_matches_bsd.json")
    parser.add_argument("--out-dir",default="tmp/exact-scores")
    parser.add_argument("--max-2025",type=int,default=1400)
    args=parser.parse_args()
    path=Path(args.history)
    if not path.is_file(): parser.error("Encrypted BSD history must be restored privately before evaluation")
    events=json.loads(path.read_text(encoding="utf-8"))
    report,audit=evaluate_all(events,max_2025=args.max_2025)
    output=Path(args.out_dir);output.mkdir(parents=True,exist_ok=True)
    (output/"full-2026-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    # This per-match score history MUST NEVER go to GitHub Pages or public repository.
    (output/"private-per-match-audit.json").write_text(json.dumps(audit,ensure_ascii=False),encoding="utf-8")
    print("EXACT_FULL_2026",json.dumps({
        "finished":report["total_finished_2026"],"eligible":report["eligible"],
        "rejected":report["rejected"],"h2h_weight":report["training"]["h2h_influence"]["chosen_influence"],
        "comparison":report["comparison"],"months":report["month_coverage"]
    },ensure_ascii=False))


if __name__=="__main__":
    main()
