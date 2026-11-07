"""Ultra-selective BTTS NO rule research.

The target is precision, not volume. Rules use only pre-match estimated goals,
league BTTS rate, V3 BTTS NO probability and optional last-H2H confirmation.
Thresholds are chosen on 2025 H1, validated on 2025 H2, then tested on 2026.
"""
from __future__ import annotations
from math import sqrt
from .engine import train_runtime
from .legacy import (fixture_datetime,outcome_scores,estimate_goals,
                     score_matrix,markets_from_matrix)
from .policy import V3Policy,classify_fixture,quality_tier
from bsd_v2_btts import btts_features
from bsd_v2_btts_h2h import btts_h2h_decision

POLICIES={
    "lambda50": lambda r:r["min_lambda"]<=.50,
    "lambda45": lambda r:r["min_lambda"]<=.45,
    "lambda40": lambda r:r["min_lambda"]<=.40,
    "lambda35": lambda r:r["min_lambda"]<=.35,
    "lambda30": lambda r:r["min_lambda"]<=.30,
    "lambda50_league52": lambda r:r["min_lambda"]<=.50 and r["league_btts"]<=.52,
    "lambda50_league50": lambda r:r["min_lambda"]<=.50 and r["league_btts"]<=.50,
    "lambda45_league52": lambda r:r["min_lambda"]<=.45 and r["league_btts"]<=.52,
    "lambda45_league50": lambda r:r["min_lambda"]<=.45 and r["league_btts"]<=.50,
    "lambda40_league52": lambda r:r["min_lambda"]<=.40 and r["league_btts"]<=.52,
    "lambda40_league50": lambda r:r["min_lambda"]<=.40 and r["league_btts"]<=.50,
    "p55_lambda55": lambda r:r["p_no"]>=.55 and r["min_lambda"]<=.55,
    "p55_lambda50": lambda r:r["p_no"]>=.55 and r["min_lambda"]<=.50,
    "p58_lambda50": lambda r:r["p_no"]>=.58 and r["min_lambda"]<=.50,
    "p60_lambda50": lambda r:r["p_no"]>=.60 and r["min_lambda"]<=.50,
    "p55_lambda45": lambda r:r["p_no"]>=.55 and r["min_lambda"]<=.45,
    "p58_lambda45": lambda r:r["p_no"]>=.58 and r["min_lambda"]<=.45,
    "p60_lambda45": lambda r:r["p_no"]>=.60 and r["min_lambda"]<=.45,
    "lambda50_h2h": lambda r:r["min_lambda"]<=.50 and r["h2h_no"],
    "lambda45_h2h": lambda r:r["min_lambda"]<=.45 and r["h2h_no"],
    "lambda40_h2h": lambda r:r["min_lambda"]<=.40 and r["h2h_no"],
    "lambda50_league50_h2h": lambda r:(r["min_lambda"]<=.50 and r["league_btts"]<=.50 and r["h2h_no"]),
    "lambda45_league50_h2h": lambda r:(r["min_lambda"]<=.45 and r["league_btts"]<=.50 and r["h2h_no"]),
}

def _stats(rows):
    n=len(rows)
    if not n:return {"n":0,"wins":0,"hit_rate":None,"wilson_low":None,"wilson_95":None}
    wins=sum(int(r["won"]) for r in rows)
    p=wins/n;z=1.96;q=z*z
    center=(p+q/(2*n))/(1+q/n)
    half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
    return {"n":n,"wins":wins,"hit_rate":round(p,5),
            "wilson_low":round(max(0,center-half),5),
            "wilson_95":[round(max(0,center-half),5),round(min(1,center+half),5)]}

def evaluate_window(history,start_date,end_date):
    from datetime import datetime,timezone
    runtime=train_runtime(history,challenger=False)
    start=datetime.fromisoformat(start_date+"T00:00:00+00:00")
    end=datetime.fromisoformat(end_date+"T23:59:59+00:00")
    rows=[]
    for _,event in runtime["index"].global_games:
        dt=fixture_datetime(event)
        if not start<=dt<=end:continue
        score=outcome_scores(event)
        if score is None:continue
        expected,reason=estimate_goals(event,runtime["index"])
        if expected is None:continue
        quality=classify_fixture(expected,V3Policy())
        if quality_tier({},quality)=="simple":continue
        goal_model=runtime.get("goal_strength")
        if goal_model is not None and goal_model.alpha:
            expected=goal_model.apply(event,runtime["index"],expected)
        matrix=score_matrix(expected["home"],expected["away"],runtime["rho"])
        cal=runtime.get("calibration")
        if cal is not None:matrix=cal.apply(matrix)
        p_no=next(c.probability for c in markets_from_matrix(matrix) if c.key=="BTTS_NO")
        feat=btts_features(event,runtime["index"])
        if feat is None:continue
        h2h_ok,_,_=btts_h2h_decision(event,runtime["index"],"BTTS_NO")
        rows.append({
            "p_no":float(p_no),
            "min_lambda":min(float(expected["home"]),float(expected["away"])),
            "total_lambda":float(expected["home"])+float(expected["away"]),
            "league_btts":float(feat[9]+.5),
            "h2h_no":bool(h2h_ok),
            "won":bool(score[0]==0 or score[1]==0),
        })
    return {"start":start_date,"end":end_date,"population":len(rows),
            "tables":{name:_stats([r for r in rows if rule(r)])
                      for name,rule in POLICIES.items()}}

def aggregate(select,validate,test_parts):
    candidates=[]
    for name in POLICIES:
        s,v=select["tables"][name],validate["tables"][name]
        if s["n"]<30 or v["n"]<30:continue
        if s["hit_rate"] is None or v["hit_rate"] is None:continue
        if s["hit_rate"]<.72:continue
        candidates.append(name)
    chosen=(max(candidates,key=lambda n:(validate["tables"][n]["wilson_low"],
                                        validate["tables"][n]["hit_rate"],
                                        validate["tables"][n]["n"]))
            if candidates else None)
    accepted=bool(chosen and validate["tables"][chosen]["hit_rate"]>=.72
                  and validate["tables"][chosen]["hit_rate"]>=select["tables"][chosen]["hit_rate"]-.07)
    def merge(parts,name):
        if not name:return None
        n=sum(p["tables"][name]["n"] for p in parts)
        wins=sum(p["tables"][name]["wins"] for p in parts)
        if not n:return {"n":0,"wins":0,"hit_rate":None}
        p=wins/n;z=1.96;q=z*z
        center=(p+q/(2*n))/(1+q/n)
        half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
        return {"n":n,"wins":wins,"hit_rate":round(p,5),
                "wilson_low":round(max(0,center-half),5),
                "wilson_95":[round(max(0,center-half),5),round(min(1,center+half),5)]}
    return {
        "format":"bsd-v3-btts-no-ultra-selective-v1",
        "chosen_on_2025_h1":chosen,
        "accepted_on_2025_h2":accepted,
        "active_policy":chosen if accepted else None,
        "selection":select["tables"].get(chosen) if chosen else None,
        "validation":validate["tables"].get(chosen) if chosen else None,
        "test_2026":merge(test_parts,chosen) if accepted else None,
        "population":{"select":select["population"],"validate":validate["population"],
                      "test":sum(p["population"] for p in test_parts)},
        "warning":"2026 is held out from policy selection. Precision is prioritized over BTTS NO volume."
    }
