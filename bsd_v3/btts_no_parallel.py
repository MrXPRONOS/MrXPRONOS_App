"""Parallel evaluation helpers for BTTS NO direct model."""
from __future__ import annotations
from datetime import datetime,timezone
from .engine import train_runtime
from .legacy import fixture_datetime,outcome_scores
from .btts_no_model import fit_btts_no_model
from .btts_no_model_experiment import POLICIES,_stats

UTC=timezone.utc

def evaluate_window(history,start_date,end_date):
    runtime=train_runtime(history,challenger=False)
    gate=runtime.get("btts_quality_gate")
    if gate is None or gate.team_model is None:
        raise RuntimeError("team scoring model missing")
    model=fit_btts_no_model(runtime["index"],runtime["rho"],gate.team_model,
                            goal_model=runtime.get("goal_strength"),
                            cal=runtime.get("calibration"))
    if model is None:
        raise RuntimeError("BTTS NO classifier failed to train")
    start=datetime.fromisoformat(start_date+"T00:00:00+00:00")
    end=datetime.fromisoformat(end_date+"T23:59:59+00:00")
    rows=[]
    for _,event in runtime["index"].global_games:
        dt=fixture_datetime(event)
        if not (start<=dt<=end):
            continue
        score=outcome_scores(event)
        if score is None:
            continue
        pred=model.predict(event,runtime["index"],runtime["rho"],
                           runtime.get("goal_strength"),runtime.get("calibration"))
        if pred is None:
            continue
        rows.append({
            "p":float(pred["probability"]),
            "league_btts":float(pred["league_btts"]),
            "won":bool(score[0]==0 or score[1]==0),
        })
    return {
        "start":start_date,"end":end_date,
        "population":len(rows),
        "model":model.metadata(),
        "tables":{name:_stats([r for r in rows if rule(r)])
                  for name,rule in POLICIES.items()}
    }

def aggregate_windows(select,validate,test_parts):
    candidates=[]
    for name in POLICIES:
        s,v=select["tables"][name],validate["tables"][name]
        if s["n"]<100 or v["n"]<100:continue
        if s["hit_rate"] is None or v["hit_rate"] is None:continue
        if s["hit_rate"]<.70:continue
        candidates.append(name)
    chosen=(max(candidates,key=lambda n:(select["tables"][n]["wilson_low"],
                                        select["tables"][n]["hit_rate"],
                                        select["tables"][n]["n"]))
            if candidates else None)
    accepted=bool(chosen
                  and validate["tables"][chosen]["hit_rate"] is not None
                  and validate["tables"][chosen]["hit_rate"]>=.70
                  and validate["tables"][chosen]["hit_rate"]>=
                      select["tables"][chosen]["hit_rate"]-.05)

    def merge_stats(parts,name):
        n=sum(p["tables"][name]["n"] for p in parts)
        wins=sum(p["tables"][name]["wins"] for p in parts)
        # Recompute a minimal aggregate. Mean probability/Brier are omitted here
        # because acceptance is based on hit rate and Wilson lower bound.
        if not n:return {"n":0,"wins":0,"hit_rate":None,"wilson_low":None}
        from math import sqrt
        p=wins/n;z=1.96;q=z*z
        center=(p+q/(2*n))/(1+q/n)
        half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
        return {"n":n,"wins":wins,"hit_rate":round(p,5),
                "wilson_low":round(max(0,center-half),5),
                "wilson_95":[round(max(0,center-half),5),round(min(1,center+half),5)]}
    test=merge_stats(test_parts,chosen) if chosen else None
    return {
        "format":"bsd-v3-btts-no-direct-model-parallel-v1",
        "chosen_on_2025_h1":chosen,
        "accepted_on_2025_h2":accepted,
        "active_policy":chosen if accepted else None,
        "selection":select["tables"].get(chosen) if chosen else None,
        "validation":validate["tables"].get(chosen) if chosen else None,
        "test_2026":test if accepted else None,
        "population":{
            "select":select["population"],
            "validate":validate["population"],
            "test":sum(p["population"] for p in test_parts),
        },
        "model":select["model"],
        "warning":"2026 is not used to choose the threshold. Prospective confirmation remains required."
    }
