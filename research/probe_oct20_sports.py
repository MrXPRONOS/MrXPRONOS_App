#!/usr/bin/env python3
"""Read-only diagnosis: why a football endpoint returned tennis and volleyball."""
import json
from datetime import date
from sportdata_api import fetch_games
r=fetch_games(date(2026,10,20),date(2026,10,20),timeout=40,show_odds=False)
print("SPORT_DIAG_STATUS",r.ok,"raw_games",len(r.games),"payload_keys",list(r.payload)[:30],flush=True)
def relevant(g):
    return {k:v for k,v in g.items() if any(s in k.lower() for s in ("sport","competition","type","category","name")) and not isinstance(v,(dict,list))}
for ident in ("4877806","4754818","4875944"):
    g=next((x for x in r.games if str(x.get("id"))==ident),None)
    if g:
        print("SPORT_DIAG_EXAMPLE",ident, json.dumps({"meta":relevant(g),"keys":list(g.keys()),"sport":g.get("sport"),"competition":g.get("competition"),"home":g.get("homeCompetitor"),"away":g.get("awayCompetitor")},ensure_ascii=False)[:3200],flush=True)
for key in ("sports","competitions","countries"):
    value=r.payload.get(key)
    if isinstance(value,list):
        print("SPORT_DIAG_METADATA",key,"count",len(value),"sample",json.dumps(value[:4],ensure_ascii=False)[:1500],flush=True)
    elif isinstance(value,dict):
        print("SPORT_DIAG_METADATA",key,"keys",list(value)[:10],flush=True)
print("SPORT_DIAG_UNIQUE",json.dumps([{**relevant(g),"keys":[k for k in g.keys() if "sport" in k.lower()]} for g in r.games[:5]],ensure_ascii=False)[:4500],flush=True)
if not r.ok: raise RuntimeError("SportData fetch failed")
