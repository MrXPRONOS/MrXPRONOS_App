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
MAX_BSD_REQUESTS=24
MAX_ODDS_PROBE_EVENTS=8
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

def native_parts(event, *, official_leagues=None):
    """Interpret only documented native BSD identifiers, never research IDs."""
    if not isinstance(event,dict):
        return None,"not_object"
    lid_value=event.get("league_id")
    league_value=event.get("league")
    if lid_value is None and isinstance(league_value,dict):
        lid_value=league_value.get("id")
    home_info=event.get("home_team")
    away_info=event.get("away_team")
    hid_value=event.get("home_team_id")
    aid_value=event.get("away_team_id")
    if hid_value is None and isinstance(home_info,dict):
        hid_value=home_info.get("id")
    if aid_value is None and isinstance(away_info,dict):
        aid_value=away_info.get("id")
    bid=positive_native_id(event.get("id"))
    lid=positive_native_id(lid_value)
    hid=positive_native_id(hid_value)
    aid=positive_native_id(aid_value)
    if bid is None:return None,"missing_native_event_id"
    if lid is None:return None,"missing_native_competition_id"
    if hid is None or aid is None or hid==aid:return None,"missing_or_conflicting_team_ids"
    home=canonical_team(str(team_name(event,"home") or ""))
    away=canonical_team(str(team_name(event,"away") or ""))
    if not home or not away or home==away:
        return None,"missing_or_conflicting_team_names"
    league_raw=(event.get("league_name") or event.get("competition_name") or
                event.get("tournament_name") or
                (league_value.get("name") if isinstance(league_value,dict) else league_value))
    if not league_raw and official_leagues:
        league_raw=official_leagues.get(lid)
    league=competition(str(league_raw or ""))
    if not league:return None,"missing_native_competition_name"
    stamp=aware_time(event.get("event_date"))
    if stamp is None:return None,"missing_utc_kickoff"
    if str(event.get("status") or "").lower() not in ALLOWED_NATIVE_STATUSES:
        return None,"native_not_prematch"
    return (bid,(league,home,away,stamp)),None

def native_key(event):
    return native_parts(event)[0]

def prove(external:list[dict], native:list[dict], *, at:datetime, official_leagues=None, verified_id_sink=None, verified_pair_sink=None)->dict:
    if at.tzinfo is None:
        raise ValueError("Timezone-aware current time required")
    at=at.astimezone(timezone.utc)
    external_ok=[]
    external_ok_rows=[]
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
        external_ok_rows.append(row)
    natives=defaultdict(list)
    native_originals=defaultdict(list)
    invalid_native=0
    native_issues=Counter()
    for row in native:
        key,issue=native_parts(row,official_leagues=official_leagues)
        if key is None:
            invalid_native+=1
            native_issues[issue or "unclassified"]+=1
            continue
        ident,attributes=key
        if attributes[3]<=at:
            rejected["native_not_future"]+=1
            continue
        natives[ident].append(attributes)
        native_originals[ident].append(row)
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
    # The optional sink remains PROCESS-LOCAL ONLY. Never put IDs in a report,
    # log, artifact, Telegram message, site JSON or a data model identifier.
    if verified_id_sink is not None:
        verified_id_sink.extend(sorted({ident for _,ident in confirmed}))
    if verified_pair_sink is not None:
        for i,ident in sorted(confirmed):
            if len(native_originals.get(ident,[]))!=1:
                raise AssertionError("Native event ambiguity after crosswalk")
            verified_pair_sink.append((ident,external_ok_rows[i],native_originals[ident][0]))
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
        "native_invalid_breakdown":dict(sorted(native_issues.items())),
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

def candidate_official_league_ids(external, native, *, at):
    """Lookup IDs only after exact time+team match; no league guessed."""
    lids=set()
    for row in external:
        if not isinstance(row,dict) or row.get("_schedule_verified_by")!="openfootball_cc0" or row.get("league_verified") is not True:
            continue
        if row.get("status")!="prematch" or row.get("ambiguous_match") or row.get("league_conflict") or row.get("scores_conflict"):
            continue
        ext_home=canonical_team(str(row.get("home_team") or ""))
        ext_away=canonical_team(str(row.get("away_team") or ""))
        ext_time=aware_time(row.get("kickoff_utc"))
        if not ext_home or not ext_away or ext_home==ext_away or not ext_time or ext_time<=at:
            continue
        for official in native:
            if not isinstance(official,dict) or str(official.get("status") or "").lower() not in ALLOWED_NATIVE_STATUSES:
                continue
            ident=positive_native_id(official.get("id"))
            lid=positive_native_id(official.get("league_id") or
                ((official.get("league") or {}).get("id") if isinstance(official.get("league"),dict) else None))
            t=aware_time(official.get("event_date"))
            if not ident or not lid or not t or t<=at:
                continue
            if (canonical_team(str(team_name(official,"home") or ""))==ext_home
                and canonical_team(str(team_name(official,"away") or ""))==ext_away
                and abs((t-ext_time).total_seconds())<=MAX_DELTA_SECONDS):
                lids.add(lid)
    return sorted(lids)


def audit_official_consensus_quotes(client,native,linked_ids,league_names,*,at,verified_quotes_sink=None):
    """Proof of native market pricing, not proof of an executable bookmaker bet.

    Only confirmed official BSD event IDs are inspected; a consensus value
    is an aggregated indication and cannot supply a bookmaker ticket code.
    """
    from bsd_v2_odds import fetch_event_odds
    by_id=defaultdict(list)
    for row in native:
        key,reason=native_parts(row,official_leagues=league_names)
        if key is not None:
            ident,attributes=key
            by_id[ident].append(attributes)
    outcomes=Counter()
    audited=0
    # Prioritize the nearest authentic kickoffs, not arbitrary numeric IDs,
    # so the native publisher's genuine 48h window is sampled when available.
    prioritized=sorted(set(linked_ids),key=lambda ident:(
        by_id[ident][0][3] if len(by_id.get(ident,[]))==1
        else datetime.max.replace(tzinfo=timezone.utc),ident))
    for ident in prioritized[:MAX_ODDS_PROBE_EVENTS]:
        if client.requests_made>=MAX_BSD_REQUESTS-2:
            outcomes["remaining_request_budget_insufficient"]+=1
            break
        rows=by_id.get(ident) or []
        if len(rows)!=1:
            outcomes["ambiguous_native_event"]+=1
            continue
        kickoff=rows[0][3]
        if at>=kickoff:
            outcomes["not_prematch"]+=1
            continue
        audited+=1
        try:
            quotes,diag=fetch_event_odds(
                client,ident,kickoff=kickoff,captured_at=at,
                bookmaker_slug="consensus",max_pages=2,max_age_hours=2)
            if verified_quotes_sink is not None:
                verified_quotes_sink.append((ident,quotes))
            verified=[q for q in quotes.values()
                      if isinstance(q,dict) and q.get("origin")=="bsd_consensus"
                      and q.get("bookmaker")=="consensus"]
            if verified:
                outcomes["events_with_fresh_consensus_market_prices"]+=1
                outcomes["fresh_consensus_market_prices"]+=len(verified)
            else:
                outcomes["events_with_no_fresh_consensus_prices"]+=1
        except Exception as exc:
            if getattr(exc,"status",None)==402:
                outcomes["bsd_odds_entitlement_required"]+=1
                break
            outcomes["api_or_quote_"+type(exc).__name__]+=1
    return {
        "event_ids_selected_only_from_confirmed_native_links":True,
        "max_linked_events_for_quote_probe":MAX_ODDS_PROBE_EVENTS,
        "official_native_events_quoted_attempts":audited,
        "events_with_fresh_consensus_market_prices":
            outcomes["events_with_fresh_consensus_market_prices"],
        "fresh_consensus_market_prices":outcomes["fresh_consensus_market_prices"],
        "consensus_is_not_executable_bookmaker_offer":True,
        "independent_bookmaker_selection_codes_verified":0,
        "production_market_policy_approved":False,
        "raw_market_prices_or_event_ids_exported":False,
        "issues":dict(sorted((k,v) for k,v in outcomes.items()
                             if k not in ("events_with_fresh_consensus_market_prices",
                                          "fresh_consensus_market_prices"))),
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--public-fixtures",required=True)
    parser.add_argument("--licensed-history",help="Licensed CC0 finished results only; for exact selected-market proof")
    parser.add_argument("--existing-feed",help="Read-only public BSD production tracker JSON")
    parser.add_argument("--ledger",help="Required immutable BSD publication ledger for any candidate generation")
    parser.add_argument("--report",required=True)
    parser.add_argument("--accepted-output",help="Private process-local qualified rows; never upload as artifact")
    parser.add_argument("--days",type=int,default=2)
    parser.add_argument("--start-offset",type=int,default=2)
    args=parser.parse_args()
    if not 1<=args.days<=3 or not 1<=args.start_offset<=3:
        parser.error("BSD audit is limited to 3 calendar days and start offset 1..3")
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
        day=(clock+timedelta(days=n+args.start_offset)).date()
        page=client.list_events(day,day,max_pages=4,ttl=0)
        if not page.complete:
            raise RuntimeError("BSD fixture pagination incomplete (do not infer missing matches)")
        native.extend(page.events)
    # Resolve real competition names ONLY through the official BSD
    # league-detail endpoint for exact team+time candidates; no inferred alias.
    ids=candidate_official_league_ids(verified,native,at=clock)
    names={}
    metadata_issues=Counter()
    available=max(0,min(8,MAX_BSD_REQUESTS-client.requests_made))
    for lid in ids[:available]:
        try:
            details=client.get_json(f"/leagues/{lid}/",ttl=0)
            if not isinstance(details,dict) or positive_native_id(details.get("id"))!=lid:
                metadata_issues["identity_mismatch_or_invalid_schema"]+=1
                continue
            label=details.get("name") or details.get("league_name")
            if not isinstance(label,str) or not competition(label):
                metadata_issues["no_official_competition_name"]+=1
                continue
            names[lid]=label
        except Exception as exc:
            metadata_issues["api_"+type(exc).__name__]+=1
    if len(ids)>available:
        metadata_issues["league_metadata_budget_exceeded"]+=len(ids)-available
    linked_ids=[]
    confirmed_pairs=[]
    result=prove(verified,native,at=clock,official_leagues=names,
                 verified_id_sink=linked_ids,verified_pair_sink=confirmed_pairs)
    market_quotes=[]
    pricing=audit_official_consensus_quotes(
        client,native,linked_ids,names,at=clock,verified_quotes_sink=market_quotes)
    market_proof=None
    if bool(args.licensed_history)!=bool(args.existing_feed):
        parser.error("Selected market verification requires both licensed history and public BSD feed")
    if args.accepted_output and not args.licensed_history:
        parser.error("Candidate staging requires complete market verification and the immutable ledger")
    if args.licensed_history and not args.ledger:
        parser.error("Full candidate verification requires the immutable historical publication ledger")
    if args.licensed_history:
        from scripts.football_multisource_market_gate import verify_selected_markets
        history=[json.loads(line) for line in
                 Path(args.licensed_history).read_text(encoding="utf-8").splitlines()
                 if line.strip()]
        feed=json.loads(Path(args.existing_feed).read_text(encoding="utf-8"))
        ledger=json.loads(Path(args.ledger).read_text(encoding="utf-8"))
        by_id={ident:(ext_row,native_row) for ident,ext_row,native_row in confirmed_pairs}
        paired=[]
        for ident,quotes in market_quotes:
            if ident not in by_id:
                raise AssertionError("Quote event not in unique native matching set")
            ext_row,native_row=by_id[ident]
            paired.append((ext_row,native_row,quotes))
        accepted_rows=[]
        market_proof=verify_selected_markets(
            history,paired,feed,at=clock,historical_ledger=ledger,
            accepted_rows_sink=accepted_rows)
        if args.accepted_output:
            accepted_path=Path(args.accepted_output).resolve()
            forbidden={(ROOT/"data.json").resolve(),(ROOT/"bsd"/"publication_ledger.json").resolve()}
            if accepted_path in forbidden:
                parser.error("Accepted candidate staging must not overwrite production files")
            accepted_path.parent.mkdir(parents=True,exist_ok=True)
            accepted_path.write_text(json.dumps(accepted_rows,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            try:
                accepted_path.chmod(0o600)
            except OSError:
                pass
    else:
        accepted_rows=[]
    result.update({
        "read_only_native_consensus_price_audit":pricing,
        "full_model_selected_market_consensus_audit":market_proof,
        "candidate_official_league_metadata_ids":len(ids),
        "official_league_metadata_requested":min(len(ids),available),
        "official_league_metadata_verified":len(names),
        "official_league_metadata_issues":dict(sorted(metadata_issues.items())),
        "bsd_http_calls":client.requests_made,
        "bsd_max_http_requests":MAX_BSD_REQUESTS,
        "calendar_files_verified":health["files_ok"],
        "independent_cc0_calendar_confirmed":coverage["schedule_matches_confirmed"],
        "qualified_candidate_rows_staged":len(accepted_rows),
    })
    assert client.requests_made<=MAX_BSD_REQUESTS
    assert result["one_to_one_native_event_links"]<=coverage["schedule_matches_confirmed"]
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STRICT_BSD_NATIVE_IDENTITY_AUDIT",json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    main()
