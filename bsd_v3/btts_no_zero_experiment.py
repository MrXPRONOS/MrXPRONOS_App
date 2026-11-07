"""BTTS NO experiment using direct scoreless-risk modelling.

Unlike the legacy last-H2H gate, this experiment estimates the actual event
needed by BTTS NO: P(home blank OR away blank). Models are trained on Jan-Aug
2024 only. Policies are selected on Jul-Sep 2026, with Jan-Jun as stability
veto and October held out.
"""
from __future__ import annotations
from math import sqrt
from .engine import train_runtime
from .legacy import (fixture_datetime,outcome_scores,estimate_goals,
                     score_matrix,markets_from_matrix)
from .policy import (V3Policy,classify_fixture,quality_tier,
                     uncertainty_adjustment)
from bsd_v2_btts import btts_features
from bsd_v2_btts_h2h import btts_h2h_decision
from bsd_v2_btts_zero import fit_zero_goal_model
from bsd_v2_btts_team import team_scoring_probabilities

POLICIES={
    "v3_60": lambda r: r["v3_no"]>=.60 and r["pc"]>=.58,
    "zero60": lambda r: r["zero_no"]>=.60,
    "zero65": lambda r: r["zero_no"]>=.65,
    "zero70": lambda r: r["zero_no"]>=.70,
    "dual58": lambda r: r["v3_no"]>=.58 and r["zero_no"]>=.58,
    "dual60": lambda r: r["v3_no"]>=.60 and r["zero_no"]>=.60,
    "dual62": lambda r: r["v3_no"]>=.62 and r["zero_no"]>=.62,
    "dual65": lambda r: r["v3_no"]>=.65 and r["zero_no"]>=.65,
    "zero60_blank35": lambda r: r["zero_no"]>=.60 and r["max_blank"]>=.35,
    "zero65_blank35": lambda r: r["zero_no"]>=.65 and r["max_blank"]>=.35,
    "zero60_league50": lambda r: r["zero_no"]>=.60 and r["league_btts"]<=.50,
    "zero65_league50": lambda r: r["zero_no"]>=.65 and r["league_btts"]<=.50,
    "dual60_league50": lambda r: (r["v3_no"]>=.60 and r["zero_no"]>=.60
        and r["league_btts"]<=.50),
    "dual62_league50": lambda r: (r["v3_no"]>=.62 and r["zero_no"]>=.62
        and r["league_btts"]<=.50),
    "agreement60": lambda r: (min(r["v3_no"],r["zero_no"])>=.60
        and r["model_gap"]<=.10),
    "agreement62": lambda r: (min(r["v3_no"],r["zero_no"])>=.62
        and r["model_gap"]<=.08),
    "zero60_h2h": lambda r: r["zero_no"]>=.60 and r["h2h_no"],
    "dual60_h2h": lambda r: r["v3_no"]>=.60 and r["zero_no"]>=.60 and r["h2h_no"],
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

def experiment(history):
    runtime=train_runtime(history,challenger=False)
    index=runtime["index"]
    training=[]
    for _,event in index.global_games:
        dt=fixture_datetime(event)
        if dt.year==2024 and dt.month<=8 and outcome_scores(event) is not None:
            training.append(event)
    zero_model=fit_zero_goal_model(index,training)
    if zero_model is None:
        raise RuntimeError("BTTS NO zero-goal model failed to train")
    periods={"train":[],"validation":[],"test":[]}
    cal=runtime.get("calibration")
    samples=cal.trained if cal and cal.active else 0
    goal_model=runtime.get("goal_strength")
    gate=runtime.get("btts_quality_gate")

    for _,event in index.global_games:
        dt=fixture_datetime(event)
        if dt.year!=2026 or dt.month>10 or outcome_scores(event) is None:
            continue
        expected,reason=estimate_goals(event,index)
        if expected is None:continue
        quality=classify_fixture(expected,V3Policy())
        if quality.get("level")=="rejected" or quality_tier({},quality)=="simple":
            continue
        if goal_model is not None and goal_model.alpha:
            expected=goal_model.apply(event,index,expected)
        matrix=score_matrix(expected["home"],expected["away"],runtime["rho"])
        if cal is not None:
            matrix=cal.apply(matrix)
        p_no=next(c.probability for c in markets_from_matrix(matrix)
                  if c.key=="BTTS_NO")
        haircut=uncertainty_adjustment(expected,quality,calibration_samples=samples)
        pc=max(.00001,p_no-haircut)
        zero=zero_model.predict(event,index,expected)
        side=team_scoring_probabilities(event,index,model=gate.team_model if gate else None)
        feat=btts_features(event,index)
        if zero is None or side is None or feat is None:continue
        ph=float(zero["home_blank"]);pa=float(zero["away_blank"])
        zero_no=ph+pa-ph*pa
        league=float(feat[9]+.5)
        h2h_ok,_,_=btts_h2h_decision(event,index,"BTTS_NO")
        h,a=outcome_scores(event)
        item={
            "v3_no":float(p_no),"pc":float(pc),
            "zero_no":float(zero_no),
            "home_blank":ph,"away_blank":pa,"max_blank":max(ph,pa),
            "team_model_no":1-float(side["home_scores"])*float(side["away_scores"]),
            "league_btts":league,"model_gap":abs(float(p_no)-zero_no),
            "h2h_no":bool(h2h_ok),"won":bool(h==0 or a==0),
        }
        key="train" if dt.month<=6 else ("validation" if dt.month<=9 else "test")
        periods[key].append(item)

    tables={period:{name:_stats([r for r in rows if rule(r)])
                    for name,rule in POLICIES.items()}
            for period,rows in periods.items()}
    train=tables["train"];validation=tables["validation"]
    candidates=[]
    for name in POLICIES:
        tr,va=train[name],validation[name]
        if tr["n"]<100 or va["n"]<50:continue
        if tr["hit_rate"] is None or va["hit_rate"] is None:continue
        if tr["hit_rate"]<.68:continue
        candidates.append(name)
    chosen=(max(candidates,key=lambda n:(validation[n]["wilson_low"],
                                        validation[n]["hit_rate"],
                                        validation[n]["n"]))
            if candidates else None)
    accepted=bool(chosen and validation[chosen]["hit_rate"]>=.72)
    return {
        "format":"bsd-v3-btts-no-zero-goal-experiment-v1",
        "zero_model":zero_model.to_dict(),
        "stability_period":"2026-01 through 2026-06",
        "selection_period":"2026-07 through 2026-09",
        "test_period":"2026-10",
        "chosen_on_recent_selection":chosen,
        "accepted":accepted,
        "active_policy":chosen if accepted else None,
        "tables":tables,
        "october_filtered":tables["test"].get(chosen) if chosen else None,
        "population":{"train":len(periods["train"]),
                      "validation":len(periods["validation"]),
                      "test":len(periods["test"])},
        "warning":"Retrospective research. October is held out from threshold selection; prospective confirmation remains required."
    }
