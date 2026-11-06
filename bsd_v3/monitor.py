"""Prospective model calibration surveillance and conservative circuit breakers.

Only events already observed pre-match and later settled contribute.
No learning or publication ever occurs in the monitor.
"""
from __future__ import annotations
from collections import defaultdict
from math import log,sqrt
from .registry import verify_registry,canonical_forecasts

def wilson_interval(wins,n,z=1.96):
    if not n:return None
    p=wins/n
    q=z*z
    center=(p+q/(2*n))/(1+q/n)
    half=z*sqrt((p*(1-p)+q/(4*n))/n)/(1+q/n)
    return [round(max(0,center-half),6),round(min(1,center+half),6)]

def _empty():
    return {"n":0,"wins":0,"sum_predicted":0.,"brier_sum":0.,
            "logloss_sum":0.,"priced":0,"paper_profit":0.}

def _observe(bucket,y,p,price=None):
    p=max(.000001,min(.999999,float(p)))
    bucket["n"]+=1
    bucket["wins"]+=int(y)
    bucket["sum_predicted"]+=p
    bucket["brier_sum"]+=(p-int(y))**2
    bucket["logloss_sum"]-=int(y)*log(p)+(1-int(y))*log(1-p)
    if price is not None:
        bucket["priced"]+=1
        bucket["paper_profit"]+=(price-1 if y else -1)

def _finalize(bucket,min_samples=100,max_gap=.06):
    n=bucket["n"]
    hit=bucket["wins"]/n if n else None
    pred=bucket["sum_predicted"]/n if n else None
    band=wilson_interval(bucket["wins"],n)
    # A small-sample 79% label is not an observed 79% hit-rate guarantee.
    gap=pred-hit if n else None
    shadow=bool(n>=min_samples and band and pred>band[1]+max_gap/2)
    return {"n":n,"wins":bucket["wins"],"hit_rate":round(hit,6) if n else None,
            "predicted_mean":round(pred,6) if n else None,
            "calibration_gap":round(gap,6) if n else None,
            "wilson_95":band,
            "brier":round(bucket["brier_sum"]/n,6) if n else None,
            "logloss":round(bucket["logloss_sum"]/n,6) if n else None,
            "priced_n":bucket["priced"],
            "paper_roi_named_bookmaker":round(bucket["paper_profit"]/bucket["priced"],6)
                    if bucket["priced"] else None,
            "circuit_breaker":shadow}

def monitor(path,*,min_samples=100,max_gap=.06):
    entries=verify_registry(path)
    canonical=canonical_forecasts(entries)
    forecasts={x["id"]:x["payload"] for x in canonical.values()}
    sections={name:defaultdict(_empty) for name in
              ("market","family","league_market","probability_band",
               "pro_vip_shadow","value_shadow")}
    total=0
    for record in entries:
        if record["type"]!="settlement":continue
        forecast=forecasts.get(record["id"])
        if not forecast:continue
        stored={r["key"]:r for r in forecast.get("candidates",[])}
        selections=forecast.get("selections") or {}
        pro=set(selections.get("pro_vip_shadow") or [])
        value=set(selections.get("value_shadow") or [])
        league=str(forecast.get("league_key") or "unknown")
        for key,realized in (record["payload"].get("markets") or {}).items():
            row=stored.get(key)
            if row is None or realized.get("settled") is not True:continue
            p=row.get("probability")
            if type(p) not in (int,float) or not 0 < p < 1:continue
            y=int(bool(realized["won"]))
            quote=row.get("quote") or {}
            price=quote.get("odds") if quote.get("verified") and quote.get("executable") else None
            band=f"{int(p*10)*10:02d}-{int(p*10)*10+9:02d}%"
            family=row.get("family") or "unknown"
            for section,bucket in (("market",key),("family",family),
                                   ("league_market",league+"|"+key),
                                   ("probability_band",band)):
                _observe(sections[section][bucket],y,p,price)
            if key in pro:_observe(sections["pro_vip_shadow"][key],y,p,price)
            if key in value:_observe(sections["value_shadow"][key],y,p,price)
            total+=1
    report={}
    disabled=[]
    for section,values in sections.items():
        report[section]={k:_finalize(v,min_samples,max_gap) for k,v in sorted(values.items())}
        if section=="market":
            disabled=[key for key,v in report[section].items() if v["circuit_breaker"]]
    return {"format":"bsd-v3-prospective-monitor-v1","records":len(entries),
            "forecasts":len(forecasts),"market_outcomes":total,
            "sections":report,"disabled_keys":disabled,
            "available_for_publication":False,
            "notes":["Shadow performance is observational, not real betting execution.",
                     "ROI is a paper return only for captured named sportsbook quotes.",
                     "Disable keys only with sufficient settled samples and a conservative Wilson gap.",
                     "Correlated picks and matches require additional prospective evaluation."]}
