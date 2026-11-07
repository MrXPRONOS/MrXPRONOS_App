"""Chronological BTTS NO quality-policy experiment for BSD V3.

Selection:
- Jan-Jun 2026 is a stability veto.
- Jul-Sep 2026 selects among a fixed policy menu.
- Oct 2026 is a held-out diagnostic.
Existing strict last-H2H BTTS NO eligibility remains mandatory.
"""
from __future__ import annotations
from datetime import timedelta
from math import sqrt
from .engine import train_runtime,evaluate_fixture
from .legacy import fixture_datetime,outcome_scores
from .policy import V3Policy
from bsd_v2_btts import btts_features
from bsd_v2_btts_team import team_scoring_probabilities

POLICIES={
    "base65": lambda r: r["p"]>=.65 and r["pc"]>=.63,
    "p68": lambda r: r["p"]>=.68 and r["pc"]>=.66,
    "p70": lambda r: r["p"]>=.70 and r["pc"]>=.68,
    "p72": lambda r: r["p"]>=.72 and r["pc"]>=.70,
    "p65_blank35": lambda r: r["p"]>=.65 and r["pc"]>=.63 and r["max_blank"]>=.35,
    "p65_blank40": lambda r: r["p"]>=.65 and r["pc"]>=.63 and r["max_blank"]>=.40,
    "p68_blank35": lambda r: r["p"]>=.68 and r["pc"]>=.66 and r["max_blank"]>=.35,
    "p68_blank40": lambda r: r["p"]>=.68 and r["pc"]>=.66 and r["max_blank"]>=.40,
    "p70_blank40": lambda r: r["p"]>=.70 and r["pc"]>=.68 and r["max_blank"]>=.40,
    "p65_league50": lambda r: r["p"]>=.65 and r["pc"]>=.63 and r["league_btts"]<=.50,
    "p65_league48": lambda r: r["p"]>=.65 and r["pc"]>=.63 and r["league_btts"]<=.48,
    "p68_league50": lambda r: r["p"]>=.68 and r["pc"]>=.66 and r["league_btts"]<=.50,
    "p68_league48": lambda r: r["p"]>=.68 and r["pc"]>=.66 and r["league_btts"]<=.48,
    "p65_blank35_league50": lambda r: (r["p"]>=.65 and r["pc"]>=.63
        and r["max_blank"]>=.35 and r["league_btts"]<=.50),
    "p65_blank40_league50": lambda r: (r["p"]>=.65 and r["pc"]>=.63
        and r["max_blank"]>=.40 and r["league_btts"]<=.50),
    "p68_blank35_league50": lambda r: (r["p"]>=.68 and r["pc"]>=.66
        and r["max_blank"]>=.35 and r["league_btts"]<=.50),
    "p68_blank40_league48": lambda r: (r["p"]>=.68 and r["pc"]>=.66
        and r["max_blank"]>=.40 and r["league_btts"]<=.48),
}

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

def experiment(history):
    runtime=train_runtime(history,challenger=False)
    gate=runtime.get("btts_quality_gate")
    periods={"train":[],"validation":[],"test":[]}
    from bsd_v2_btts_h2h import btts_h2h_decision
    for _,event in runtime["index"].global_games:
        dt=fixture_datetime(event)
        if dt.year!=2026 or dt.month>10 or outcome_scores(event) is None:
            continue
        h2h_ok,_,_=btts_h2h_decision(event,runtime["index"],"BTTS_NO")
        if not h2h_ok:
            continue
        historical=dict(event,status="notstarted",home_score=None,away_score=None)
        report=evaluate_fixture(historical,runtime,now=dt-timedelta(minutes=1),policy=V3Policy())
        if report.get("status")!="analyzed":
            continue
        row=next((x for x in report["candidates"] if x["key"]=="BTTS_NO"),None)
        if row is None or row["decision"]["quality_tier"]=="simple":
            continue
        side=team_scoring_probabilities(event,runtime["index"],
                                        model=gate.team_model if gate else None)
        feat=btts_features(event,runtime["index"])
        if side is None or feat is None:
            continue
        league=float(feat[9]+.5)
        max_blank=max(float(side["home_blank"]),float(side["away_blank"]))
        h,a=outcome_scores(event)
        item={
            "p":float(row["probability"]),
            "pc":float(row["conservative_probability"]),
            "max_blank":max_blank,
            "min_side_score":min(float(side["home_scores"]),float(side["away_scores"])),
            "league_btts":league,
            "won":bool(h==0 or a==0),
        }
        key="train" if dt.month<=6 else ("validation" if dt.month<=9 else "test")
        periods[key].append(item)

    tables={period:{name:_stats([r for r in rows if rule(r)])
                    for name,rule in POLICIES.items()}
            for period,rows in periods.items()}
    train=tables["train"];validation=tables["validation"]
    base_train=train["base65"];base_val=validation["base65"]
    candidates=[]
    for name in POLICIES:
        if name=="base65":continue
        tr,va=train[name],validation[name]
        if tr["n"]<40 or va["n"]<25:continue
        if tr["hit_rate"] is None or va["hit_rate"] is None:continue
        # Stability veto: no more than 3pp worse than base, and >=70% absolute.
        if tr["hit_rate"]<max(.70,base_train["hit_rate"]-.03):continue
        candidates.append(name)
    chosen=(max(candidates,key=lambda n:(validation[n]["wilson_low"],
                                        validation[n]["hit_rate"],
                                        validation[n]["n"]))
            if candidates else "base65")
    accepted=(chosen!="base65" and validation[chosen]["hit_rate"] is not None
              and validation[chosen]["hit_rate"]>=.75
              and validation[chosen]["hit_rate"]>=base_val["hit_rate"]+.02)
    active=chosen if accepted else "base65"
    return {
        "format":"bsd-v3-btts-no-policy-experiment-v1",
        "stability_period":"2026-01 through 2026-06",
        "selection_period":"2026-07 through 2026-09",
        "test_period":"2026-10",
        "existing_h2h_rule":"BTTS_NO requires latest completed H2H to be BTTS_NO",
        "chosen_on_recent_selection":chosen,
        "accepted":accepted,
        "active_policy":active,
        "tables":tables,
        "october_base":tables["test"]["base65"],
        "october_filtered":tables["test"][active],
        "warning":"Retrospective research; October is not used to choose the policy. Prospective confirmation remains required."
    }
