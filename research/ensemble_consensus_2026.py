#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mr XPRONOS: exact-score SIX-MODEL agreement and walk-forward backtest.

Inputs are original *saved before-match* predictions, not fitted output recomputed
using today's scores. All six models vote equally for their favourite exact score.
Tied votes are never broken by knowledge of the actual score.

Reports both EXACT agreement tiers (2/6 ... 6/6) and CUMULATIVE
strategies (minimum 3, 4, 5 or 6 votes). Strategies abstain otherwise.
Compare consensus on the exact same fixtures against each component model.

There are no bookmaker exact-score odds: hit rate != betting ROI.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

SIX = ("poisson", "dixon_coles", "bivariate_poisson",
       "bayesian_gamma", "machine_learning", "monte_carlo")
VOTE_STRATEGIES = (3, 4, 5, 6)
SOURCE_RUN = "39511299147"
TEST_START = "2026-08-01"


def read_predictions(path):
    by_match = defaultdict(dict)
    seen_rows = 0
    for row in csv.DictReader(open(path, newline="", encoding="utf8")):
        model = row.get("model")
        if model not in SIX:
            continue
        seen_rows += 1
        game = (date.fromisoformat(row["date"]).isoformat(), str(row["id"]))
        if model in by_match[game]:
            raise ValueError(f"Duplicated model fixture {game} {model}")
        score = row["predicted_score"].strip().replace("-", ":")
        actual = row["actual_score"].strip().replace("-", ":")
        for text in (score, actual):
            parts = text.split(":")
            if len(parts) != 2 or not all(x.isdigit() for x in parts):
                raise ValueError(f"Invalid score {text} on fixture {game}")
        hit = int(row["hit"])
        if hit != int(score == actual):
            raise ValueError(f"Inconsistent hit label {game} {model}")
        by_match[game][model] = {
            "predicted": score, "actual": actual, "hit": hit,
            "league": row["league"], "home": row["home"], "away": row["away"],
            "top_probability": float(row["top_probability"]),
            "log_loss": float(row["log_loss"])
        }

    decisions = []
    pairs = {p: [0, 0] for p in combinations(SIX, 2)}
    for (day, game), values in sorted(by_match.items()):
        if set(values) != set(SIX):
            raise ValueError(f"All six models must be present for {game}: {set(values)}")
        if len({x["actual"] for x in values.values()}) != 1:
            raise ValueError(f"Conflicting score outcomes for {game}")
        if len({x["league"] for x in values.values()}) != 1:
            raise ValueError(f"Conflicting leagues for {game}")
        tally = Counter(values[name]["predicted"] for name in SIX)
        most = tally.most_common()
        max_votes = most[0][1]
        winners = sorted(k for k, v in tally.items() if v == max_votes)
        tie = len(winners) > 1
        score = winners[0] if not tie else None
        actual = values["poisson"]["actual"]
        votes = [m for m in SIX if score and values[m]["predicted"] == score]
        for a, b in pairs:
            pairs[a, b][1] += 1
            pairs[a, b][0] += values[a]["predicted"] == values[b]["predicted"]
        first = values["poisson"]
        decisions.append({
            "date": day, "id": game, "league": first["league"],
            "home": first["home"], "away": first["away"],
            "actual": actual, "consensus": score, "votes": max_votes,
            "tied_for_first": tie, "selected": not tie and max_votes >= 3,
            "won": int(score == actual) if not tie else 0,
            "agreeing_models": votes,
            "all_predictions": {m: values[m]["predicted"] for m in SIX},
            "individual_hit": {m: values[m]["hit"] for m in SIX},
            "individual_probability": {m: values[m]["top_probability"] for m in SIX},
            "number_distinct_scores": len(tally)
        })
    if not decisions:
        raise ValueError("No complete fixtures")
    return decisions, pairs, seen_rows


def rate(hits, n):
    return round(hits / n * 100, 5) if n else None


def model_results(rows):
    if not rows:
        return None
    n = len(rows)
    return {m: {"hits": sum(r["individual_hit"][m] for r in rows),
                "hit_rate_pct": rate(sum(r["individual_hit"][m] for r in rows), n)}
            for m in SIX}


def chosen(rows, threshold, min_league_prior=0):
    return [r for r in rows if (not r["tied_for_first"] and
            r["votes"] >= threshold and
            r.get("league_prior", 0) >= min_league_prior)]


def metrics(selected, universe, *, interval=None):
    total = len(universe)
    n = len(selected)
    if not n:
        return {"n": 0, "coverage_pct": 0, "hit_rate_pct": None,
                "matches_skipped": total, "reason": "No unique agreement at selected threshold"}
    hits = sum(r["won"] for r in selected)
    by_model = model_results(selected)
    poisson = by_model["poisson"]["hits"]
    result = {
        "n": n, "coverage_pct": rate(n,total),
        "hits": hits, "hit_rate_pct": rate(hits,n),
        "misses": n-hits, "matches_skipped": total-n,
        "vs_poisson_on_same_matches_pp": round(100*(hits-poisson)/n,5),
        "individuals_on_same_matches": by_model,
        "observed_success_odds_inverse": round(n/hits,3) if hits else None,
    }
    if interval:
        result["day_cluster_95pct_intervals"] = interval
    return result


def bootstrap_day_cluster(selected, *, draws=1300, seed=20261021):
    if not selected:
        return None
    dates=defaultdict(lambda:[0,0,0,0,0])
    for r in selected:
        s=dates[r["date"]]
        s[0] += 1
        s[1] += r["won"]
        s[2] += r["individual_hit"]["poisson"]
        s[3] += r["individual_hit"]["machine_learning"]
        s[4] += r["individual_hit"]["dixon_coles"]
    blocks=list(dates.values())
    rng=random.Random(seed)
    intervals=defaultdict(list)
    for _ in range(draws):
        n=h=p=ml=dc=0
        for _ in range(len(blocks)):
            v=blocks[rng.randrange(len(blocks))]
            n+=v[0];h+=v[1];p+=v[2];ml+=v[3];dc+=v[4]
        if n:
            intervals["hit_rate_pct"].append(100*h/n)
            intervals["lift_vs_poisson_pp"].append(100*(h-p)/n)
            intervals["lift_vs_ml_pp"].append(100*(h-ml)/n)
            intervals["lift_vs_dixon_coles_pp"].append(100*(h-dc)/n)
    def percentile(xs, q):
        s=sorted(xs)
        at=(len(s)-1)*q
        k=int(at)
        return s[k]+(s[min(k+1,len(s)-1)]-s[k])*(at-k)
    return {metric:{"lo95":round(percentile(values,.025),5),
                    "hi95":round(percentile(values,.975),5)}
            for metric,values in intervals.items()}


def assign_past_league_coverage(rows):
    """Only earlier UTC dates count for league-size filters."""
    days=defaultdict(list)
    for r in rows:
        days[r["date"]].append(r)
    prior=Counter()
    for day in sorted(days):
        for r in days[day]:
            r["league_prior"]=prior[r["league"]]
        for r in days[day]:
            prior[r["league"]]+=1


def rolling_reliability(rows, thresholds=VOTE_STRATEGIES, start=TEST_START):
    """Learn hit frequency for each agreement threshold using prior dates only.
    This is a probability estimate of the final consensus score, NOT an extra vote.
    Beta(2,18) prior = prior mean 10%; no threshold chosen by future hit rates.
    """
    by_date=defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)
    totals={k:[0,0] for k in thresholds}
    records=defaultdict(list)
    for d in sorted(by_date):
        todays=by_date[d]
        for k in thresholds:
            accepted=chosen(todays,k)
            n,w=totals[k]
            estimated=(w+2)/(n+20)
            if d>=start:
                for r in accepted:
                    records[k].append({
                        "date":d, "predicted_probability":estimated,
                        "actual":r["won"], "n_past_selections":n
                    })
        for k in thresholds:
            accepted=chosen(todays,k)
            totals[k][0]+=len(accepted)
            totals[k][1]+=sum(r["won"] for r in accepted)
    result={}
    for k in thresholds:
        rows_out=records[k]
        n=len(rows_out)
        if not n:
            result[str(k)]={"n":0}
            continue
        real=sum(r["actual"] for r in rows_out)/n
        p=sum(r["predicted_probability"] for r in rows_out)/n
        bs=sum((r["predicted_probability"]-r["actual"])**2 for r in rows_out)/n
        result[str(k)]={"n":n,"actual_hit_rate_pct":rate(sum(r["actual"] for r in rows_out),n),
                        "estimated_pre_match_probability_pct":round(100*p,4),
                        "brier":round(bs,6),
                        "calibration_gap_pp":round(100*(p-real),4)}
    return result


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w",newline="",encoding="utf8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_report(rows, pairs, seen_rows, *, draws=1300):
    assign_past_league_coverage(rows)
    full_n=len(rows)
    groups=Counter(("tie" if x["tied_for_first"] else str(x["votes"])) for x in rows)
    whole=model_results(rows)
    periods={
        "entire_available_2026": rows,
        "discovery_jan_jul": [r for r in rows if r["date"]<TEST_START],
        "holdout_aug_oct": [r for r in rows if r["date"]>=TEST_START]
    }
    grouped={}
    for period,universe in periods.items():
        grouped[period]={
            "base_matches": len(universe),
            "individuals_all_matches": model_results(universe),
            "thresholds":{}
        }
        for votes in VOTE_STRATEGIES:
            subset=chosen(universe,votes)
            ci=bootstrap_day_cluster(subset,draws=draws,seed=20261021+votes) if len(subset)>=50 else None
            grouped[period]["thresholds"][str(votes)]=metrics(subset,universe,interval=ci)

    tiers={}
    for votes in (1,2,3,4,5,6):
        subset=[r for r in rows if not r["tied_for_first"] and r["votes"]==votes]
        tiers[str(votes)]=metrics(subset,rows)
    ties=[r for r in rows if r["tied_for_first"]]
    strict_league={}
    holdout=periods["holdout_aug_oct"]
    for min_n in (30,100):
        strict_league[str(min_n)]={
            str(k):metrics(chosen(holdout,k,min_league_prior=min_n),holdout)
            for k in VOTE_STRATEGIES
        }
    agreements=[{
        "model_a":a,"model_b":b,"same_score_count":values[0],
        "same_score_pct":rate(values[0],values[1])
    } for (a,b),values in sorted(pairs.items())]
    report={
        "source_workflow_run":SOURCE_RUN,
        "method":"Top-1 score, equal weight for six frozen independently computed models; unique plurality wins; tie means ABSTAIN",
        "validation":"No model retrained; all post-match information used for metrics only; holdout fixed Aug 1, 2026",
        "first_date":rows[0]["date"],"last_date":rows[-1]["date"],
        "n_total_matches":full_n,"source_rows_used":seen_rows,
        "underlying_model_performance":whole,
        "votes_distribution":{"unique_1_to_6_and_ties":dict(groups)},
        "exclusive_agreement_tiers":tiers,
        "cumulative_strategies":grouped,
        "pairwise_score_agreement":agreements,
        "holdout_restrict_by_previous_league_matches":strict_league,
        "holdout_walk_forward_vote_confidence":rolling_reliability(rows),
        "caveats":[
            "Agreeing models use overlapping football inputs: votes are correlated, not independent probabilities.",
            "Consensus and individual results are compared on exactly the same selected matches.",
            "No quoted pre-match CORRECT SCORE odds => ROI and value-bet claims are NOT evaluable.",
            "Strict agreement may select only easy-to-model fixtures: a higher hit rate may reflect selection, not better probabilities.",
            "Historical fixture coverage is incomplete; CI does not correct missing competitions/days.",
            "Testing four vote thresholds can bias selection after looking at results; holdout shown separately.",
        ]}
    return report


def run(args):
    rows,pairs,count=read_predictions(args.predictions)
    report=build_report(rows,pairs,count,draws=args.bootstrap)
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
    predictions=[]
    for r in rows:
        predictions.append({
            "date":r["date"],"game_id":r["id"],"league":r["league"],
            "home":r["home"],"away":r["away"],"actual_score":r["actual"],
            "consensus_score":r["consensus"] or "ABSTAIN",
            "highest_votes":r["votes"],"tied_for_first":int(r["tied_for_first"]),
            "winning_prediction":r["won"] if not r["tied_for_first"] else "",
            "models_agreeing":";".join(r["agreeing_models"]),
            **{f"vote_{m}":r["all_predictions"][m] for m in SIX}
        })
    write_csv(out/"all_consensus_decisions.csv",predictions)
    monthly=[]
    by_group=defaultdict(list)
    for r in rows:
        for k in VOTE_STRATEGIES:
            by_group[(r["date"][:7],k)].append(r)
    for (month,k),allrows in sorted(by_group.items()):
        result=metrics(chosen(allrows,k),allrows)
        monthly.append({"month":month,"threshold":k,
                        **{x:result.get(x) for x in ("n","hits","coverage_pct","hit_rate_pct","vs_poisson_on_same_matches_pp")}})
    write_csv(out/"monthly.csv",monthly)
    by_league=defaultdict(list)
    for r in rows:
        by_league[r["league"]].append(r)
    per_league=[]
    for league,items in by_league.items():
        if len(items)<100:
            continue
        for k in VOTE_STRATEGIES:
            result=metrics(chosen(items,k),items)
            per_league.append({"league":league,"total_matches":len(items),"threshold":k,
                               **{x:result.get(x) for x in ("n","hits","coverage_pct","hit_rate_pct","vs_poisson_on_same_matches_pp")}})
    write_csv(out/"leagues_100plus.csv",per_league)
    print("CONSENSUS_FINAL_RESULTS",json.dumps({
        "n_total_matches":report["n_total_matches"],
        "votes_distribution":report["votes_distribution"],
        "cumulative_strategies":report["cumulative_strategies"],
        "holdout_restrict_by_previous_league_matches":report["holdout_restrict_by_previous_league_matches"],
        "holdout_walk_forward_vote_confidence":report["holdout_walk_forward_vote_confidence"]
    },ensure_ascii=False),flush=True)
    return report


def self_test():
    r=[]
    scores=["1:0","1:0","1:0","2:1","2:1","0:0"]
    for i in range(3):
        r.append({"date":f"2026-08-0{i+1}","id":str(i),"league":"Test League",
                  "home":"Home","away":"Away","actual":"1:0",
                  "consensus":"1:0","votes":3,"tied_for_first":False,
                  "won":1,"agreeing_models":list(SIX[:3]),"league_prior":i,
                  "all_predictions":dict(zip(SIX,scores)),
                  "individual_hit":{m:int(score=="1:0") for m,score in zip(SIX,scores)},
                  "individual_probability":{m:.1 for m in SIX},"number_distinct_scores":3})
    assert len(chosen(r,3))==3 and len(chosen(r,4))==0
    assert metrics(chosen(r,3),r)["hits"]==3
    assert len(bootstrap_day_cluster(chosen(r,3),draws=10)["hit_rate_pct"])==2
    assert rolling_reliability(r, start="2026-08-01")["3"]["n"]==3
    assert build_report(r,{},18,draws=10)["cumulative_strategies"]["holdout_aug_oct"]["thresholds"]["3"]["n"]==3
    print("CONSENSUS_SELF_TEST_OK",flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--predictions")
    p.add_argument("--output",default="research/results/consensus_2026")
    p.add_argument("--bootstrap",type=int,default=1300)
    p.add_argument("--self-test-only",action="store_true")
    args=p.parse_args()
    self_test()
    if not args.self_test_only:
        if not args.predictions:
            p.error("--predictions required outside self-test")
        run(args)


if __name__=="__main__":
    main()
