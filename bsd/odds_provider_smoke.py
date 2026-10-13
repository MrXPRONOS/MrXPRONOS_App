#!/usr/bin/env python3
"""One-request-per-provider credential and real-schema smoke test.

No authentication values, raw URLs containing keys, response bodies, team names,
or exception strings are printed. This script never writes to Supabase/Telegram.
"""
from __future__ import annotations
import os
import sys
import json
import requests

def probe(name, url, headers=None):
    try:
        response = requests.get(url, headers=headers or {}, timeout=35)
        status = response.status_code
        if status != 200:
            print(json.dumps({"provider":name,"http":status,"result":"rejected" if status in (401,403,429) else "http_error"}))
            return False
        data = response.json()
        if name == "pinnwire":
            events = data.get("events") if isinstance(data,dict) else None
            valid = isinstance(events,list)
            markets = sum(1 for x in (events or []) if isinstance(x,dict) and isinstance(x.get("periods"),dict))
            count = len(events) if valid else 0
        elif name == "oddslink":
            valid = isinstance(data,list)
            markets = sum(1 for x in (data or []) if isinstance(x,dict) and isinstance(x.get("bookmakers"),list)) if valid else 0
            count = len(data) if valid else 0
        else:
            events = data.get("matches") if isinstance(data,dict) else None
            valid = isinstance(events,list)
            markets = sum(1 for x in (events or []) if isinstance(x,dict) and isinstance(x.get("quotes"),list))
            count = len(events) if valid else 0
        print(json.dumps({"provider":name,"http":status,"schema_valid":valid,"fixtures":count,"market_structures":markets}))
        return valid
    except (ValueError, requests.RequestException) as exc:
        print(json.dumps({"provider":name,"result":"error","kind":type(exc).__name__}))
        return False

def main():
    key1 = os.getenv("PINNWIRE_API_KEY") or ""
    key2 = os.getenv("ODDSLINK_API_KEY") or ""
    selected = os.getenv("ODDS_SMOKE_PROVIDER","all")
    if selected not in ("all","pinnwire","oddslink","moviodds"):
        raise SystemExit("invalid provider")
    ok = True
    if selected in ("all","pinnwire"):
        if not key1:
            print('{"provider":"pinnwire","result":"missing_secret"}')
            ok = False
        else:
            ok = probe("pinnwire","https://pinnwire.com/kit/v1/prematch/fixtures?sport_id=1",
                       {"x-api-key":key1}) and ok
    if selected in ("all","oddslink"):
        if not key2:
            print('{"provider":"oddslink","result":"missing_secret"}')
            ok = False
        else:
            ok = probe("oddslink","https://oddslink.app/v1/sports/soccer/odds?league=epl&oddsFormat=decimal",
                       {"X-API-Key":key2}) and ok
    if selected in ("all","moviodds"):
        ok = probe("moviodds","https://moviodds.com/odds?sport=soccer&groups=40") and ok
    print("ODDS_SMOKE_RESULT="+("PASS" if ok else "FAIL"))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
