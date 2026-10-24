#!/usr/bin/env python3
"""Build a CERTIFIED football-only research archive from SportData; never alter production cache.

Each UTC day has a durable source snapshot so a quota-limited 2024-present backfill
can resume safely. Unknown sport IDs, unfinished games and contradictory IDs fail closed.
A complete output is published ONLY after every day has an API-verified snapshot.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sportdata_api import fetch_games, get_api_keys

def utc_dt(value):
    if isinstance(value,(int,float)) or (isinstance(value,str) and value.strip().isdigit()):
        val=float(value)
        if val>1e11: val/=1000
        return datetime.fromtimestamp(val,timezone.utc)
    if not value: return None
    try:
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if dt.tzinfo is None: return None
        return dt.astimezone(timezone.utc)
    except (ValueError,TypeError,OverflowError): return None

def normalize(raw, requested_day):
    if not isinstance(raw,dict) or str(raw.get("sportId"))!="1":
        return None,"not_certified_football"
    start=utc_dt(raw.get("startTime"))
    if start is None or start.date()!=requested_day:
        return None,"wrong_or_missing_kickoff"
    home=raw.get("homeCompetitor") or {}
    away=raw.get("awayCompetitor") or {}
    if not isinstance(home,dict) or not isinstance(away,dict):
        return None,"invalid_competitors"
    try:
        hg,ag=home.get("score"),away.get("score")
        if isinstance(hg,bool) or isinstance(ag,bool): raise ValueError()
        if hg is None or ag is None or int(hg)!=float(hg) or int(ag)!=float(ag): raise ValueError()
        hg,ag=int(hg),int(ag)
    except (ValueError,TypeError,OverflowError):
        return None,"invalid_score"
    if str(raw.get("statusGroup"))!="4":
        return None,"not_finished"
    if min(hg,ag)<0 or max(hg,ag)>10:
        return None,"out_of_range"
    key=str(raw.get("id") or "").strip()
    league=str(raw.get("competitionDisplayName") or "").strip()
    h=str(home.get("name") or "").strip()
    a=str(away.get("name") or "").strip()
    if not (key and league and h and a) or h==a:
        return None,"missing_identity"
    return {
        "id":key,"sportId":1,"start_time":start.isoformat().replace("+00:00","Z"),
        "home_team":h,"away_team":a,"competition":league,
        "home_score":hg,"away_score":ag,"status_group":4,"is_finished":True,
        "source":"sportsapipro_v1_allscores","source_match_id":key,
        "source_competition_id":raw.get("competitionId"),
    },None

def atomic_json(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")
    os.replace(temp,path)

def dates(start,end):
    n=(end-start).days
    return [start+timedelta(days=i) for i in range(n+1)]

def day_snapshot(day,response):
    if not response.ok:
        raise RuntimeError("SportData retrieval failed: "+str(response.reason)[:160])
    accepted={}
    skips=Counter()
    for raw in response.games:
        item,reason=normalize(raw,day)
        if reason:
            skips[reason]+=1
            continue
        old=accepted.get(item["id"])
        if old is not None and old!=item:
            raise ValueError("Contradictory football match ID "+item["id"])
        accepted[item["id"]]=item
    return {
        "day":day.isoformat(),"verified":True,
        "source_endpoint":response.endpoint,
        "captured_at":datetime.now(timezone.utc).isoformat(),
        "raw_count":len(response.games),"certified_football_count":len(accepted),
        "skips":dict(skips),"matches":list(accepted.values())
    }

def build_archive(checkpoints,start,end,output,audit_path,*,max_days=0,fetcher=fetch_games):
    if not get_api_keys() and fetcher is fetch_games:
        raise RuntimeError("No SPORTDATA_API_KEY configured; no fake football archive will be generated")
    checkpoints=Path(checkpoints)
    all_days=dates(start,end)
    failed=[]
    attempts=0
    for day in all_days:
        path=checkpoints/(day.isoformat()+".json")
        if path.is_file():
            try:
                cached=json.loads(path.read_text(encoding="utf8"))
                if cached.get("day")==str(day) and cached.get("verified") is True:
                    continue
            except (ValueError,OSError): pass
        if max_days and attempts>=max_days:
            break
        attempts+=1
        try:
            snapshot=day_snapshot(day,fetcher(day,day,timeout=45,show_odds=False))
            atomic_json(path,snapshot)
            print("FOOTBALL_DAY",str(day),"raw",snapshot["raw_count"],
                  "football",snapshot["certified_football_count"],flush=True)
        except Exception as exc:
            failed.append({"day":str(day),"error":str(exc)[:180]})
            print("FOOTBALL_DAY_FAILED",str(day),str(exc)[:160],flush=True)
    collected={}
    missing=[]
    covered=[]
    zero=[]
    for day in all_days:
        path=checkpoints/(day.isoformat()+".json")
        try:
            doc=json.loads(path.read_text(encoding="utf8"))
            if doc["day"]!=str(day) or doc.get("verified") is not True:
                raise ValueError("uncertified snapshot")
            covered.append(str(day))
            if doc["certified_football_count"]==0: zero.append(str(day))
            for row in doc["matches"]:
                if str(row.get("sportId"))!="1" or row["start_time"][:10]!=str(day):
                    raise ValueError("corrupt sport or day in checkpoint")
                old=collected.get(row["id"])
                if old and old!=row:
                    raise ValueError("Conflicting match across dates: "+row["id"])
                collected[row["id"]]=row
        except (OSError,ValueError,KeyError,TypeError) as exc:
            missing.append(str(day))
    audit={
        "start":str(start),"end":str(end),
        "total_requested_days":len(all_days),"certified_days":len(covered),
        "missing_days":missing,"failed_requests":failed,"zero_football_days":zero,
        "certified_finished_matches":len(collected),
        "complete":not missing,
        "source":"sportsapipro_v1_allscores",
        "old_production_cache_reused":False,
    }
    if not missing:
        records=sorted(collected.values(),key=lambda v:(v["start_time"],v["id"]))
        atomic_json(output,records)
        audit["output"]=str(output)
        audit["archive_sha256"]=hashlib.sha256(Path(output).read_bytes()).hexdigest()
    else:
        audit["output"]="NOT_PUBLISHED_INCOMPLETE"
    atomic_json(audit_path,audit)
    print("FOOTBALL_ARCHIVE_AUDIT",json.dumps({k:v for k,v in audit.items()
          if k not in ("missing_days","zero_football_days")},ensure_ascii=False),flush=True)
    return audit

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",default="2024-01-01")
    p.add_argument("--end",default=None,help="UTC date, default yesterday")
    p.add_argument("--checkpoints",default="research/private/football_checkpoints")
    p.add_argument("--output",default="research/private/football_history.json")
    p.add_argument("--audit",default="research/private/football_audit.json")
    p.add_argument("--max-days",type=int,default=0,
                   help="Max newly queried dates in this run; 0 unlimited")
    a=p.parse_args()
    end=date.fromisoformat(a.end) if a.end else datetime.now(timezone.utc).date()-timedelta(days=1)
    start=date.fromisoformat(a.start)
    if end<start or end>=datetime.now(timezone.utc).date():
        p.error("Require start <= end < today's UTC date")
    status=build_archive(a.checkpoints,start,end,a.output,a.audit,max_days=a.max_days)
    if not status["complete"]:
        raise SystemExit(2)

if __name__=="__main__":main()
