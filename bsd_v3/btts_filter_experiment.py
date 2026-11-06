"""Chronological BTTS YES quality-filter experiment.

A small fixed policy menu is selected on Jan-Jun 2026, must improve/hold on
Jul-Sep, then is evaluated on October without using October to select thresholds.
No historical odds or ROI are inferred.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from math import sqrt
from .engine import train_runtime,evaluate_fixture
from .legacy import (fixture_datetime,outcome_scores,estimate_goals,
                     score_matrix,markets_from_matrix)
from .policy import V3Policy
from bsd_v2_btts import fit_btts_model,btts_features
from bsd_v2_btts_team import team_scoring_probabilities

POLICIES={
    "base": lambda r: True,
    "two_sides_65": lambda r: r["min_side_score"]>=.65,
    "two_sides_68": lambda r: r["min_side_score"]>=.68,
    "two_sides_70": lambda r: r["min_side_score"]>=.70,
    "two_sides_72": lambda r: r["min_side_score"]>=.72,
    "two_sides_74": lambda r: r["min_side_score"]>=.74,
    "two_sides_76": lambda r: r["min_side_score"]>=.76,
    "two_sides_78": lambda r: r["min_side_score"]>=.78,
    "side68_spec55": lambda r: r["min_side_score"]>=.68 and r["specialist_p"]>=.55,
    "side70_spec55": lambda r: r["min_side_score"]>=.70 and r["specialist_p"]>=.55,
    "side68_blank35": lambda r: r["min_side_score"]>=.68 and r["max_blank"]<=.35,
    "side70_blank32": lambda r: r["min_side_score"]>=.70 and r["max_blank"]<=.32,
    "balanced_a": lambda r: (r["min_side_score"]>=.68 and r["specialist_p"]>=.55
                              and r["max_blank"]<=.35 and r["min_lambda"]>=.75),
    "balanced_b": lambda r: (r["min_side_score"]>=.70 and r["specialist_p"]>=.57
                              and r["max_blank"]<=.32 and r["min_lambda"]>=.80),
    "balanced_league": lambda r: (r["min_side_score"]>=.68 and r["specialist_p"]>=.55
                                   and r["max_blank"]<=.35 and r["league_btts"]>=.52),
    "agreement": lambda r: (r["min_side_score"]>=.68 and r["specialist_p"]>=.55
                             and r["model_gap"]<=.12),
    "side70_league55": lambda r: r["min_side_score"]>=.70 and r["league_btts"]>=.55,
    "side72_league55": lambda r: r["min_side_score"]>=.72 and r["league_btts"]>=.55,
    "side74_league55": lambda r: r["min_side_score"]>=.74 and r["league_btts"]>=.55,
    "side70_league58": lambda r: r["min_side_score"]>=.70 and r["league_btts"]>=.58,
    "side72_spec58": lambda r: r["min_side_score"]>=.72 and r["specialist_p"]>=.58,
    "side74_spec58": lambda r: r["min_side_score"]>=.74 and r["specialist_p"]>=.58,
    "side72_blank28": lambda r: r["min_side_score"]>=.72 and r["max_blank"]<=.28,
    "side74_blank28": lambda r: r["min_side_score"]>=.74 and r["max_blank"]<=.28,
    "side72_lambda90": lambda r: r["min_side_score"]>=.72 and r["min_lambda"]>=.90,
    "side74_lambda100": lambda r: r["min_side_score"]>=.74 and r["min_lambda"]>=1.00,
    "strict_recent_a": lambda r: (r["min_side_score"]>=.72 and r["league_btts"]>=.55
                                  and r["specialist_p"]>=.58 and r["max_blank"]<=.30),
    "strict_recent_b": lambda r: (r["min_side_score"]>=.74 and r["league_btts"]>=.55
                                  and r["specialist_p"]>=.58 and r["max_blank"]<=.28),
    "strict_recent_c": lambda r: (r["min_side_score"]>=.76 and r["league_btts"]>=.58
                                  and r["specialist_p"]>=.60 and r["max_blank"]<=.26),

}

def _stats(rows):
    n=len(rows)
    if not n:
        return {"n":0,"wins":0,"hit_rate":None,"wilson_low":None,"wilson_95":None}
    wins=sum(int(r["won"]) for r in rows)
    p=wins/n
    z=1.96
    q=z*z
    center=(p+q/(2*n))/(1+q/n)
    half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
    return {"n":n,"wins":wins,"hit_rate":round(p,5),
            "wilson_low":round(max(0,center-half),5),
            "wilson_95":[round(max(0,center-half),5),round(min(1,center+half),5)]}

def _extract(event,runtime,specialist):
    kickoff=fixture_datetime(event)
    historical=dict(event,status="notstarted",home_score=None,away_score=None)
    report=evaluate_fixture(historical,runtime,now=kickoff-timedelta(minutes=1),
                            policy=V3Policy())
    if report.get("status")!="analyzed":
        return None
    btts=next((r for r in report["candidates"] if r["key"]=="BTTS_YES"),None)
    if btts is None or not btts["decision"]["pro_vip_shadow"]:
        return None
    raw,_=estimate_goals(event,runtime["index"])
    if raw is None:
        return None
    baseline=markets_from_matrix(score_matrix(raw["home"],raw["away"],runtime["rho"]))
    p0=next(c.probability for c in baseline if c.key=="BTTS_YES")
    ps=specialist.predict(event,runtime["index"],p0)
    team=team_scoring_probabilities(event,runtime["index"],model=specialist.team_model)
    if team is None:
        return None
    zero=(specialist.zero_model.predict(event,runtime["index"],raw)
          if specialist.zero_model is not None else None)
    if zero is None:
        return None
    feat=btts_features(event,runtime["index"])
    if feat is None:
        return None
    score=outcome_scores(event)
    return {
        "event_id":str(event["id"]),"kickoff":kickoff.isoformat(),
        "won":bool(score[0]>0 and score[1]>0),
        "v3_p":float(btts["probability"]),
        "specialist_p":float(ps),
        "model_gap":abs(float(btts["probability"])-float(ps)),
        "home_score_p":float(team["home_scores"]),
        "away_score_p":float(team["away_scores"]),
        "min_side_score":min(float(team["home_scores"]),float(team["away_scores"])),
        "home_blank":float(zero["home_blank"]),
        "away_blank":float(zero["away_blank"]),
        "max_blank":max(float(zero["home_blank"]),float(zero["away_blank"])),
        "min_lambda":min(float(report["estimated_goals"]["home"]),
                         float(report["estimated_goals"]["away"])),
        "total_lambda":float(report["estimated_goals"]["home"])+float(report["estimated_goals"]["away"]),
        "league_btts":float(feat[9]+.5),
    }

def experiment(history):
    runtime=train_runtime(history,challenger=False)
    specialist,_diag=fit_btts_model(runtime["index"],rho=runtime["rho"])
    periods={"train":[],"validation":[],"test":[]}
    for _,event in runtime["index"].global_games:
        dt=fixture_datetime(event)
        if dt.year!=2026 or dt.month>10 or outcome_scores(event) is None:
            continue
        if dt.month<=6:key="train"
        elif dt.month<=9:key="validation"
        else:key="test"
        row=_extract(event,runtime,specialist)
        if row is not None:
            periods[key].append(row)
    tables={}
    for period,rows in periods.items():
        tables[period]={name:_stats([r for r in rows if rule(r)])
                        for name,rule in POLICIES.items()}
    train=tables["train"]
    validation=tables["validation"]
    # Rolling selection: recent Jul-Sep form selects the gate, while Jan-Jun
    # is only a safety veto. October is never consulted.
    candidates=[
        name for name,stat in validation.items()
        if name!="base" and stat["n"]>=40 and stat["hit_rate"] is not None
        and train[name]["n"]>=40 and train[name]["hit_rate"] is not None
        and train[name]["hit_rate"]>=train["base"]["hit_rate"]-.05
    ]
    if not candidates:
        chosen="base"
    else:
        chosen=max(candidates,key=lambda name:(validation[name]["wilson_low"],
                                               validation[name]["hit_rate"],
                                               validation[name]["n"]))
    accepted=(chosen!="base"
              and validation[chosen]["hit_rate"]>=validation["base"]["hit_rate"]+.02)
    active=chosen if accepted else "base"
    return {
        "format":"bsd-v3-btts-filter-experiment-v1",
        "stability_period":"2026-01 through 2026-06",
        "selection_period":"2026-07 through 2026-09",
        "test_period":"2026-10",
        "fixed_policies":list(POLICIES),
        "chosen_on_recent_selection":chosen,
        "accepted_on_validation":accepted,
        "active_policy":active,
        "tables":tables,
        "october_base":tables["test"]["base"],
        "october_filtered":tables["test"][active],
        "october_quality_delta":(
            round(tables["test"][active]["hit_rate"]-tables["test"]["base"]["hit_rate"],5)
            if tables["test"][active]["hit_rate"] is not None and
               tables["test"]["base"]["hit_rate"] is not None else None),
        "coverage_october_pct":(
            round(100*tables["test"][active]["n"]/tables["test"]["base"]["n"],2)
            if tables["test"]["base"]["n"] else None),
        "warning":"Retrospective filter research; October is not used to choose thresholds, "
                  "but 2026 behavior has influenced the wider project design."
    }
