"""Exact 2026 year-to-date backtest for the CURRENT BSD V3 policy.

One runtime is trained once, then every finished fixture in the requested period
is replayed one minute before kickoff. Final scores are used only after the
forecast decision is produced. Historical bookmaker odds are never invented.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from math import log,sqrt
from .engine import train_runtime,evaluate_fixture
from .legacy import fixture_datetime,outcome_scores,markets_from_matrix,score_matrix,realized
from .policy import V3Policy

UTC=timezone.utc
_MARKETS={c.key:c for c in markets_from_matrix(score_matrix(1.4,1.2))}
PRIMARY_PREFERRED=frozenset({"1","2","BTTS_YES","OVER_15"})

def _bucket():
    return {"n":0,"wins":0,"sum_p":0.,"brier":0.,"logloss":0.}

def _observe(bucket,p,won):
    p=max(.000001,min(.999999,float(p)))
    y=int(bool(won))
    bucket["n"]+=1
    bucket["wins"]+=y
    bucket["sum_p"]+=p
    bucket["brier"]+=(p-y)**2
    bucket["logloss"]-=y*log(p)+(1-y)*log(1-p)

def _wilson(wins,n,z=1.96):
    if not n:return None
    p=wins/n;q=z*z
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

def year_to_date_backtest(history,*,year=2026,end_date="2026-11-07",
                          policy=V3Policy(),enable_challengers=False):
    cutoff=datetime.fromisoformat(end_date+"T23:59:59+00:00")
    start=datetime(year,1,1,tzinfo=UTC)
    runtime=train_runtime(history,challenger=enable_challengers)
    events=[]
    for _,event in runtime["index"].global_games:
        try: kickoff=fixture_datetime(event)
        except (ValueError,TypeError,OverflowError): continue
        if start<=kickoff<=cutoff and outcome_scores(event) is not None:
            events.append(event)
    events.sort(key=lambda e:(fixture_datetime(e),str(e.get("id"))))

    counters=Counter()
    by_market=defaultdict(_bucket)
    primary_by_market=defaultdict(_bucket)
    preferred=defaultdict(_bucket)
    fallback=defaultdict(_bucket)
    confidence=defaultdict(_bucket)
    monthly={m:{
        "fixtures":0,"analyzed":0,"fixtures_with_pick":0,
        "selections":_bucket(),"primary":_bucket(),"over25":_bucket()
    } for m in range(1,13)}
    over25=_bucket()
    examples=[]

    for finished in events:
        kickoff=fixture_datetime(finished)
        month=kickoff.month
        monthly[month]["fixtures"]+=1
        historical=dict(finished,status="notstarted",home_score=None,away_score=None)
        report=evaluate_fixture(historical,runtime,now=kickoff-timedelta(minutes=1),
                                policy=policy)
        if report.get("status")!="analyzed":
            counters["rejected"]+=1
            counters["rejected_"+str(report.get("reason"))]+=1
            continue
        counters["analyzed"]+=1
        monthly[month]["analyzed"]+=1
        hs,aws=outcome_scores(finished)
        rows={r["key"]:r for r in report["candidates"]}

        over25_keys=report["selections"].get("over25_priority_shadow") or []
        if "OVER_25" in over25_keys:
            row=rows["OVER_25"];won=bool(realized(_MARKETS["OVER_25"],hs,aws))
            _observe(over25,row["probability"],won)
            _observe(monthly[month]["over25"],row["probability"],won)
            counters["over25_priority_picks"]+=1
            counters["over25_priority_wins"]+=int(won)

        choices=report["selections"].get("pro_vip_shadow") or []
        if not choices:
            counters["no_pick"]+=1
            continue
        counters["fixtures_with_pick"]+=1
        monthly[month]["fixtures_with_pick"]+=1
        fixture_rows=[]
        for position,key in enumerate(choices):
            row=rows[key]
            won=bool(realized(_MARKETS[key],hs,aws))
            p=row["probability"]
            _observe(by_market[key],p,won)
            _observe(monthly[month]["selections"],p,won)
            counters["selections"]+=1
            if key in PRIMARY_PREFERRED:
                _observe(preferred[key],p,won)
                counters["preferred_selections"]+=1
            else:
                _observe(fallback[key],p,won)
                counters["fallback_selections"]+=1
            band=f"{int(p*20)*5:02d}-{int(p*20)*5+4:02d}%"
            _observe(confidence[band],p,won)
            if position==0:
                _observe(primary_by_market[key],p,won)
                _observe(monthly[month]["primary"],p,won)
                counters["primary_picks"]+=1
                if key in PRIMARY_PREFERRED:counters["primary_preferred"]+=1
                else:counters["primary_fallback"]+=1
            fixture_rows.append({"key":key,"p":round(p,5),"won":won})
        if len(examples)<100:
            examples.append({"event_id":str(finished["id"]),
                             "kickoff_utc":kickoff.isoformat(),
                             "score":[hs,aws],"selections":fixture_rows,
                             "over25_priority":bool(over25_keys)})

    def table(values):return {k:_finish(v) for k,v in sorted(values.items())}
    all_sel=_bucket()
    for v in by_market.values():
        for k in all_sel:all_sel[k]+=v[k]
    all_primary=_bucket()
    for v in primary_by_market.values():
        for k in all_primary:all_primary[k]+=v[k]
    month_rows={}
    for m,data in monthly.items():
        if not data["fixtures"]:continue
        month_rows[f"{year}-{m:02d}"]={
            "fixtures":data["fixtures"],
            "analyzed":data["analyzed"],
            "fixtures_with_pick":data["fixtures_with_pick"],
            "all_selections":_finish(data["selections"]),
            "primary_picks":_finish(data["primary"]),
            "over25_priority_shadow":_finish(data["over25"]),
        }
    return {
        "format":"bsd-v3-ytd-policy-backtest-v1",
        "period":f"{year}-01-01 through {end_date}",
        "as_of_cutoff_utc":cutoff.isoformat(),
        "fixtures_in_archive":len(events),
        "counts":dict(counters),
        "all_selections":_finish(all_sel),
        "primary_picks":_finish(all_primary),
        "over25_priority_shadow":_finish(over25),
        "by_market":table(by_market),
        "primary_by_market":table(primary_by_market),
        "primary_preferred_markets":table(preferred),
        "fallback_markets":table(fallback),
        "confidence_bands":table(confidence),
        "by_month":month_rows,
        "calibration":runtime["calibration"].metadata() if runtime.get("calibration") else None,
        "goal_strength":runtime["goal_strength"].metadata() if runtime.get("goal_strength") else None,
        "btts_quality_gate":runtime["btts_quality_gate"].metadata()
            if runtime.get("btts_quality_gate") else None,
        "examples_first_100":examples,
        "real_bookmaker_roi":None,
        "warnings":[
            "Retrospective backtest: the current November 2026 policy is applied backward to 2026 matches.",
            "2026 helped inform later project decisions, so this is not an untouched prospective test.",
            "Each fixture is replayed one minute before kickoff; final score is used only after selection.",
            "No historical bookmaker quote is fabricated; ROI/value performance is unavailable.",
            "The requested calendar year is incomplete as of 2026-11-07, so results cover 2026-01-01 through 2026-11-07 only."
        ]
    }
