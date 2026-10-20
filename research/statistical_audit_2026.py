#!/usr/bin/env python3
"""Paired statistical audit of immutable GitHub Actions exact-score predictions.
The same UTC match/day must occur for all six full-coverage models.
95% confidence intervals use bootstrap resampling of WHOLE UTC match days.
No historical SportsData/odds/xG API calls; never trains on future scores.
"""
import argparse
import csv
import json
import math
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

MODELS = ("poisson","dixon_coles","bivariate_poisson","bayesian_gamma",
          "machine_learning","monte_carlo")
OTHER = ("xg_poisson","market_adjusted")


def mean(x):
    return sum(x)/len(x)


def summ(rows):
    n=len(rows)
    if not n:
        return None
    return {
        "n":n, "exact_hits":sum(r["hit"] for r in rows),
        "top1_pct":round(100*mean([r["hit"] for r in rows]),4),
        "top3_pct":round(100*mean([r["top3_hit"] for r in rows]),4),
        "log_loss":round(mean([r["log_loss"] for r in rows]),6),
        "confidence_pct":round(100*mean([r["top_probability"] for r in rows]),4),
        "top_score_brier":round(mean([(r["hit"]-r["top_probability"])**2 for r in rows]),6)
    }


def load(path):
    by_game=defaultdict(dict)
    duplicates=bad=total=0
    with open(path,newline="",encoding="utf8") as fh:
        for r in csv.DictReader(fh):
            total+=1
            try:
                model=r["model"]
                if model not in MODELS+OTHER:
                    continue
                day=str(date.fromisoformat(r["date"]))
                game=(day,str(r["id"]))
                p=float(r["top_probability"])
                logloss=float(r["log_loss"])
                hit=int(r["hit"])
                top3=int(r["top3_hit"])
                if not (0<p<=1 and math.isfinite(logloss) and logloss>=0
                        and hit in (0,1) and top3 in (0,1)
                        and hit==int(r["actual_score"]==r["predicted_score"])):
                    raise ValueError("out-of-range prediction")
                if model in by_game[game]:
                    duplicates+=1
                    continue
                by_game[game][model]={
                    "date":day, "id":game[1], "league":r["league"],
                    "actual_score":r["actual_score"], "predicted_score":r["predicted_score"],
                    "hit":hit,"top3_hit":top3, "top_probability":p,"log_loss":logloss}
            except (ValueError,KeyError,OverflowError):
                bad+=1
    if bad or duplicates:
        raise ValueError(f"Invalid input: malformed={bad} duplicate={duplicates}")
    if not by_game:
        raise ValueError("No match predictions")
    for key,entries in by_game.items():
        if not all(m in entries for m in MODELS):
            raise ValueError(f"Unpaired models on {key}")
        if len({r["actual_score"] for r in entries.values()})!=1:
            raise ValueError(f"Conflicting final score on {key}")
    audit={"input_csv_rows":total,"matches":len(by_game),
           "unique_utc_dates":len({key[0] for key in by_game}),
           "first_actual_date":min(key[0] for key in by_game),
           "last_actual_date":max(key[0] for key in by_game),
           "leagues":len({x["poisson"]["league"] for x in by_game.values()}),
           "conditional_coverage":{m:sum(m in x for x in by_game.values()) for m in OTHER}}
    return by_game,audit


def pctile(xs,fraction):
    data=sorted(xs)
    if not data:
        return None
    pos=(len(data)-1)*fraction
    i=int(pos)
    if i==len(data)-1:
        return data[i]
    return data[i]+(data[i+1]-data[i])*(pos-i)


def bootstrap(by_game,draws=1500):
    # Reweight entire date clusters to preserve schedule dependence.
    per_day=defaultdict(lambda:defaultdict(lambda:[0,0,0,0.0]))
    for (day,_),models in by_game.items():
        for m in MODELS:
            r=models[m]
            z=per_day[day][m]
            z[0]+=1
            z[1]+=r["hit"]
            z[2]+=r["top3_hit"]
            z[3]+=r["log_loss"]
    days=sorted(per_day)
    rng=random.Random(20261020)
    samples=defaultdict(lambda:defaultdict(list))
    for _ in range(draws):
        totals={m:[0,0,0,0.0] for m in MODELS}
        for day in rng.choices(days,k=len(days)):
            by_model=per_day[day]
            for m in MODELS:
                t=totals[m]
                v=by_model[m]
                for k in range(4):
                    t[k]+=v[k]
        b=totals["poisson"]
        for m in MODELS:
            n,h,t,loss=totals[m]
            samples[m]["top1_pct"].append(100*h/n)
            samples[m]["top3_pct"].append(100*t/n)
            samples[m]["log_loss"].append(loss/n)
            if m!="poisson":
                samples[m]["top1_delta_vs_poisson_pp"].append(100*(h-b[1])/n)
                samples[m]["log_loss_gain_vs_poisson"].append((b[3]-loss)/n)
    return {m:{metric:{"lo95":round(pctile(v,.025),5),"hi95":round(pctile(v,.975),5)}
               for metric,v in metrics.items()}
            for m,metrics in samples.items()}


def breakdown(by_game,dimension,threshold):
    buckets=defaultdict(list)
    for games in by_game.values():
        for model,row in games.items():
            key=row["date"][:7] if dimension=="month" else row["league"]
            buckets[(model,key)].append(row)
    return [dict(model=model,group=group,**summ(rows))
            for (model,group),rows in sorted(buckets.items()) if len(rows)>=threshold]


def write_csv(path,rows):
    if not rows:
        return
    with path.open("w",newline="",encoding="utf8") as fh:
        wr=csv.DictWriter(fh,fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--predictions",required=True)
    p.add_argument("--output",default="research/results/statistical_2026")
    p.add_argument("--source-run",default="39511299147")
    p.add_argument("--bootstrap",type=int,default=1500)
    args=p.parse_args()
    games,audit=load(args.predictions)
    by_model={m:[entries[m] for entries in games.values() if m in entries] for m in MODELS+OTHER}
    monthly=breakdown(games,"month",1)
    leagues=breakdown(games,"league",100)
    calibration=defaultdict(list)
    for entries in games.values():
        for model,row in entries.items():
            bin_id=min(9,int(row["top_probability"]*10))
            calibration[(model,bin_id)].append(row)
    cal=[dict(model=m,bin=f"{k*10}-{k*10+10}%",**summ(v),
              gap_pp=round(100*mean([x["top_probability"]-x["hit"] for x in v]),4))
         for (m,k),v in sorted(calibration.items())]
    xs={key:entries for key,entries in games.items() if "xg_poisson" in entries}
    report={
        "source_workflow_run":args.source_run,
        "audit":audit,
        "models":{m:summ(rows) for m,rows in by_model.items()},
        "paired_day_cluster_bootstrap_95pct":bootstrap(games,args.bootstrap),
        "xg_same_match_comparison":{"n":len(xs),"models":{
            m:summ([entries[m] for entries in xs.values() if m in entries])
            for m in MODELS+OTHER}},
        "notes":[
            "Resampling matched UTC days estimates sampling uncertainty, not database accuracy",
            "Top1 winner is not evidence of statistical superiority when the paired 95% interval includes zero",
            "Only 2026 matches recorded and predicted by the original workflow are assessed",
            "No original correct-score bookmaker odds -> ROI cannot be claimed",
            "Do not compare conditional xG coverage to whole-history results without matching fixtures"]
    }
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
    write_csv(out/"monthly.csv",monthly)
    write_csv(out/"leagues.csv",leagues)
    write_csv(out/"calibration.csv",cal)
    print("STATISTICAL_AUDIT",json.dumps({
        "source_workflow_run":args.source_run,"audit":audit,
        "models":report["models"],"paired_day_cluster_bootstrap_95pct":report["paired_day_cluster_bootstrap_95pct"],
        "xg_same_match_comparison":report["xg_same_match_comparison"]},ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
