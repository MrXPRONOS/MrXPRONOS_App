"""Prospective V3 settlement writes NEW records, never changes forecasts.

There is no historical ROI without actual pre-kickoff verified named-bookmaker
odds stored in the original immutable forecast entry.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta
from math import sqrt
from .legacy import outcome_scores, fixture_datetime, realized
from .policy import utc_datetime
from .registry import append_once,verify_registry
from bsd_v3.legacy import markets_from_matrix,score_matrix

_MARKETS={c.key:c for c in markets_from_matrix(score_matrix(1.4,1.2))}

def settle_forecast(forecast, final_event, *, now):
    now=utc_datetime(now)
    if forecast.get("event_id")!=str(final_event.get("id")):
        raise ValueError("Different match IDs")
    kickoff=utc_datetime(forecast["kickoff_utc"])
    if fixture_datetime(final_event)!=kickoff:
        raise ValueError("Match kickoff changed; settle manually")
    if now < kickoff+timedelta(hours=4):
        raise ValueError("Four-hour settlement buffer")
    scores=outcome_scores(final_event)
    if scores is None:
        raise ValueError("Unsettled or invalid match scores")
    rows={}
    for candidate in forecast["candidates"]:
        key=candidate["key"]
        if key not in _MARKETS:
            continue
        won=bool(realized(_MARKETS[key],*scores))
        quote=candidate.get("quote")
        executable=bool(quote and quote.get("verified") and quote.get("executable"))
        odds=quote.get("odds") if executable else None
        rows[key]={"won":won,"settled":True,
                   "return_per_unit":round(odds-1 if won else -1,6)
                       if odds is not None else None,
                   "observed_named_bookmaker_odds":odds}
    return {"event_id":forecast["event_id"],"kickoff_utc":forecast["kickoff_utc"],
            "result_score":[scores[0],scores[1]],
            "settled_at_utc":now.isoformat(),"markets":rows}

def settle_registry(path,final_events,*,now):
    """Read old forecast entries, only add one immutable settlement per forecast."""
    events={str(event.get("id")):event for event in final_events
            if isinstance(event,dict) and event.get("id") is not None}
    created=0
    skipped={}
    for entry in verify_registry(path):
        if entry["type"]!="forecast":continue
        forecast=entry["payload"]
        event=events.get(forecast["event_id"])
        if event is None:
            skipped["missing_result"]=skipped.get("missing_result",0)+1
            continue
        try:
            settlement=settle_forecast(forecast,event,now=now)
            _,added=append_once(path,"settlement",entry["id"],settlement)
            created+=int(added)
        except (ValueError,KeyError,TypeError) as exc:
            key=type(exc).__name__
            skipped[key]=skipped.get(key,0)+1
    return {"new_settlements":created,"not_settled":skipped}

def performance_report(path):
    entries=verify_registry(path)
    forecasts={x["id"]:x["payload"] for x in entries if x["type"]=="forecast"}
    by_market=defaultdict(lambda:{"n":0,"wins":0,"sum_p":0.,"brier":0.,
                                   "roi_units":0.,"roi_n":0})
    for entry in entries:
        if entry["type"]!="settlement":continue
        forecast=forecasts.get(entry["id"])
        if forecast is None:
            continue
        original={r["key"]:r for r in forecast["candidates"]}
        for key,outcome in entry["payload"]["markets"].items():
            if key not in original:continue
            p=original[key]["probability"]
            y=int(outcome["won"])
            row=by_market[key]
            row["n"]+=1
            row["wins"]+=y
            row["sum_p"]+=p
            row["brier"]+=(p-y)**2
            if outcome["return_per_unit"] is not None:
                row["roi_units"]+=outcome["return_per_unit"]
                row["roi_n"]+=1
    result={}
    for key,v in by_market.items():
        n=v["n"]
        result[key]={"n":n,"win_rate":round(v["wins"]/n,6),
                     "mean_predicted":round(v["sum_p"]/n,6),
                     "brier":round(v["brier"]/n,6),
                     "roi_verified_named_bookmaker":round(v["roi_units"]/v["roi_n"],6)
                        if v["roi_n"] else None,
                     "priced_n":v["roi_n"]}
    return {"format":"bsd-v3-prospective-evaluation-v1",
            "forecasts":len(forecasts),
            "settlements":sum(x["type"]=="settlement" for x in entries),
            "by_market":result,
            "warning":"Observational recorded quotes; not a confirmed bet or net of transaction costs."}
