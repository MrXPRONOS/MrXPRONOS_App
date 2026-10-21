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
    observed_days={key[0] for key in by_game}
    start=date(2026,1,1)
    end=max(date.fromisoformat(x) for x in observed_days)
    calendar_days=(end-start).days+1
    league_counts=defaultdict(int)
    for item in by_game.values():
        league_counts[item["poisson"]["league"]]+=1
    audit={"input_csv_rows":total,"matches":len(by_game),
           "unique_utc_dates":len(observed_days),
           "first_actual_date":min(observed_days),
           "last_actual_date":max(observed_days),
           "calendar_days_2026_until_last_observed":calendar_days,
           "dates_without_completed_matches_in_archive":calendar_days-len(observed_days),
           "observed_date_coverage_pct":round(100*len(observed_days)/calendar_days,2),
           "leagues":len(league_counts),
           "leagues_with_100plus_matches":sum(n>=100 for n in league_counts.values()),
           "matches_in_leagues_with_100plus":sum(n for n in league_counts.values() if n>=100),
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



def walk_forward_top_probability_calibration(by_game, first_day="2026-04-01"):
    """Recalibrate only P(top predicted exact score wins), not the 121-score grid.
    Calibration parameters are fixed BEFORE evaluation, learned from prior UTC days.
    All fixtures on each UTC day are calibrated before ANY of their labels are learned.
    """
    counts={m:{"n":0,"hit":0,"sum_p":0.0,"bins":defaultdict(lambda:[0,0])} for m in MODELS}
    actual=defaultdict(list)
    diagnostics=defaultdict(list)
    day_groups=defaultdict(list)
    for key,items in by_game.items():
        day_groups[key[0]].append(items)
    for day in sorted(day_groups):
        pending=[]
        for item in day_groups[day]:
            for m in MODELS:
                r=item[m]
                raw=r["top_probability"]
                hit=r["hit"]
                b=min(19,int(raw*20))
                state=counts[m]
                # Empirical vs expected top-score event ratio, with fixed 200
                # pseudo-observations at 10% prior. No target-match label here.
                factor=(state["hit"]+20.0)/(state["sum_p"]+20.0)
                factor=max(.45,min(1.50,factor))
                adjusted_global=raw*factor
                n_bin,win_bin=state["bins"][b]
                # Local reliability shrinkage toward globally adjusted probability.
                calibrated=max(.002,min(.65,(win_bin+120*adjusted_global)/(n_bin+120)))
                if day>=first_day:
                    row={"model":m,"date":day,"hit":hit,"raw":raw,
                         "calibrated":calibrated,
                         "raw_brier":(raw-hit)**2,
                         "cal_brier":(calibrated-hit)**2,
                         "raw_binary_logloss":-(hit*math.log(raw)+(1-hit)*math.log(1-raw)),
                         "cal_binary_logloss":-(hit*math.log(calibrated)+(1-hit)*math.log(1-calibrated))}
                    actual[m].append(row)
                    diagnostics[(m,day[:7])].append(row)
                pending.append((m,b,raw,hit))
        # Update training state AFTER complete day's predictions.
        for m,b,raw,hit in pending:
            state=counts[m]
            state["n"]+=1
            state["hit"]+=hit
            state["sum_p"]+=raw
            v=state["bins"][b]
            v[0]+=1
            v[1]+=hit

    def summarise(rows):
        if not rows:
            return None
        n=len(rows)
        return {
            "n":n,
            "observed_top1_pct":round(100*sum(x["hit"] for x in rows)/n,4),
            "raw_confidence_pct":round(100*sum(x["raw"] for x in rows)/n,4),
            "recalibrated_confidence_pct":round(100*sum(x["calibrated"] for x in rows)/n,4),
            "raw_top_score_brier":round(sum(x["raw_brier"] for x in rows)/n,7),
            "recalibrated_top_score_brier":round(sum(x["cal_brier"] for x in rows)/n,7),
            "brier_gain":round(sum(x["raw_brier"]-x["cal_brier"] for x in rows)/n,7),
            "raw_top_score_binary_logloss":round(sum(x["raw_binary_logloss"] for x in rows)/n,7),
            "recalibrated_top_score_binary_logloss":round(sum(x["cal_binary_logloss"] for x in rows)/n,7)
        }
    summary={m:summarise(rows) for m,rows in actual.items()}
    monthly=[dict(model=m,month=month,**summarise(rows))
             for (m,month),rows in sorted(diagnostics.items())]
    daily=defaultdict(lambda:defaultdict(lambda:[0,0.0,0.0]))
    for model,rows in actual.items():
        for row in rows:
            cell=daily[row["date"]][model]
            cell[0]+=1
            cell[1]+=row["raw_brier"]-row["cal_brier"]
            cell[2]+=row["raw_binary_logloss"]-row["cal_binary_logloss"]
    days=sorted(daily)
    rng=random.Random(20261021)
    bootstrap_samples=defaultdict(lambda:defaultdict(list))
    for _ in range(1200):
        total={m:[0,0.0,0.0] for m in MODELS}
        for day in rng.choices(days,k=len(days)):
            values=daily[day]
            for model in MODELS:
                count,brier,log=values[model]
                cell=total[model]
                cell[0]+=count
                cell[1]+=brier
                cell[2]+=log
        for model,vec in total.items():
            if vec[0]:
                bootstrap_samples[model]["brier_gain"].append(vec[1]/vec[0])
                bootstrap_samples[model]["binary_log_loss_gain"].append(vec[2]/vec[0])
    gain_intervals={m:{k:{"lo95":round(pctile(v,.025),7),"hi95":round(pctile(v,.975),7)}
                        for k,v in values.items()}
                    for m,values in bootstrap_samples.items()}
    return {"first_evaluation_date":first_day,
            "method":"expanding prior-day reliability shrinkage with fixed global 200-sample prior and 120-bin prior; no score reranking",
            "models":summary,
            "day_cluster_bootstrap_calibration_gain_95pct":gain_intervals}, monthly

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
    forward_calibration,monthly_calibration=walk_forward_top_probability_calibration(games)
    xs={key:entries for key,entries in games.items() if "xg_poisson" in entries}
    report={
        "source_workflow_run":args.source_run,
        "audit":audit,
        "models":{m:summ(rows) for m,rows in by_model.items()},
        "paired_day_cluster_bootstrap_95pct":bootstrap(games,args.bootstrap),
        "walk_forward_top_score_calibration":forward_calibration,
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
    write_csv(out/"walk_forward_calibration_monthly.csv",monthly_calibration)
    print("STATISTICAL_AUDIT",json.dumps({
        "source_workflow_run":args.source_run,"audit":audit,
        "models":report["models"],"paired_day_cluster_bootstrap_95pct":report["paired_day_cluster_bootstrap_95pct"],
        "xg_same_match_comparison":report["xg_same_match_comparison"],
        "walk_forward_top_score_calibration":forward_calibration},ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
