#!/usr/bin/env python3
"""Bounded SportsAPI Pro V2 dated football history into AES-GCM Git archive.

Provider fixture IDs are namespaced as 'v2-<id>' to avoid accidental mixing
with V1 IDs. This module never uses a future label in prematch features;
it only saves finished, verified football fixtures.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import os
import urllib.error
import urllib.request

from single_ml_v2_data import dates,utc_dt
from single_ml_v2_git import (ROOT,atomic_bytes,day_data,key_from_environment,
                              logical_for_day,path_for,rebuild_manifest,seal,load_days)

BASE="https://api.sportsapipro.com/v2/football/schedule/"
VERSION="v2_football_schedule_ft_v1"

def team_info(raw):
    if not isinstance(raw,dict):
        raise ValueError("Missing V2 team")
    name=str(raw.get("name") or "").strip()
    ident=raw.get("id")
    if not name or ident in (None,"",0):
        raise ValueError("No verifiable V2 team identity")
    sport=raw.get("sport")
    if isinstance(sport,dict) and str(sport.get("id"))!="1":
        raise ValueError("Wrong V2 team sport")
    return name,ident

def goals(raw):
    if not isinstance(raw,dict):
        raise ValueError("Missing score object")
    # Regular-time score is preferred to current scores that may include ET.
    value=raw.get("normaltime")
    if value is None:
        value=raw.get("current")
    if value is None or isinstance(value,bool):
        raise ValueError("Missing verified FT goals")
    candidate=int(value)
    if not 0<=candidate<=10 or float(value)!=candidate:
        raise ValueError("Bad fulltime goals")
    return candidate

def v2_fixture(event, day):
    """Return a certified normalized match or no row; never fabricate FT."""
    if not isinstance(event,dict):
        return None
    start=utc_dt(event.get("startTimestamp"))
    if start is None or start.date()!=day:
        return None
    status=event.get("status")
    if not isinstance(status,dict) or str(status.get("type","")).lower()!="finished":
        return None
    tour=event.get("tournament")
    if not isinstance(tour,dict):
        return None
    cat=tour.get("category")
    sport=cat.get("sport") if isinstance(cat,dict) else None
    if not isinstance(sport,dict) or str(sport.get("id"))!="1":
        return None
    try:
        home,hid=team_info(event.get("homeTeam"))
        away,aid=team_info(event.get("awayTeam"))
        h,a=goals(event.get("homeScore")),goals(event.get("awayScore"))
    except (TypeError,ValueError,OverflowError):
        return None
    if home==away or str(hid)==str(aid):
        return None
    event_id=str(event.get("id") or "").strip()
    tournament_name=str(tour.get("name") or "").strip()
    if not event_id.isdecimal() or not tournament_name:
        return None
    result={
        "id":"v2-"+event_id,
        "sportId":1,
        "start_time":start.isoformat().replace("+00:00","Z"),
        "home_team":home,"away_team":away,"competition":tournament_name,
        "home_score":h,"away_score":a,
        "status_group":4,"is_finished":True,
        "source":"sportsapipro_v2_schedule",
        "source_match_id":event_id,
        "source_competition_id":tour.get("id"),
        "source_home_team_id":hid,"source_away_team_id":aid,
        "source_date":str(day),
    }
    return result

def fetch_schedule(day, *,token,timeout=25,opener=urllib.request.urlopen):
    if not isinstance(day,date) or not token:
        raise ValueError("Missing V2 date or access token")
    url=BASE+day.isoformat()
    request=urllib.request.Request(url,headers={"x-api-key":token,
         "Accept":"application/json","User-Agent":"MrXPRONOS-Research-Only"})
    try:
        response=opener(request,timeout=timeout)
        with response as stream:
            raw=stream.read(12*1024*1024+1)
            if len(raw)>12*1024*1024:
                raise ValueError("V2 schedule response too large")
        document=json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("V2 schedule HTTP "+str(exc.code)) from exc
    if not isinstance(document,dict) or document.get("success") is not True:
        raise ValueError("V2 schedule did not report explicit success")
    items=document.get("events")
    if not isinstance(items,list):
        child=document.get("data")
        items=child.get("events") if isinstance(child,dict) else None
    if not isinstance(items,list):
        raise ValueError("Unexpected V2 football schedule schema")
    return items

def collect(start,end,*,key,token,root=ROOT,limit=1,fetcher=fetch_schedule):
    if end<start or end>=datetime.now(timezone.utc).date():
        raise ValueError("Dates must be completed UTC days")
    if not 1<=limit<=5:raise ValueError("Maximum 1..5 new daily V2 requests")
    root=Path(root)
    candidates=dates(start,end)
    for day in candidates:
        existing=path_for(day,root)
        if existing.exists():
            day_data(existing,key,day)
    pending=[day for day in candidates if not path_for(day,root).exists()]
    failures=[]
    saved=0
    for day in pending[:limit]:
        try:
            rows=fetcher(day,token=token)
            accepted={}
            reasons=Counter()
            for row in rows:
                m=v2_fixture(row,day)
                if m is None:
                    reasons["not_verified_football_ft"]+=1
                    continue
                mid=m["id"]
                if mid in accepted and accepted[mid]!=m:
                    raise ValueError("Conflicting V2 football fixture ID")
                accepted[mid]=m
            if not accepted:
                raise RuntimeError("No source-verified finished football matches")
            snapshot={
                "day":str(day),"verified":True,"source_endpoint":BASE+str(day),
                "source_schema":VERSION,"captured_at":datetime.now(timezone.utc).isoformat(),
                "raw_count":len(rows),"certified_football_count":len(accepted),
                "skips":dict(reasons),"matches":list(accepted.values()),
            }
            atomic_bytes(path_for(day,root),seal(snapshot,key,logical_for_day(day)))
            saved+=1
            print("V2_CERTIFIED_ENCRYPTED_DAY",day,"games",len(accepted),flush=True)
        except Exception as exc:
            # Avoid wasting more API calls after the first unsupported date.
            failures.append({"day":str(day),"reason":type(exc).__name__+": "+str(exc)[:90]})
            print("V2_DAY_NOT_CERTIFIED",day,type(exc).__name__,flush=True)
            break
    catalog=rebuild_manifest(start,end,key=key,root=root)
    _,missing,_=load_days(start,end,key=key,root=root,allow_missing=True)
    return {
        "status":"COMPLETE" if not missing else "INCOMPLETE",
        "new_days_saved":saved,"available_window_days":len(candidates)-len(missing),
        "missing_window_days":len(missing),
        "total_catalog_days":catalog["days"],
        "failures":failures,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2026-09-20")
    p.add_argument("--end",default="2026-09-20")
    p.add_argument("--limit",type=int,default=1)
    args=p.parse_args()
    token=os.environ.get("SPORTDATA_API_KEY_2","").strip()
    if not token:raise SystemExit("V2 provider credential SPORTDATA_API_KEY_2 missing")
    status=collect(date.fromisoformat(args.start),date.fromisoformat(args.end),
                   key=key_from_environment(),token=token,limit=args.limit)
    print("ENCRYPTED_V2_RESEARCH_STATUS",json.dumps(status),flush=True)
    if status["new_days_saved"]==0 and status["available_window_days"]==0:
        raise SystemExit(1)
    if status["status"]!="COMPLETE":
        raise SystemExit(2)

if __name__=="__main__":main()
