#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline SIX-model consensus predictor for forthcoming football fixtures.

Inputs: JSON fixture list + historic games cache; outputs 6 individual top scores
plus abstain/accept consensus at configurable min 3,4,5,6 votes.
No standings/score data for current fixture, no odds or xG fabrication.
Only matches dated strictly BEFORE the fixture's UTC date train the models.

Research command; does not publish to site or Telegram automatically.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from itertools import groupby
from pathlib import Path

import numpy as np

from exact_scores_2026 import (
    FormState, load_matches, utc_day, poisson_grid, dixon_coles,
    bivariate_grid, league_shared_covariance, bayesian_grid, monte_carlo_grid,
    estimate_dc_rho, estimate_shared, train_ml, SEED
)

SIX = ("poisson", "dixon_coles", "bivariate_poisson",
       "bayesian_gamma", "machine_learning", "monte_carlo")


def consensus(votes, minimum=5):
    """Equal vote from each of six independent forecast procedures.
    4/6 is four votes, not 66.7% probability of the football score.
    """
    if not isinstance(votes, dict) or set(votes) != set(SIX):
        raise ValueError("Exactly six model votes are required")
    if minimum not in (3, 4, 5, 6):
        raise ValueError("Minimum agreement must be 3/4/5/6")
    freq = Counter(votes.values())
    high = max(freq.values())
    top_scores = sorted(s for s,n in freq.items() if n == high)
    tie = len(top_scores)>1
    selected = not tie and high >= minimum
    agreed = top_scores[0] if not tie else None
    return {
        "score": agreed if selected else None,
        "status": "SELECTED" if selected else "ABSTAIN",
        "top_score_without_threshold": agreed,
        "highest_vote_count": high,
        "total_models": len(SIX),
        "minimum_required": minimum,
        "tied_first": tie,
        "agreeing_models": [m for m in SIX if selected and votes[m]==agreed],
        "score_vote_counts": dict(sorted(freq.items())),
        "agreement_not_probability": "Model vote fraction is NOT an exact-score probability",
    }


def normalized_fixtures(path):
    raw=json.loads(Path(path).read_text(encoding="utf8"))
    rows=raw if isinstance(raw,list) else raw.get("fixtures",[])
    if not isinstance(rows,list) or not rows:
        raise ValueError("Expected a nonempty fixtures array")
    out=[]
    seen=set()
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("Fixture must be an object")
        d=utc_day(row.get("start_time") or row.get("event_date") or row.get("date"))
        league=str(row.get("league") or row.get("competition") or "").strip()
        home=str(row.get("home_team") or "").strip()
        away=str(row.get("away_team") or "").strip()
        if d is None or not league or not home or not away or home==away:
            raise ValueError(f"Invalid fixture, require date, league, home_team, away_team: {row}")
        key=str(row.get("id") or f"{d}:{league}:{home}:{away}")
        if (d,key) in seen:
            raise ValueError(f"Duplicate fixture: {key}")
        seen.add((d,key))
        out.append({"date":d,"id":key,"league":league,"home_team":home,"away_team":away})
    return sorted(out,key=lambda x:(x["date"],x["id"]))


def score_grid_top(grid):
    i,j=np.unravel_index(grid.argmax(),grid.shape)
    return f"{i}:{j}"


def predict(fixtures, history, minimum):
    states=FormState()
    training=[]
    obs=[]
    league_residuals=defaultdict(list)
    model=None
    fitted_at=None
    dc_rho=-.04
    common_fraction=0.0
    history=sorted(history,key=lambda r:(r.day,r.key))
    days=groupby(fixtures,lambda x:x["date"])
    idx=0
    result=[]
    for target_day,fixtures_on_day in days:
        while idx<len(history) and history[idx].day < target_day:
            # Only prior calendar days; extract the prior day's fixture features
            # BEFORE any scores from that prior date are added to state.
            old_day=history[idx].day
            group=[]
            while idx<len(history) and history[idx].day==old_day:
                group.append(history[idx])
                idx+=1
            features=[states.features(game) for game in group]
            for match,f in zip(group,features):
                obs.append((f["h"],f["a"],match.hg,match.ag))
                league_residuals[match.league].append((match.hg-f["h"],match.ag-f["a"]))
                training.append((f["vector"],match.hg,match.ag))
                states.add(match)
        month=(target_day.year,target_day.month)
        if month != fitted_at:
            if len(training)>=350:
                model=train_ml(training)
                dc_rho=estimate_dc_rho(obs[-9000:])
                common_fraction=estimate_shared(obs)
            fitted_at=month
        for fxt in fixtures_on_day:
            # Feature builder accepts fixture-like object; actual scores are never read.
            from types import SimpleNamespace
            obj=SimpleNamespace(day=target_day,league=fxt["league"],
                                home=fxt["home_team"],away=fxt["away_team"])
            f=states.features(obj)
            score_seed=(SEED+sum(ord(ch) for ch in fxt["id"])*8191)%(2**32)
            grids={
                "poisson":poisson_grid(f["h"],f["a"]),
                "dixon_coles":dixon_coles(f["h"],f["a"],dc_rho),
                "bivariate_poisson":bivariate_grid(
                    f["h"],f["a"],league_shared_covariance(
                        league_residuals[fxt["league"]],
                        common_fraction*min(f["h"],f["a"]))),
                "bayesian_gamma":bayesian_grid(f,score_seed),
                "monte_carlo":monte_carlo_grid(f["h"],f["a"],score_seed+1)
            }
            if model is None:
                # No silent 5-model replacement: equal votes require all six.
                result.append({
                    "id":fxt["id"],"date":str(target_day),
                    "home_team":fxt["home_team"],"away_team":fxt["away_team"],
                    "league":fxt["league"],"status":"ABSTAIN",
                    "reason":"insufficient_previous_games_for_six_model_ML",
                    "previous_completed_match_count":len(training)
                })
                continue
            lam_h=float(np.clip(model[0].predict(f["vector"][None,:])[0],.12,5))
            lam_a=float(np.clip(model[1].predict(f["vector"][None,:])[0],.12,5))
            grids["machine_learning"]=poisson_grid(lam_h,lam_a)
            picks={m:score_grid_top(grids[m]) for m in SIX}
            decision=consensus(picks,minimum)
            result.append({
                "id":fxt["id"],"date":str(target_day),
                "home_team":fxt["home_team"],"away_team":fxt["away_team"],
                "league":fxt["league"],
                "previous_completed_match_count":len(training),
                "models":picks,
                "decision":decision,
                "status":decision["status"],
                "exact_score":decision["score"],
            })
    return result


def self_test():
    picks={m:"1:0" for m in SIX}
    assert consensus(picks,6)["score"]=="1:0"
    picks=dict(zip(SIX,["1:0","1:0","1:0","2:0","2:0","2:0"]))
    assert consensus(picks,3)["status"]=="ABSTAIN"
    picks=dict(zip(SIX,["1:0","1:0","1:0","1:0","2:0","2:0"]))
    assert consensus(picks,4)["score"]=="1:0"
    assert consensus(picks,5)["score"] is None
    try:
        consensus({SIX[0]:"1:0"},3)
    except ValueError:
        pass
    else:
        raise AssertionError("Must reject partial voting")
    print("SIX_MODEL_PREDICTOR_SELF_TEST_OK",flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--fixtures")
    parser.add_argument("--history",default="cache/all_matches.json")
    parser.add_argument("--output",default="research/results/upcoming_consensus.json")
    parser.add_argument("--minimum-votes",type=int,choices=(3,4,5,6),default=5)
    parser.add_argument("--self-test-only",action="store_true")
    args=parser.parse_args()
    self_test()
    if args.self_test_only:
        return
    if not args.fixtures:
        parser.error("--fixtures required")
    fixtures=normalized_fixtures(args.fixtures)
    history=load_matches(args.history,max(x["date"] for x in fixtures))
    rows=predict(fixtures,history,args.minimum_votes)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps({
        "rules":{"models":list(SIX),"minimum_votes":args.minimum_votes,
                 "history_policy":"previous UTC calendar days only",
                 "predictions_are_not_guarantees":True},
        "fixtures":rows
    },ensure_ascii=False,indent=2),encoding="utf8")
    print("FUTURE_CONSENSUS_SUMMARY",json.dumps({
        "fixtures":len(rows),"selected":sum(r["status"]=="SELECTED" for r in rows),
        "abstained":sum(r["status"]=="ABSTAIN" for r in rows),
        "output":str(dest)
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
