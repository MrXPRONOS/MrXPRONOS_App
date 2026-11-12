#!/usr/bin/env python3
"""Diagnostic local de structures de cotes autorisées. Aucun réseau, aucune table de codes 1xBet inventée."""
import argparse
import datetime
import html
import json
import pathlib
import re

PATTERNS = {"corners": r"corners?|corners? kick", "shots": r"shots?|tirs?", "fouls": r"fouls?|fautes?"}
FIELDS = ("desc", "name", "marketName", "label")
def events_of(data, provider):
    if provider == "sportybet":
        root = data.get("data", data) if isinstance(data, dict) else {}
        tournaments = root.get("tournaments", [])
        events = [e for t in tournaments if isinstance(t, dict) for e in t.get("events", []) if isinstance(e, dict)]
        return events or root.get("events", [])
    if isinstance(data, list):
        return data
    return data.get("Value", data.get("events", []))

def market_kind(label):
    return [k for k, pat in PATTERNS.items() if re.search(pat, label, re.I)]

def numeric_odd(value):
    try:
        n=float(value)
        return n if n > 1 and n < 10000 else None
    except (ValueError, TypeError):
        return None

def analyze(data, provider):
    events=events_of(data,provider)
    found=[]; unknown=0; total=0
    for event in events:
        candidates=event.get("markets", []) if provider=="sportybet" else event.get("E",event.get("markets",[]))
        for market in candidates:
            if not isinstance(market,dict): continue
            total+=1
            label=next((str(market[f]) for f in FIELDS if market.get(f)), "")
            kinds=market_kind(label)
            if not kinds:
                if provider=="1xbet" and ("T" in market or "G" in market):
                    unknown+=1
                continue
            outcomes=market.get("outcomes",[])
            if not isinstance(outcomes,list): outcomes=[]
            valid=sum(numeric_odd(o.get("odds",o.get("C"))) is not None for o in outcomes if isinstance(o,dict))
            over_under=any(re.search(r"over|under|plus|moins",str(o.get("desc",o.get("name",""))),re.I) for o in outcomes if isinstance(o,dict))
            found.append({"label":label,"kinds":kinds,"valid_odds":valid,"over_under":over_under})
    return {"provider":provider,"events":len(events),"markets_inspected":total,"unmapped_numeric_markets":unknown,"markets":found,"counts":{k:sum(k in m["kinds"] for m in found) for k in PATTERNS}}

def sample(provider):
    if provider=="sportybet":
        return {"data":{"tournaments":[{"events":[{"markets":[{"desc":"Total Corners","outcomes":[{"desc":"Over","odds":"1.87"},{"desc":"Under","odds":"1.93"}]},{"desc":"Total Shots","outcomes":[{"desc":"Over","odds":"1.75"}]},{"desc":"Total Fouls","outcomes":[{"desc":"Under","odds":"1.89"}]}]}]}]}}
    return {"Value":[{"O1":"Demo A","O2":"Demo B","E":[{"T":1,"C":1.85},{"T":2,"C":1.9}]}]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--sportybet-json",type=pathlib.Path)
    parser.add_argument("--xbet-json",type=pathlib.Path)
    parser.add_argument("--output",type=pathlib.Path,default=pathlib.Path("odds_diagnostic_results"))
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    reports=[]
    for provider,path in (("sportybet",args.sportybet_json),("1xbet",args.xbet_json)):
        data=json.loads(path.read_text(encoding="utf-8")) if path else sample(provider)
        r=analyze(data,provider)
        r["source"]="provided_json" if path else "synthetic_offline"
        reports.append(r)
        print(provider,r["source"],r["counts"],"unmapped:",r["unmapped_numeric_markets"])
    report={"generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"network_tested":False,"results":reports}
    raw=json.dumps(report,ensure_ascii=False,indent=2)
    (args.output/"report.json").write_text(raw,encoding="utf-8")
    (args.output/"report.html").write_text("<!doctype html><meta charset='utf-8'><title>Mr XPRONOS diagnostic</title><h1>Diagnostic hors ligne</h1><p>Aucune cote réelle vérifiée par le réseau.</p><pre>"+html.escape(raw)+"</pre>",encoding="utf-8")
if __name__=="__main__":
    main()
