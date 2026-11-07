"""Backtest the CURRENT BSD V3 reliability policy on a closed calendar month.

This is a retrospective diagnostic, not independent prospective evidence.
It never fabricates historical bookmaker odds and therefore never reports ROI.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import timedelta
from math import log,sqrt
from .engine import train_runtime,evaluate_fixture
from .legacy import fixture_datetime,outcome_scores,markets_from_matrix,score_matrix,realized
from .policy import V3Policy

_MARKETS={c.key:c for c in markets_from_matrix(score_matrix(1.4,1.2))}
PREFERRED=frozenset({"1","2","BTTS_YES","OVER_15","OVER_25"})

def _wilson(wins,n,z=1.96):
    if not n:return None
    p=wins/n
    q=z*z
    center=(p+q/(2*n))/(1+q/n)
    half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
    return [round(max(0,center-half),5),round(min(1,center+half),5)]

def _finish(bucket):
    n=bucket["n"]
    if not n:
        return {"n":0,"wins":0,"hit_rate":None,"wilson_95":None,
                "mean_probability":None,"brier":None,"logloss":None}
    return {"n":n,"wins":bucket["wins"],
            "hit_rate":round(bucket["wins"]/n,5),
            "wilson_95":_wilson(bucket["wins"],n),
            "mean_probability":round(bucket["sum_p"]/n,5),
            "brier":round(bucket["brier"]/n,6),
            "logloss":round(bucket["logloss"]/n,6)}

def _observe(bucket,p,won):
    p=max(.000001,min(.999999,float(p)))
    y=int(bool(won))
    bucket["n"]+=1
    bucket["wins"]+=y
    bucket["sum_p"]+=p
    bucket["brier"]+=(p-y)**2
    bucket["logloss"]-=y*log(p)+(1-y)*log(1-p)

def monthly_policy_backtest(history, *, year, month, policy=V3Policy(),
                            enable_challengers=False):
    runtime=train_runtime(history,challenger=enable_challengers)
    events=[]
    for _,event in runtime["index"].global_games:
        try:
            kickoff=fixture_datetime(event)
        except (ValueError,TypeError,OverflowError):
            continue
        if kickoff.year==year and kickoff.month==month and outcome_scores(event) is not None:
            events.append(event)
    events.sort(key=lambda e:(fixture_datetime(e),str(e.get("id"))))
    counters=Counter()
    by_market=defaultdict(lambda:{"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.})
    primary_by_market=defaultdict(lambda:{"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.})
    preferred=defaultdict(lambda:{"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.})
    fallback=defaultdict(lambda:{"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.})
    confidence=defaultdict(lambda:{"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.})
    over25_priority={"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.}
    sample=[]
    for finished in events:
        kickoff=fixture_datetime(finished)
        # Recreate the fixture exactly as it was one minute before kickoff:
        # no final score and upcoming state.
        historical=dict(finished)
        historical["status"]="notstarted"
        historical["home_score"]=None
        historical["away_score"]=None
        report=evaluate_fixture(historical,runtime,now=kickoff-timedelta(minutes=1),
                                policy=policy)
        if report.get("status")!="analyzed":
            counters["rejected"]+=1
            counters["rejected_"+str(report.get("reason"))]+=1
            continue
        counters["analyzed"]+=1
        choices=report["selections"]["pro_vip_shadow"]
        over25_choices=report["selections"].get("over25_priority_shadow") or []
        hs,aws=outcome_scores(finished)
        all_rows={row["key"]:row for row in report["candidates"]}
        if over25_choices:
            row=all_rows["OVER_25"]
            won=bool(realized(_MARKETS["OVER_25"],hs,aws))
            _observe(over25_priority,row["probability"],won)
            counters["over25_priority_picks"]+=1
            counters["over25_priority_wins"]+=int(won)
        if not choices:
            counters["no_pick"]+=1
            continue
        counters["fixtures_with_pick"]+=1
        selected={key:all_rows[key] for key in choices}
        fixture_rows=[]
        for position,key in enumerate(choices):
            row=selected[key]
            market=_MARKETS[key]
            won=bool(realized(market,hs,aws))
            p=row["probability"]
            _observe(by_market[key],p,won)
            counters["selections"]+=1
            if key in PREFERRED:
                _observe(preferred[key],p,won)
                counters["preferred_selections"]+=1
            else:
                _observe(fallback[key],p,won)
                counters["fallback_selections"]+=1
            band=f"{int(p*20)*5:02d}-{int(p*20)*5+4:02d}%"
            _observe(confidence[band],p,won)
            if position==0:
                _observe(primary_by_market[key],p,won)
                counters["primary_picks"]+=1
                if key in PREFERRED:
                    counters["primary_preferred"]+=1
                else:
                    counters["primary_fallback"]+=1
            fixture_rows.append({"key":key,"probability":round(p,5),
                                 "conservative_probability":row["conservative_probability"],
                                 "won":won})
        if len(sample)<50:
            sample.append({"event_id":str(finished["id"]),
                           "kickoff_utc":kickoff.isoformat(),
                           "score":[hs,aws],
                           "selections":fixture_rows})
    def finalize_table(table):
        return {key:_finish(value) for key,value in sorted(table.items())}
    overall={"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.}
    for value in by_market.values():
        for field in overall:
            overall[field]+=value[field]
    primary_overall={"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.}
    for value in primary_by_market.values():
        for field in primary_overall:
            primary_overall[field]+=value[field]
    return {
        "format":"bsd-v3-monthly-policy-backtest-v1",
        "year":year,"month":month,
        "period":f"{year:04d}-{month:02d}-01 through month end",
        "model_policy":"current BSD V3 reliability policy, no historical odds",
        "fixtures_in_archive":len(events),
        "counts":dict(counters),
        "all_selections":_finish(overall),
        "primary_picks":_finish(primary_overall),
        "over25_priority_shadow":_finish(over25_priority),
        "by_market":finalize_table(by_market),
        "primary_by_market":finalize_table(primary_by_market),
        "preferred_markets":finalize_table(preferred),
        "fallback_markets":finalize_table(fallback),
        "confidence_bands":finalize_table(confidence),
        "calibration":runtime["calibration"].metadata() if runtime.get("calibration") else None,
        "goal_strength":runtime["goal_strength"].metadata() if runtime.get("goal_strength") else None,
        "sample_first_50":sample,
        "real_bookmaker_roi":None,
        "warnings":[
            "Retrospective backtest: current November policy is applied to October matches.",
            "The current policy was designed after observing 2026 historical behavior; October is not an untouched final test set.",
            "No historical bookmaker snapshots are fabricated, so ROI/value performance is intentionally unavailable.",
            "Features are computed at each historical kickoff using only prior matches through the BSD temporal index."
        ]
    }
