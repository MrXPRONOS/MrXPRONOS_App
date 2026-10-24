#!/usr/bin/env python3
"""One-shot 2024 calendar-year backfill from CC0 OpenFootball football.json.

Source: https://github.com/openfootball/football.json (public domain CC0).
The complete CALENDAR YEAR is queried over the 2023-24 and 2024-25 season
files, but coverage is limited to the competitions available upstream.
No timestamp or global team identity is invented from date-only match rows.

The archive is separate from SportsAPI Pro's certified V1/V2 day snapshots.
No Supabase, Neon, API key usage or plaintext Git commits.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date,datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

from single_ml_v2_git import ROOT, key_from_environment, seal, open_sealed, atomic_bytes

YEAR=2024
SEASON_CODES={
    "2023-24":("at.1","de.1","de.2","en.1","en.2","es.1","fr.1","it.1","nl.1","pt.1"),
    "2024-25":("at.1","at.2","au.1","be.1","de.1","de.2","dz.1","eg.1",
        "en.1","en.2","en.3","en.4","es.1","es.2","fr.1","fr.2",
        "gr.1","it.1","it.2","ma.1","mx.1","nl.1","pt.1","sco.1",
        "tr.1","uefa.cl"),
}
SOURCE="https://raw.githubusercontent.com/openfootball/football.json/master/"
OUTPUT=ROOT/"openfootball"/"2024.enc"
SCHEMA="openfootball_cc0_calendar_2024_v1"
MIN_EXPECTED=700
MIN_DIVISIONS=8
MIN_ACTIVE_MONTHS=9

def fetch_source(season,code,*,opener=urllib.request.urlopen):
    if season not in SEASON_CODES or code not in SEASON_CODES[season]:
        raise ValueError("Unapproved OpenFootball season/division")
    url=SOURCE+season+"/"+code+".json"
    req=urllib.request.Request(url,headers={"Accept":"application/json",
                  "User-Agent":"MrXPRONOS-CC0-Research-2024"})
    # No secrets sent. 1 optional retry on transient network failure.
    last=None
    for attempt in range(2):
        try:
            with opener(req,timeout=25) as stream:
                raw=stream.read(3*1024*1024+1)
            if len(raw)>3*1024*1024:
                raise ValueError("Oversized OpenFootball season data")
            return json.loads(raw),sha256(raw).hexdigest(),url
        except (urllib.error.URLError,TimeoutError,OSError) as exc:
            last=exc
            if attempt==0:time.sleep(.3)
    raise RuntimeError("OpenFootball season unavailable: "+season+"/"+code+
                       " ("+type(last).__name__+")")

def parse_match(raw,season,code,league):
    if not isinstance(raw,dict):return None
    day=raw.get("date")
    try:
        if not isinstance(day,str) or len(day)!=10:return None
        parsed=date.fromisoformat(day)
    except ValueError:return None
    if parsed.year!=YEAR:return None
    home=raw.get("team1")
    away=raw.get("team2")
    score=raw.get("score")
    ft=score.get("ft") if isinstance(score,dict) else None
    if not (isinstance(home,str) and isinstance(away,str) and home.strip()
            and away.strip() and home!=away and isinstance(ft,list) and len(ft)==2):
        return None
    if any(type(x) is not int or x<0 or x>10 for x in ft):return None
    hh=home.strip()
    aa=away.strip()
    raw_time=raw.get("time")
    local_time=raw_time if isinstance(raw_time,str) and re.fullmatch(r"[0-2][0-9]:[0-5][0-9]",raw_time) else None
    logical=season+"|"+code+"|"+day+"|"+hh+"|"+aa
    ident="of2024:"+sha256(logical.encode("utf8")).hexdigest()[:24]
    # Matches are GROUPED BY DATE in backtests. Local fixture times are
    # explicitly not converted into fictional UTC timestamps.
    return {"id":ident,"sportId":1,"date":day,
        "home_team":hh,"away_team":aa,"competition":league,
        "home_score":ft[0],"away_score":ft[1],"status_group":4,
        "is_finished":True,"source":"openfootball_football_json_cc0",
        "source_season":season,"source_division":code,
        "source_date_precision":"calendar_date_only_no_utc",
        "source_local_time_unverified_tz":local_time,
        "source_home_team_id":None,"source_away_team_id":None,
        "source_competition_id":None}

def build(*,fetcher=fetch_source):
    matches={}
    failures=[]
    file_stats=[]
    divisions=set()
    active_months=set()
    for season,codes in SEASON_CODES.items():
        for code in codes:
            try:
                data,digest,url=fetcher(season,code)
                if not isinstance(data,dict) or not isinstance(data.get("matches"),list):
                    raise ValueError("Unexpected OpenFootball match schema")
                league=code  # Stable between 2023/24 and 2024/25; no invented team IDs
                accepted=0
                for raw in data["matches"]:
                    row=parse_match(raw,season,code,league)
                    if row is None:continue
                    key=row["id"]
                    if key in matches and matches[key]!=row:
                        raise ValueError("Conflicting duplicated upstream football fixture")
                    if key not in matches:
                        matches[key]=row
                        accepted+=1
                        divisions.add(code)
                        active_months.add(row["date"][:7])
                file_stats.append({"season":season,"division":code,
                    "source_sha256":digest,"source_url":url,"2024_matches":accepted})
            except Exception as exc:
                failures.append({"season":season,"division":code,
                                 "reason":type(exc).__name__})
    items=sorted(matches.values(),key=lambda r:(r["date"],r["competition"],r["id"]))
    days=Counter(r["date"] for r in items)
    months=Counter(r["date"][:7] for r in items)
    audit={
        "source":"openfootball/football.json","license":"CC0/public-domain",
        "source_project":"https://github.com/openfootball/football.json",
        "calendar_start":"2024-01-01","calendar_end":"2024-12-31",
        "calendar_days":366,"match_days":len(days),
        "days_with_no_observed_fixture":366-len(days),
        "matches":len(items),"divisions":len(divisions),
        "division_codes":sorted(divisions),
        "by_month":{f"2024-{m:02d}":months.get(f"2024-{m:02d}",0)
                    for m in range(1,13)},
        "season_files_expected":sum(len(codes) for codes in SEASON_CODES.values()),
        "season_files_checked":len(file_stats),"season_files_failed":len(failures),
        "files":file_stats,"failures":failures,
        "scope_limit":"NOT the full world 2024 match universe; only source-published leagues",
        "kickoff_provenance":"DATE ONLY, no verified UTC clock or prekickoff odds",
        "no_xg_invented":True,
        "no_source_team_id_invented":True,
        "independent_of_sportsapipro_archive":True,
    }
    if failures:
        raise RuntimeError("Incomplete 2024 upstream league-source catalogue: "+json.dumps(failures))
    if len(items)<MIN_EXPECTED or len(divisions)<MIN_DIVISIONS or len(active_months)<MIN_ACTIVE_MONTHS:
        raise RuntimeError("CC0 2024 dataset too sparse; refuse certified annual archive: "+
            json.dumps({"matches":len(items),"divisions":len(divisions),
                        "active_months":len(active_months),"failed_sources":len(failures)}))
    # Some off-season calendar months can legitimately contain no fixtures
    # in the selected leagues; keep that gap explicit in the audited report.
    # Do not claim fully covered league seasons if an upstream file failed.
    return {"schema":SCHEMA,"year":YEAR,"created_at":datetime.now(timezone.utc).isoformat(),
            "audit":audit,"matches":items}

def store(result,key,*,path=OUTPUT):
    path=Path(path)
    blob=seal(result,key,"openfootball-cc0-calendar-2024")
    if path.exists():
        existing=open_sealed(path.read_bytes(),key,"openfootball-cc0-calendar-2024")
        if existing.get("schema")!=SCHEMA or existing.get("year")!=YEAR:
            raise ValueError("Unexpected existing year-2024 ciphertext")
        if existing.get("audit",{}).get("matches")!=result["audit"]["matches"]:
            raise RuntimeError("Immutable 2024 archive has different match count; manual version required")
        return False
    atomic_bytes(path,blob)
    verified=open_sealed(path.read_bytes(),key,"openfootball-cc0-calendar-2024")
    if verified["audit"]!=result["audit"] or len(verified["matches"])!=result["audit"]["matches"]:
        raise RuntimeError("AES-GCM archive integrity verification failed")
    return True

def export(key,*,path=OUTPUT,destination="/tmp/mrx_openfootball_2024.json"):
    source=Path(path)
    data=open_sealed(source.read_bytes(),key,"openfootball-cc0-calendar-2024")
    target=Path(destination)
    if not str(target.resolve()).startswith("/tmp/"):
        raise ValueError("Plaintext export allowed ONLY in /tmp")
    if target.exists():raise FileExistsError("Refusing plaintext overwrite")
    target.write_text(json.dumps(data["matches"],ensure_ascii=False),encoding="utf8")
    target.chmod(0o600)
    return len(data["matches"])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["collect","export"])
    p.add_argument("--output",default="/tmp/mrx_openfootball_2024.json")
    args=p.parse_args()
    key=key_from_environment()
    if args.action=="export":
        count=export(key,destination=args.output)
        print("OPENFOOTBALL_2024_TEMPORARY_EXPORT",count)
        return
    result=build()
    added=store(result,key)
    report=result["audit"]
    print("OPENFOOTBALL_2024_RESULT",json.dumps({
        "calendar_days":report["calendar_days"],
        "match_days":report["match_days"],
        "matches":report["matches"],
        "divisions":report["divisions"],
        "by_month":report["by_month"],
        "source_files_checked":report["season_files_checked"],
        "source_files_failed":report["season_files_failed"],
        "encrypted_saved":added,
        "scope":"openfootball_cc0_leagues_only_not_worldwide",
    },ensure_ascii=False))

if __name__=="__main__":
    main()
