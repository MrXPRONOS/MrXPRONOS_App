"""Chronological acceptance experiment for the direct BTTS NO classifier.

Model training: Jan-Aug 2024 only.
Threshold selection: Jan-Jun 2025.
Threshold validation: Jul-Dec 2025.
Final retrospective test: Jan-Oct 2026.
"""
from __future__ import annotations
from math import sqrt
from .engine import train_runtime
from .legacy import fixture_datetime,outcome_scores
from .btts_no_model import fit_btts_no_model

THRESHOLDS=(.55,.58,.60,.62,.65,.68,.70,.72,.75,.78,.80)
POLICIES={}
for threshold in THRESHOLDS:
    POLICIES[f"p{int(threshold*100)}"]=(lambda r,t=threshold:r["p"]>=t)
    POLICIES[f"p{int(threshold*100)}_league52"]=(lambda r,t=threshold:
        r["p"]>=t and r["league_btts"]<=.52)
    POLICIES[f"p{int(threshold*100)}_league50"]=(lambda r,t=threshold:
        r["p"]>=t and r["league_btts"]<=.50)

def _stats(rows):
    n=len(rows)
    if not n:
        return {"n":0,"wins":0,"hit_rate":None,"wilson_low":None,
                "wilson_95":None,"mean_probability":None,"brier":None}
    wins=sum(int(r["won"]) for r in rows)
    p=wins/n;z=1.96;q=z*z
    center=(p+q/(2*n))/(1+q/n)
    half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
    brier=sum((r["p"]-int(r["won"]))**2 for r in rows)/n
    return {"n":n,"wins":wins,"hit_rate":round(p,5),
            "wilson_low":round(max(0,center-half),5),
            "wilson_95":[round(max(0,center-half),5),round(min(1,center+half),5)],
            "mean_probability":round(sum(r["p"] for r in rows)/n,5),
            "brier":round(brier,6)}

def experiment(history):
    runtime=train_runtime(history,challenger=False)
    gate=runtime.get("btts_quality_gate")
    if gate is None or gate.team_model is None:
        raise RuntimeError("team scoring model missing")
    model=fit_btts_no_model(runtime["index"],runtime["rho"],gate.team_model,
                            goal_model=runtime.get("goal_strength"),
                            cal=runtime.get("calibration"))
    if model is None:
        raise RuntimeError("BTTS NO classifier failed to train")
    periods={"select":[],"validate":[],"test":[]}
    for _,event in runtime["index"].global_games:
        dt=fixture_datetime(event)
        score=outcome_scores(event)
        if score is None:continue
        if dt.year==2025:
            key="select" if dt.month<=6 else "validate"
        elif dt.year==2026 and dt.month<=10:
            key="test"
        else:
            continue
        pred=model.predict(event,runtime["index"],runtime["rho"],
                           runtime.get("goal_strength"),runtime.get("calibration"))
        if pred is None:continue
        periods[key].append({
            "p":float(pred["probability"]),
            "league_btts":float(pred["league_btts"]),
            "won":bool(score[0]==0 or score[1]==0),
        })
    tables={period:{name:_stats([r for r in rows if rule(r)])
                    for name,rule in POLICIES.items()}
            for period,rows in periods.items()}

    select=tables["select"];validate=tables["validate"]
    candidates=[]
    for name in POLICIES:
        s,v=select[name],validate[name]
        if s["n"]<100 or v["n"]<100:continue
        if s["hit_rate"] is None or v["hit_rate"] is None:continue
        if s["hit_rate"]<.70:continue
        candidates.append(name)
    chosen=(max(candidates,key=lambda n:(select[n]["wilson_low"],
                                        select[n]["hit_rate"],select[n]["n"]))
            if candidates else None)
    accepted=bool(chosen
                  and validate[chosen]["hit_rate"] is not None
                  and validate[chosen]["hit_rate"]>=.70
                  and validate[chosen]["hit_rate"]>=select[chosen]["hit_rate"]-.05)
    active=chosen if accepted else None
    return {
        "format":"bsd-v3-btts-no-direct-model-experiment-v1",
        "model":model.metadata(),
        "threshold_selection_period":"2025-01 through 2025-06",
        "threshold_validation_period":"2025-07 through 2025-12",
        "test_period":"2026-01 through 2026-10",
        "chosen_on_2025_h1":chosen,
        "accepted_on_2025_h2":accepted,
        "active_policy":active,
        "population":{k:len(v) for k,v in periods.items()},
        "tables":tables,
        "test_result":tables["test"].get(active) if active else None,
        "warning":"Retrospective model research. 2026 is not used to choose the model threshold; prospective confirmation remains required."
    }
