#!/usr/bin/env python3
"""Diagnostic ponctuel de la structure graphique renvoyée par BSD V2.

N'affiche ni clé API ni headers. Il liste seulement les champs visuels présents
sur quelques événements/équipes afin d'adapter le renderer Mr XPRONOS.
"""
from __future__ import annotations
import json, sys
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"bsd"))
from bsd_api import BSDClient

TOKENS=("logo","crest","badge","image","photo","icon","shirt","jersey","kit")

def visual_fields(obj, prefix=""):
    out={}
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=(prefix+"."+str(k)).strip(".")
            if any(t in str(k).lower() for t in TOKENS):
                out[p]=v
            if isinstance(v,(dict,list)):
                out.update(visual_fields(v,p))
    elif isinstance(obj,list):
        for i,v in enumerate(obj[:3]):
            out.update(visual_fields(v,f"{prefix}[{i}]"))
    return out

client=BSDClient(max_requests=8,max_retries=1)
page=client.list_events(date.today(),date.today(),max_pages=3,ttl=0)
print("BSD_VISUAL_DIAGNOSTIC events",len(page.events))
for event in page.events[:10]:
    summary={
        "id":event.get("id"),
        "home_team":event.get("home_team"),
        "away_team":event.get("away_team"),
        "visual":visual_fields(event),
    }
    print("BSD_VISUAL_EVENT",json.dumps(summary,ensure_ascii=False,default=str)[:7000])
