#!/usr/bin/env python3
"""As-of safe xG provenance enrichment for certified football archive.

Supabase API original late-match snapshots are genuine OBSERVED live expected-goals,
but not certified final xG. Never rename these final xG or use a target match's xG.
A snapshot becomes usable only after its actual recorded updated_at instant.
Unmatched and ambiguous fixture mappings are left without xG.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from single_ml_v2_data import utc_dt, atomic_json

def norm(s):
    s=unicodedata.normalize("NFKD",str(s or "")).encode("ascii","ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+","",s)

def xg_num(v):
    try:
        if isinstance(v,bool): return None
        f=float(v)
        if 0<=f<=10 and f==f:return f
    except (ValueError,TypeError,OverflowError):pass
    return None

def validated_snapshots(rows,*,asof):
    indexed=defaultdict(list)
    audit=Counter()
    for row in rows:
        if row.get("source_name")!="api_original":
            audit["other_source"]+=1;continue
        k=utc_dt(row.get("event_date"))
        updated=utc_dt(row.get("updated_at"))
        try:minute=int(row.get("minute"))
        except (ValueError,TypeError):minute=-1
        v=row.get("stats_json") or {}
        if not isinstance(v,dict):continue
        h=xg_num((v.get("home") or {}).get("expected_goals"))
        a=xg_num((v.get("away") or {}).get("expected_goals"))
        if not k or not updated or updated<=k or updated>asof or not 90<=minute<=135 or h is None or a is None:
            audit["invalid_or_future"]+=1;continue
        key=(norm(row.get("home_team")),norm(row.get("away_team")),k.date())
        if not all(key):audit["unnamed"]+=1;continue
        indexed[key].append({"kickoff":k,"updated":updated,"h":h,"a":a,
                             "minute":minute,"provider":"supabase_live_stats_sources_api_original",
                             "snapshot_id":str(row.get("canonical_match_id") or "")})
        audit["valid"]+=1
    return indexed,audit

def enrich(football_rows,stats_rows,*,asof):
    idx,audit=validated_snapshots(stats_rows,asof=asof)
    out=[]
    for src in football_rows:
        row=dict(src)
        # Clear unverifiable xG fields; never inherit an unidentified external value.
        for key in ("home_xg","away_xg","xg_source","xg_observed_at",
                    "xg_quality","xg_kickoff","xg_usable_after"):row.pop(key,None)
        if str(row.get("sportId"))!="1":
            raise ValueError("Non-football input in certified archive")
        k=utc_dt(row.get("start_time"))
        if k is None:raise ValueError("Missing kickoff in certified archive")
        key=(norm(row["home_team"]),norm(row["away_team"]),k.date())
        c=[v for v in idx.get(key,[]) if abs((v["kickoff"]-k).total_seconds())<=5400]
        if not c:
            audit["no_xg_match"]+=1;out.append(row);continue
        fixtures={(v["snapshot_id"],v["kickoff"]) for v in c}
        if len(fixtures)>1:
            audit["ambiguous_fixture"]+=1;out.append(row);continue
        # Pick the latest captured snapshot from the same fixture.
        c.sort(key=lambda v:(v["updated"],v["minute"]))
        chosen=c[-1]
        if chosen["updated"]<k:
            raise AssertionError("Impossible pre-kickoff late snapshot")
        row["home_xg"]=chosen["h"]
        row["away_xg"]=chosen["a"]
        row["xg_source"]=chosen["provider"]
        row["xg_observed_at"]=chosen["updated"].isoformat()
        row["xg_usable_after"]=chosen["updated"].isoformat()
        row["xg_quality"]="observed_late_match_90plus_provisional"
        row["xg_kickoff"]=k.isoformat()
        audit["enriched"]+=1
        out.append(row)
    return out,dict(audit)

def retrieve_supabase(*,base_url,token,end,asof,max_pages=25):
    if not token:raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is absent")
    url=base_url.rstrip("/")+"/rest/v1/live_stats_sources"
    headers={"apikey":token,"Authorization":"Bearer "+token,"Accept":"application/json"}
    for page in range(max_pages):
        params={"select":"canonical_match_id,home_team,away_team,event_date,minute,stats_json,updated_at,source_name",
                "source_name":"eq.api_original",
                "minute":"gte.90",
                "event_date":"lte."+end+"T23:59:59Z",
                "updated_at":"lte."+asof.isoformat(),
                "order":"event_date.asc,canonical_match_id.asc,updated_at.asc",
                "limit":"1000","offset":str(page*1000)}
        r=requests.get(url,headers=headers,params=params,timeout=45)
        r.raise_for_status()
        data=r.json()
        if not isinstance(data,list):raise RuntimeError("Invalid Supabase JSON response")
        yield from data
        if len(data)<1000:return
    raise RuntimeError("Pagination cap reached: do not silently truncate xG source")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--football",default="research/private/football_history.json")
    p.add_argument("--output",default="research/private/football_with_xg.json")
    p.add_argument("--audit",default="research/private/xg_audit.json")
    p.add_argument("--snapshots-json",default=None,
                   help="Offline snapshot with recorded timestamps; avoids network access")
    p.add_argument("--asof",default=None,
                   help="UTC cutoff timestamp, defaults to present")
    a=p.parse_args()
    asof=utc_dt(a.asof) if a.asof else datetime.now(timezone.utc)
    if asof is None or asof>datetime.now(timezone.utc)+timedelta(seconds=1):
        raise ValueError("Invalid future as-of")
    football=json.loads(Path(a.football).read_text(encoding="utf8"))
    if a.snapshots_json:
        snapshots=json.loads(Path(a.snapshots_json).read_text(encoding="utf8"))
    else:
        snapshots=list(retrieve_supabase(base_url=os.environ.get("SUPABASE_URL",""),
             token=os.environ.get("SUPABASE_SERVICE_ROLE_KEY",""),end=max(
             r["start_time"][:10] for r in football),asof=asof))
    result,audit=enrich(football,snapshots,asof=asof)
    audit.update({"source_rows":len(snapshots),"football_rows":len(result),
                  "asof":asof.isoformat(),"source":"supabase_live_stats_sources_api_original",
                  "xg_certified_final":False,"xg_type":"provisional_observed_90plus"})
    atomic_json(a.output,result)
    atomic_json(a.audit,audit)
    print("XG_ENRICH_AUDIT",json.dumps(audit,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
