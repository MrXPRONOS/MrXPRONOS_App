#!/usr/bin/env python3
"""Strict native BSD event identity proof against independent CC0 calendars.

THIS IS AN AUDIT, NOT a betting bridge or automatic publication permission.
Exact league and side names + independent calendar corroboration + +/-15m
kickoff + globally unique 1:1 source-native relation are mandatory.
No fuzzy aliases, no native bookmaker quote lookups, no outputs with IDs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
if str(ROOT/"bsd") not in sys.path:sys.path.insert(0,str(ROOT/"bsd"))

from scripts.football_cc0_calendar_verification import download_schedules,corroborate
from scripts.football_history_shadow import canonical_team
from scripts.football_history_features import competition
from scripts.football_match_source_router import aware_time

MAX_DELTA_SECONDS=15*60
MAX_BSD_REQUESTS=12
ALLOWED_NATIVE_STATUSES=frozenset(("upcoming","notstarted"))

def positive_native_id(value):
    if type(value) is int:
        return value if 0<value<7_000_000_000_000_000 else None
    if isinstance(value,str) and value.isascii() and value.isdecimal() and value[0]!="0":
        number=int(value)
        return number if 0<number<7_000_000_000_000_000 else None
    return None

def team_name(event,side):
    value=event.get(side+"_team")
    return value.get("name") if isinstance(value,dict) else value

def native_key(event):
    if not isinstance(event,dict):
        return None
    bid=positive_native_id(event.get("id"))
    lid=positive_native_id(event.get("league_id"))
    hid=positive_native_id(event.get("home_team_id") or
        ((event.get("home_team") or {}).get("id") if isinstance(event.get("home_team"),dict) else None))
    aid=positive_native_id(event.get("away_team_id") or
        ((event.get("away_team") or {}).get("id") if isinstance(event.get("away_team"),dict) else None))
    home=canonical_team(str(team_name(event,"home") or ""))
    away=canonical_team(str(team_name(event,"away") or ""))
    league=competition(str(event.get("league_name") or ""))
    stamp=aware_time(event.get("event_date"))
    if (not all((bid,lid,hid,aid,home,away,league,stamp))
        or hid==aid or home==away or str(event.get("status") or "").lower() not in ALLOWED_NATIVE_STATUSES):
        return None
    return bid,(league,home,away,stamp)

def prove(external:list[dict], native:list[dict], *, at:datetime)->dict:
    if at.tzinfo is None:
        raise ValueError("Timezone-aware current time required")
    at=at.astimezone(timezone.utc)
    external_ok=[]
    rejected=Counter()
    for row in external:
        if not isinstance(row,dict) or row.get("_schedule_verified_by")!="openfootball_cc0" or row.get("league_verified") is not True:
            rejected["external_not_independently_cc0_verified"]+=1
            continue
        if row.get("ambiguous_match") or row.get("league_conflict") or row.get("scores_conflict") or row.get("status")!="prematch":
            rejected["external_ambiguous_or_not_prematch"]+=1
            continue
        leagues={competition(str(x)) for x in row.get("league_labels") or [] if competition(str(x))}
        start=aware_time(row.get("kickoff_utc"))
        home=canonical_team(str(row.get("home_team") or ""))
        away=canonical_team(str(row.get("away_team") or ""))
        if len(leagues)!=1 or not start or start<=at or not home or not away or home==away:
            rejected["external_invalid_identity_or_kickoff"]+=1
            continue
        external_ok.append((next(iter(leagues)),home,away,start))
    natives=defaultdict(list)
    invalid_native=0
    for row in native:
        key=native_key(row)
        if key is None:
            invalid_native+=1
            continue
        ident,attributes=key
        if attributes[3]<=at:
            rejected["native_not_future"]+=1
            continue
        natives[ident].append(attributes)
    unique_native={key:attributes[0] for key,attributes in natives.items()
                   if len(attributes)==1}
    rejected["duplicated_native_id"]+=sum(len(rows) for rows in natives.values() if len(rows)>1)
    edges=defaultdict(set)
    per_native=defaultdict(set)
    for i,external_key in enumerate(external_ok):
        for ident,native_key_value in unique_native.items():
            if external_key[:3]!=native_key_value[:3]:
                continue
            delta=abs((external_key[3]-native_key_value[3]).total_seconds())
            if delta>MAX_DELTA_SECONDS:
                rejected["same_identity_outside_kickoff_window"]+=1
                continue
            edges[i].add(ident)
            per_native[ident].add(i)
    confirmed=[(i,ident) for i,ids in edges.items() for ident in ids
               if len(ids)==1 and len(per_native[ident])==1]
    rejected["external_ambiguous_native_matches"]+=sum(len(ids)>1 for ids in edges.values())
    rejected["native_ambiguous_external_matches"]+=sum(len(v)>1 for v in per_native.values())
    unmatched=len(external_ok)-len({i for i,_ in confirmed})
    return {
        "scope":"read_only_identity_evidence",
        "external_total":len(external),
        "external_cc0_verified":len(external_ok),
        "native_total":len(native),
        "native_unique_eligible":len(unique_native),
        "native_invalid_records":invalid_native,
        "one_to_one_native_event_links":len(confirmed),
        "unmatched_or_ambiguous_external":unmatched,
        "identity_evidence":"exact_league_home_away_utc_kickoff_15m_unique",
        "native_event_ids_exported":False,
        "native_bookmaker_prices_fetched":False,
        "actual_bookmaker_quote_or_market_verified":False,
        "original_production_publication_enabled":False,
        "research_only":True,
        "no_data_json_modified":True,
        "rejected_reasons":dict(sorted(rejected.items())),
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--public-fixtures",required=True)
    parser.add_argument("--report",required=True)
    parser.add_argument("--days",type=int,default=2)
    args=parser.parse_args()
    if not 1<=args.days<=2:
        parser.error("BSD audit is limited to 2 calendar days")
    if not os.getenv("BSD_API_KEY"):
        parser.error("BSD_API_KEY missing; do not substitute synthetic event IDs")
    destination=Path(args.report).resolve()
    if destination==(ROOT/"data.json").resolve():
        parser.error("Production file is forbidden")
    import requests
    from bsd_api import BSDClient
    public=json.loads(Path(args.public_fixtures).read_text(encoding="utf-8"))
    if not isinstance(public,list):
        parser.error("Public fixture union must be an array")
    clock=datetime.now(timezone.utc)
    calendars,health=download_schedules(requests.Session(),season="2026-27")
    if health["files_ok"]!=8:
        raise RuntimeError("Incomplete independent CC0 calendar verification")
    verified,coverage=corroborate(public,calendars,as_of=clock)
    # Disable BSDClient free-source enrichment to avoid unrelated providers
    # and ensure all IDs originate exclusively from authentic BSD events.
    os.environ["FOOTBALL_MULTI_SOURCE"]="0"
    client=BSDClient(max_requests=MAX_BSD_REQUESTS,timeout=15,max_retries=1)
    native=[]
    for n in range(args.days):
        day=(clock+timedelta(days=n+1)).date()
        page=client.list_events(day,day,max_pages=4,ttl=0)
        if not page.complete:
            raise RuntimeError("BSD fixture pagination incomplete (do not infer missing matches)")
        native.extend(page.events)
    result=prove(verified,native,at=clock)
    result.update({
        "bsd_http_calls":client.requests_made,
        "bsd_max_http_requests":MAX_BSD_REQUESTS,
        "calendar_files_verified":health["files_ok"],
        "independent_cc0_calendar_confirmed":coverage["schedule_matches_confirmed"],
    })
    assert client.requests_made<=MAX_BSD_REQUESTS
    assert result["one_to_one_native_event_links"]<=coverage["schedule_matches_confirmed"]
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STRICT_BSD_NATIVE_IDENTITY_AUDIT",json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    main()
