"""Chronological Over 2.5 quality-gate experiment for BSD V3.

Fixed candidate policies are selected without using October 2026:
- Jan-Jun 2026: stability veto
- Jul-Sep 2026: policy selection
- Oct 2026: held-out diagnostic

No historical bookmaker odds are fabricated.
"""
from __future__ import annotations
from datetime import timedelta
from math import sqrt
from .engine import train_runtime,evaluate_fixture
from .legacy import fixture_datetime,outcome_scores
from .policy import V3Policy
from bsd_v2_over_under import features as total_features,fit_total_model
from bsd_v2_btts_team import team_scoring_probabilities

def _stats(rows):
    n=len(rows)
    if not n:
        return {"n":0,"wins":0,"hit_rate":None,"wilson_low":None,"wilson_95":None}
    wins=sum(int(r["won"]) for r in rows)
    p=wins/n;z=1.96;q=z*z
    center=(p+q/(2*n))/(1+q/n)
    half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
    return {"n":n,"wins":wins,"hit_rate":round(p,5),
            "wilson_low":round(max(0,center-half),5),
            "wilson_95":[round(max(0,center-half),5),round(min(1,center+half),5)]}

POLICIES={
    "base70": lambda r: r["p"]>=.70 and r["pc"]>=.68,
    "p72": lambda r: r["p"]>=.72 and r["pc"]>=.70,
    "p74": lambda r: r["p"]>=.74 and r["pc"]>=.72,
    "p70_total28": lambda r: r["p"]>=.70 and r["pc"]>=.68 and r["expected_total"]>=2.8,
    "p70_total30": lambda r: r["p"]>=.70 and r["pc"]>=.68 and r["expected_total"]>=3.0,
    "p72_total30": lambda r: r["p"]>=.72 and r["pc"]>=.70 and r["expected_total"]>=3.0,
    "p70_league55": lambda r: r["p"]>=.70 and r["pc"]>=.68 and r["league_over"]>=.55,
    "p70_league58": lambda r: r["p"]>=.70 and r["pc"]>=.68 and r["league_over"]>=.58,
    "p72_league58": lambda r: r["p"]>=.72 and r["pc"]>=.70 and r["league_over"]>=.58,
    "p74_league58": lambda r: r["p"]>=.74 and r["pc"]>=.72 and r["league_over"]>=.58,
    "p76_league58": lambda r: r["p"]>=.76 and r["pc"]>=.74 and r["league_over"]>=.58,
    "p78_league58": lambda r: r["p"]>=.78 and r["pc"]>=.76 and r["league_over"]>=.58,
    "p74_league60": lambda r: r["p"]>=.74 and r["pc"]>=.72 and r["league_over"]>=.60,
    "p76_league60": lambda r: r["p"]>=.76 and r["pc"]>=.74 and r["league_over"]>=.60,
    "p78_league60": lambda r: r["p"]>=.78 and r["pc"]>=.76 and r["league_over"]>=.60,
    "p70_emp60": lambda r: r["p"]>=.70 and r["pc"]>=.68 and r["empirical_over"]>=.60,
    "p72_emp62": lambda r: r["p"]>=.72 and r["pc"]>=.70 and r["empirical_over"]>=.62,
    "p70_total28_league55": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["expected_total"]>=2.8 and r["league_over"]>=.55),
    "p72_total30_league55": lambda r: (r["p"]>=.72 and r["pc"]>=.70
        and r["expected_total"]>=3.0 and r["league_over"]>=.55),
    "p70_emp60_league55": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["empirical_over"]>=.60 and r["league_over"]>=.55),
    "p72_emp62_league55": lambda r: (r["p"]>=.72 and r["pc"]>=.70
        and r["empirical_over"]>=.62 and r["league_over"]>=.55),
    "p70_specialist70_gap08": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["specialist_p"]>=.70 and r["model_gap"]<=.08),
    "p72_specialist72_gap08": lambda r: (r["p"]>=.72 and r["pc"]>=.70
        and r["specialist_p"]>=.72 and r["model_gap"]<=.08),
    "p70_league58_side60": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["league_over"]>=.58 and r["min_side_score"]>=.60),
    "p70_league58_side65": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["league_over"]>=.58 and r["min_side_score"]>=.65),
    "p70_league58_side68": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["league_over"]>=.58 and r["min_side_score"]>=.68),
    "p70_league58_side70": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["league_over"]>=.58 and r["min_side_score"]>=.70),
    "p72_league58_side65": lambda r: (r["p"]>=.72 and r["pc"]>=.70
        and r["league_over"]>=.58 and r["min_side_score"]>=.65),
    "p70_league58_side65_emp60": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["league_over"]>=.58 and r["min_side_score"]>=.65
        and r["empirical_over"]>=.60),
    "p70_league58_btts60": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["league_over"]>=.58 and r["btts_p"]>=.60),
    "p70_league58_btts65": lambda r: (r["p"]>=.70 and r["pc"]>=.68
        and r["league_over"]>=.58 and r["btts_p"]>=.65),
}

def experiment(history):
    runtime=train_runtime(history,challenger=False)
    total_model,total_fit=fit_total_model(runtime["index"],runtime["rho"])
    periods={"train":[],"validation":[],"test":[]}
    for _,event in runtime["index"].global_games:
        dt=fixture_datetime(event)
        if dt.year!=2026 or dt.month>10 or outcome_scores(event) is None:
            continue
        historical=dict(event,status="notstarted",home_score=None,away_score=None)
        report=evaluate_fixture(historical,runtime,now=dt-timedelta(minutes=1),policy=V3Policy())
        if report.get("status")!="analyzed":
            continue
        row=next((x for x in report["candidates"] if x["key"]=="OVER_25"),None)
        if row is None or row["decision"]["quality_tier"]=="simple":
            continue
        if row.get("market_probability_lift",0)<=0:
            continue
        feat=total_features(event,runtime["index"])
        if feat is None:
            continue
        spec=total_model.predict_over(event,runtime["index"])
        if not spec or 2.5 not in spec:
            continue
        specialist=float(spec[2.5])
        gate=runtime.get("btts_quality_gate")
        side=(team_scoring_probabilities(event,runtime["index"],model=gate.team_model)
              if gate is not None and gate.team_model is not None else None)
        if side is None:
            continue
        btts_row=next((x for x in report["candidates"] if x["key"]=="BTTS_YES"),None)
        if btts_row is None:
            continue
        h,a=outcome_scores(event)
        item={
            "p":float(row["probability"]),
            "pc":float(row["conservative_probability"]),
            "expected_total":float(report["estimated_goals"]["home"])+float(report["estimated_goals"]["away"]),
            "league_over":float(feat["league_over_rates"][2.5]),
            "empirical_over":float(feat["empirical_over"][2.5]),
            "specialist_p":specialist,
            "model_gap":abs(float(row["probability"])-specialist),
            "home_score_p":float(side["home_scores"]),
            "away_score_p":float(side["away_scores"]),
            "min_side_score":min(float(side["home_scores"]),float(side["away_scores"])),
            "btts_p":float(btts_row["probability"]),
            "won":bool(h+a>2.5),
        }
        key="train" if dt.month<=6 else ("validation" if dt.month<=9 else "test")
        periods[key].append(item)

    tables={period:{name:_stats([r for r in rows if rule(r)])
                    for name,rule in POLICIES.items()}
            for period,rows in periods.items()}
    train=tables["train"];validation=tables["validation"]
    base_train=train["base70"];base_validation=validation["base70"]
    candidates=[]
    for name in POLICIES:
        if name=="base70":continue
        tr,va=train[name],validation[name]
        if tr["n"]<60 or va["n"]<40:continue
        if tr["hit_rate"] is None or va["hit_rate"] is None:continue
        # Safety: earlier period must not collapse relative to the simple base.
        if tr["hit_rate"] < max(.68,base_train["hit_rate"]-.03):continue
        candidates.append(name)
    chosen=(max(candidates,key=lambda name:(validation[name]["wilson_low"],
                                            validation[name]["hit_rate"],
                                            validation[name]["n"]))
            if candidates else "base70")
    accepted=(chosen!="base70" and validation[chosen]["hit_rate"]>=.75
              and validation[chosen]["hit_rate"]>=base_validation["hit_rate"]+.03)
    active=chosen if accepted else "base70"
    return {
        "format":"bsd-v3-over25-quality-experiment-v2",
        "stability_period":"2026-01 through 2026-06",
        "selection_period":"2026-07 through 2026-09",
        "test_period":"2026-10",
        "total_model_fit":total_fit,
        "chosen_on_recent_selection":chosen,
        "accepted":accepted,
        "active_policy":active,
        "tables":tables,
        "october_base":tables["test"]["base70"],
        "october_filtered":tables["test"][active],
        "warning":"Retrospective quality-gate research. October is not used to select the policy; prospective confirmation is still required."
    }
