"""Chronological Over 2.5 threshold experiment for BSD V3.

Candidate thresholds are selected without using October 2026:
- Jan-Jun 2026: stability check
- Jul-Sep 2026: threshold selection
- Oct 2026: held-out diagnostic

No historical bookmaker odds are fabricated.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from math import sqrt
from .engine import train_runtime,evaluate_fixture
from .legacy import fixture_datetime,outcome_scores
from .policy import V3Policy

THRESHOLDS=(.60,.62,.64,.66,.68,.70,.72,.74,.76)

def _stats(rows):
    n=len(rows)
    if not n:
        return {"n":0,"wins":0,"hit_rate":None,"wilson_low":None,"wilson_95":None,
                "mean_probability":None,"mean_conservative":None}
    wins=sum(int(r["won"]) for r in rows)
    p=wins/n
    z=1.96;q=z*z
    center=(p+q/(2*n))/(1+q/n)
    half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
    return {"n":n,"wins":wins,"hit_rate":round(p,5),
            "wilson_low":round(max(0,center-half),5),
            "wilson_95":[round(max(0,center-half),5),round(min(1,center+half),5)],
            "mean_probability":round(sum(r["p"] for r in rows)/n,5),
            "mean_conservative":round(sum(r["pc"] for r in rows)/n,5)}

def experiment(history):
    runtime=train_runtime(history,challenger=False)
    periods={"train":[],"validation":[],"test":[]}
    for _,event in runtime["index"].global_games:
        dt=fixture_datetime(event)
        if dt.year!=2026 or dt.month>10 or outcome_scores(event) is None:
            continue
        historical=dict(event,status="notstarted",home_score=None,away_score=None)
        report=evaluate_fixture(historical,runtime,now=dt-timedelta(minutes=1),
                                policy=V3Policy())
        if report.get("status")!="analyzed":
            continue
        row=next((x for x in report["candidates"] if x["key"]=="OVER_25"),None)
        if row is None:
            continue
        # Require the same data-quality eligibility that Pro/VIP uses, but do
        # not apply the current generic probability threshold because that is
        # exactly what this experiment is selecting.
        if row["decision"]["quality_tier"]=="simple":
            continue
        if row.get("market_probability_lift",0)<=0:
            continue
        h,a=outcome_scores(event)
        item={"event_id":str(event["id"]),"kickoff":dt.isoformat(),
              "p":float(row["probability"]),
              "pc":float(row["conservative_probability"]),
              "won":bool(h+a>2.5)}
        key="train" if dt.month<=6 else ("validation" if dt.month<=9 else "test")
        periods[key].append(item)
    tables={}
    for period,rows in periods.items():
        tables[period]={}
        for threshold in THRESHOLDS:
            # Same two-stage convention as other preferred markets:
            # conservative floor is two points below the central floor.
            selected=[r for r in rows if r["p"]>=threshold and r["pc"]>=threshold-.02]
            tables[period][f"{threshold:.2f}"]=_stats(selected)

    train=tables["train"];validation=tables["validation"]
    candidates=[]
    base_key="0.60"
    for threshold in THRESHOLDS:
        key=f"{threshold:.2f}"
        tr=train[key];va=validation[key]
        if tr["n"]<80 or va["n"]<40:
            continue
        # Do not accept a threshold whose earlier-period accuracy collapses.
        if tr["hit_rate"] is None or tr["hit_rate"]<.68:
            continue
        candidates.append(key)
    chosen=(max(candidates,key=lambda k:(validation[k]["wilson_low"],
                                         validation[k]["hit_rate"],
                                         validation[k]["n"]))
            if candidates else base_key)
    accepted=(chosen!=base_key and validation[chosen]["hit_rate"] is not None
              and validation[chosen]["hit_rate"]>=.74)
    active=chosen if accepted else base_key
    return {
        "format":"bsd-v3-over25-threshold-experiment-v1",
        "stability_period":"2026-01 through 2026-06",
        "selection_period":"2026-07 through 2026-09",
        "test_period":"2026-10",
        "candidate_thresholds":list(THRESHOLDS),
        "chosen_on_recent_selection":chosen,
        "accepted":accepted,
        "active_threshold":active,
        "active_conservative_threshold":round(float(active)-.02,2),
        "tables":tables,
        "october":tables["test"][active],
        "warning":"Retrospective threshold research. October is not used to choose the threshold; prospective confirmation is still required."
    }
