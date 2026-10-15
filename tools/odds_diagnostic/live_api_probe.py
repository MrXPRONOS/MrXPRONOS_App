#!/usr/bin/env python3
"""One-shot probe using official API-Football endpoints. Requires user's API key."""
import os,json,datetime,pathlib,urllib.request
out=pathlib.Path("odds_diagnostic_results");out.mkdir(exist_ok=True)
result={"timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"source":"API-Football official","actual_network_response":False}
key=os.getenv("API_FOOTBALL_KEY")
if not key:
    result["status"]="SKIPPED_MISSING_API_FOOTBALL_KEY"
else:
    def fetch(path):
        req=urllib.request.Request("https://v3.football.api-sports.io"+path,headers={"x-apisports-key":key,"Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=20) as resp:return json.load(resp)
    try:
        games=fetch("/fixtures?live=all")
        result["actual_network_response"]=True
        result["live_fixtures_count"]=len(games.get("response",[]))
        if games.get("response"):
            first=games["response"][0]
            ident=first["fixture"]["id"]
            result["fixture"]={"id":ident,"home":first["teams"]["home"]["name"],"away":first["teams"]["away"]["name"]}
            odds=fetch("/odds/live?fixture="+str(ident))
            result["odds_response_count"]=len(odds.get("response",[]))
            result["api_errors"]=odds.get("errors",{})
            names=[]
            for obj in odds.get("response",[]):
                for b in obj.get("bookmakers",[]):
                    for market in b.get("bets",[]):names.append(str(market.get("name","")))
            result["available_market_names"]=sorted(set(names))[:150]
            result["target_market_names"]=[n for n in result["available_market_names"] if any(x in n.lower() for x in ("corner","shot","foul","tir","faute"))]
            result["status"]="RESPONSE_OBTAINED"
        else:result["status"]="NO_LIVE_FIXTURES"
        result["fixtures_api_errors"]=games.get("errors",{})
    except Exception as err:
        result["status"]="API_REQUEST_FAILED"
        result["error_type"]=type(err).__name__
(out/"live_api_probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
