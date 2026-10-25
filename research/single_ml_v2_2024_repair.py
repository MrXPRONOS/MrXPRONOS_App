#!/usr/bin/env python3
"""Repair ONLY missing SportScore 2024 day fetches, save encrypted additive patch.

The original 12 monthly 2024 encrypted snapshots are immutable. Provider's
200-match/day ceiling is NOT paginated by page or offset (verified empirically).
BSD completed pagination covers independent source data on capped dates.
"""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timezone
from pathlib import Path
import json,os,time,requests
from single_ml_v2_git import ROOT,key_from_environment,open_sealed,seal,atomic_bytes
from single_ml_v2_bsd_sportscore_2024 import SCHEMA,parse_sportscore,SCORE,SPORTSCORE_CAP,http_json

def aad_for_year(year):
    if year not in (2024,2025,2026):raise ValueError("Unsupported year")
    return f"bsd-sportscore-{year}-repaired-days-v1"

AAD=aad_for_year(2024)
PATCH=ROOT/"bsd_sportscore"/"2024_repair.enc"

def target_dates(*,root=ROOT,key,year=2024,through=None):
    if year==2026 and through is None:
        raise ValueError("Require completed cutoff for partial 2026 repair")
    if isinstance(through,str):through=date.fromisoformat(through)
    if through is not None:
        if through.year!=year or through>=datetime.now(timezone.utc).date():
            raise ValueError("Repair cutoff must not include current or future UTC day")
    dates=set()
    for month in range(1,(through.month if through is not None else 12)+1):
        p=Path(root)/"bsd_sportscore"/str(year)/f"{month:02d}.enc"
        document=open_sealed(p.read_bytes(),key,
                            "bsd-sportscore-"+str(year)+"-month:"+str(month))
        if document.get("schema")!=f"bsd_sportscore_{year}_private_verified_v1" or document.get("month")!=month:
            raise ValueError("Invalid base encrypted monthly snapshot")
        failed=document.get("audit",{}).get("sportscore",{}).get("failed_dates",[])
        if not isinstance(failed,list):
            raise ValueError("Missing SportScore original failed-date report")
        for row in failed:
            day=date.fromisoformat(row["date"])
            if day.year!=year or day.month!=month:
                raise ValueError("Repair request outside verified failure list")
            dates.add(str(day))
    return sorted(dates)

def repair(*,root=ROOT,key=None,retries=3,session=None,year=2024,through=None):
    associated_data=aad_for_year(year)
    root=Path(root)
    key=key or key_from_environment()
    failed=target_dates(root=root,key=key,year=year,through=through)
    if not failed:raise RuntimeError("No failed SportScore day to repair for "+str(year))
    if retries not in (1,2,3):
        raise ValueError("Retry cap must be 1..3")
    path=root/"bsd_sportscore"/f"{year}_repair.enc"
    if path.exists():
        prior=open_sealed(path.read_bytes(),key,associated_data)
        if prior.get("original_failed_dates")!=failed:
            raise RuntimeError("Existing patch does not match original failure audit")
        return prior["audit"],False
    owned=session is None
    session=session or requests.Session()
    seen={}
    errors={}
    at_cap=[]
    recovered=[]
    counter=Counter()
    try:
        for daystring in failed:
            day=date.fromisoformat(daystring)
            for attempt in range(retries):
                try:
                    payload=http_json(session,SCORE,{"Accept":"application/json"},
                        {"sport":"football","date":daystring,
                         "status":"finished","limit":SPORTSCORE_CAP},
                         counter,sleep=.15)
                    if not isinstance(payload,dict) or not isinstance(payload.get("matches"),list):
                        raise ValueError("Malformed SportScore daily response")
                    raw=payload["matches"]
                    if len(raw)>=SPORTSCORE_CAP or (
                        type(payload.get("count")) is int and
                        payload["count"]>=SPORTSCORE_CAP):
                        at_cap.append(daystring)
                    current={}
                    for item in raw:
                        game=parse_sportscore(item,day)
                        if game is None:continue
                        keyid=(daystring,game["id"])
                        if keyid in current and current[keyid]!=game:
                            raise ValueError("Conflicting repeated SportScore daily fixture")
                        current[keyid]=game
                    if not current:
                        raise RuntimeError("No certified completed football matches")
                    seen.update(current)
                    recovered.append(daystring)
                    break
                except (requests.RequestException,ValueError,RuntimeError) as e:
                    errors[daystring]=type(e).__name__
                    if "Hard HTTP request cap" in str(e):raise
                    if attempt+1<retries:time.sleep(.6*(attempt+1))
            if daystring in recovered:errors.pop(daystring,None)
    finally:
        if owned:session.close()
    audit={"original_failed_dates":len(failed),"recovered_dates":len(recovered),
        "unresolved_dates":sorted(errors),"unresolved_reason_types":errors,
        "recovered_at_200_cap":len(at_cap),
        "recovered_at_200_dates":at_cap,
        "additional_source_records":len(seen),
        "source_requests":counter["total"],
        "sportscore_daily_ceiling_unpaged":200,
        "not_globally_exhaustive":True}
    envelope={"schema":associated_data,"year":year,
        "original_failed_dates":failed,"created_at":datetime.now(timezone.utc).isoformat(),
        "audit":audit,"matches":list(seen.values())}
    atomic_bytes(path,seal(envelope,key,associated_data))
    verify=open_sealed(path.read_bytes(),key,associated_data)
    if verify["audit"]!=audit or verify["schema"]!=associated_data:
        raise RuntimeError("AES-GCM repair verification failure")
    return audit,True

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--year",type=int,default=2024,choices=(2024,2025,2026))
    ap.add_argument("--through",default=None)
    args=ap.parse_args()
    audit,_=repair(year=args.year,through=args.through)
    print("BSD_SPORTSCORE_YEAR_REPAIR",args.year,json.dumps(audit,ensure_ascii=False))
    if audit["unresolved_dates"]:raise SystemExit(2)
