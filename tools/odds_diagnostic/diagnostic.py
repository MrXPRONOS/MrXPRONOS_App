#!/usr/bin/env python3
"""Audit offline des structures de cotes — aucune requête vers les bookmakers."""
import json, argparse, re, pathlib, datetime
def analyze(payload, provider):
    if provider=="sportybet":
        events=[e for t in payload.get("data",{}).get("tournaments",[]) for e in t.get("events",[])]
    else:
        events=payload.get("Value",[])
    markets=[]
    for e in events:
        if provider=="sportybet": candidates=e.get("markets",[])
        else: candidates=e.get("E",[])
        for m in candidates:
            if not isinstance(m,dict): continue
            label=str(m.get("desc") or m.get("name") or m.get("marketName") or "")
            types=[key for key,pat in {"corners":r"corner","shots":r"shot|tir","fouls":r"foul|faute"}.items() if re.search(pat,label,re.I)]
            if not types: continue
            outcomes=m.get("outcomes",[])
            markets.append({"label":label,"types":types,"over_under":any(re.search("over|under|plus|moins",str(o.get("desc","")),re.I) for o in outcomes if isinstance(o,dict)),"valid_odds":sum(1 for o in outcomes if isinstance(o,dict) and str(o.get("odds","")).replace(".","",1).isdigit() and float(o["odds"])>1)})
    return {"provider":provider,"events":len(events),"relevant_markets":markets,"counts":{k:sum(k in m["types"] for m in markets) for k in ("corners","shots","fouls")}}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sportybet-json",type=pathlib.Path)
    p.add_argument("--xbet-json",type=pathlib.Path)
    p.add_argument("--output",default="odds_diagnostic_results")
    a=p.parse_args()
    output=pathlib.Path(a.output); output.mkdir(parents=True,exist_ok=True)
    fake_s={"data":{"tournaments":[{"events":[{"markets":[{"desc":"Total Corners","outcomes":[{"desc":"Over","odds":"1.87"},{"desc":"Under","odds":"1.93"}]},{"desc":"Total Shots","outcomes":[{"desc":"Over","odds":"1.75"}]},{"desc":"Total Fouls","outcomes":[{"desc":"Under","odds":"1.89"}]}]}]}]}}
    fake_x={"Value":[{"O1":"Demo A","O2":"Demo B","E":[{"T":1,"C":1.85}]}]}
    out=[]
    for provider,path,fixture in (("sportybet",a.sportybet_json,fake_s),("1xbet",a.xbet_json,fake_x)):
        payload=json.loads(path.read_text(encoding="utf-8")) if path else fixture
        item=analyze(payload,provider)
        item["source"]="provided_json" if path else "synthetic_offline"
        out.append(item)
    report={"timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"network_tested":False,"results":out}
    (output/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    html="<html><meta charset='utf-8'><body><h1>Mr XPRONOS — diagnostic offline</h1><p>Les tests synthétiques ne prouvent pas l'accès réseau réel.</p><pre>"+json.dumps(report,indent=2,ensure_ascii=False)+"</pre></body></html>"
    (output/"report.html").write_text(html,encoding="utf-8")
    for r in out: print(r["provider"],r["source"],r["events"],r["counts"])
    assert out[0]["counts"]=={"corners":1,"shots":1,"fouls":1} if not a.sportybet_json else True
    print("Rapport écrit :",output)
if __name__=="__main__": main()
