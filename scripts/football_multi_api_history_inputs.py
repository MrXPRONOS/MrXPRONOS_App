#!/usr/bin/env python3
"""License-gated multi-API historical results for the UNCHANGED BSD V2 engine.

Accepted *input adapters*: ESPN, SportScore, TheSportsDB, OpenLigaDB,
API-Football, and existing BSD-format records. The first five require
an explicit operator-confirmed history/model-use authorization. Neither
data availability nor a mere right to view a fixture implies model rights.

This module never makes network requests and never computes betting predictions.
It yields provider-attributed, finished-only history for an external V2History.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

SOURCES = frozenset({"espn", "sportscore", "thesportsdb",
                     "openligadb", "api_football", "bsd"})
FINAL = frozenset({"finished","post","ft","fulltime","full_time",
                   "afterextra","aet","afterpenalties","pen","matchfinished"})
LIMIT_ROWS = 200_000


def aware(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z","+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def score(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    raw = str(value).strip()
    if not raw.isdecimal():
        return None
    n = int(raw)
    return n if 0 <= n <= 30 else None


def native_name(value: Any) -> str:
    if isinstance(value, dict):
        for k in ("displayName","name","display_name","teamName","strTeam"):
            if isinstance(value.get(k), str) and value[k].strip():
                return value[k].strip()
        return ""
    return value.strip() if isinstance(value, str) else ""


def flat_records(source: str, payload: Any) -> list[dict]:
    """Normalize provider-specific *finished* historical event structures.

    Does not guess missing scores, competition labels or fixture timestamps.
    Only explicit fields supported by provider's declared existing adapter
    and fixture API contracts. Other provider payload shapes abstain.
    """
    if source == "api_football" and isinstance(payload, dict):
        entries = payload.get("response") or []
    elif source == "thesportsdb" and isinstance(payload, dict):
        entries = payload.get("events") or []
    elif source == "espn" and isinstance(payload, dict):
        entries = payload.get("events") or []
    elif source == "sportscore" and isinstance(payload, dict):
        entries = payload.get("fixtures") or payload.get("matches") or payload.get("results") or []
    elif source == "openligadb":
        entries = payload if isinstance(payload,list) else (payload.get("matches") or [] if isinstance(payload,dict) else [])
    elif source == "bsd":
        entries = payload if isinstance(payload,list) else []
    else:
        entries = payload if isinstance(payload,list) else (payload.get("rows") or [] if isinstance(payload,dict) else [])
    if not isinstance(entries,list):
        return []
    rows=[]
    for event in entries:
        if not isinstance(event,dict):
            continue
        item={}
        # Universal flat contract from existing snapshot adapters.
        if ("home_team" in event and "away_team" in event and
                event.get("home_score") is not None and event.get("away_score") is not None):
            item={
                "original_id":event.get("provider_event_id") or event.get("id"),
                "home_team":native_name(event.get("home_team")),
                "away_team":native_name(event.get("away_team")),
                "league":native_name(event.get("league_name") or event.get("league") or event.get("competition_name")),
                "kickoff_utc":event.get("event_date") or event.get("kickoff_utc"),
                "home_score":event.get("home_score"),"away_score":event.get("away_score"),
                "status":event.get("state") or event.get("status"),
            }
        elif source=="api_football":
            f=event.get("fixture") or {}
            ts=f.get("status") or {}
            t=event.get("teams") or {}
            goals=event.get("goals") or {}
            item={"original_id":f.get("id"),"home_team":native_name(t.get("home")),
                  "away_team":native_name(t.get("away")),
                  "league":native_name(event.get("league")),
                  "kickoff_utc":f.get("date"),"home_score":goals.get("home"),
                  "away_score":goals.get("away"),"status":ts.get("short")}
        elif source=="thesportsdb":
            # Date-only event schemas remain unusable without a UTC start time.
            dt=event.get("dateEvent")
            st=event.get("strTime")
            timestamp=(dt+"T"+st+"Z") if (isinstance(dt,str) and isinstance(st,str) and ":" in st) else None
            item={"original_id":event.get("idEvent"),
                  "home_team":native_name(event.get("strHomeTeam")),
                  "away_team":native_name(event.get("strAwayTeam")),
                  "league":native_name(event.get("strLeague")),
                  "kickoff_utc":event.get("strTimestamp") or timestamp,
                  "home_score":event.get("intHomeScore"),"away_score":event.get("intAwayScore"),
                  "status":event.get("strStatus")}
        elif source=="openligadb":
            results=event.get("matchResults") or []
            final=next((x for x in results if isinstance(x,dict) and x.get("resultTypeID")==2),None)
            item={"original_id":event.get("matchID"),
                  "home_team":native_name(event.get("team1")),
                  "away_team":native_name(event.get("team2")),
                  "league":native_name(event.get("leagueName") or event.get("league")),
                  "kickoff_utc":event.get("matchDateTimeUTC"),
                  "home_score":(final or {}).get("pointsTeam1"),
                  "away_score":(final or {}).get("pointsTeam2"),
                  "status":"finished" if event.get("matchIsFinished") is True else ""}
        elif source=="espn":
            competitions=event.get("competitions") or []
            c=competitions[0] if competitions and isinstance(competitions[0],dict) else {}
            sides=c.get("competitors") or []
            h=next((x for x in sides if x.get("homeAway")=="home"),{})
            a=next((x for x in sides if x.get("homeAway")=="away"),{})
            st=(c.get("status") or event.get("status") or {})
            typ=st.get("type") or {}
            lg=c.get("league") or event.get("league") or {}
            item={"original_id":event.get("id") or c.get("id"),
                  "home_team":native_name(h.get("team")),
                  "away_team":native_name(a.get("team")),
                  "league":native_name(lg),
                  "kickoff_utc":event.get("date") or c.get("date"),
                  "home_score":h.get("score"),"away_score":a.get("score"),
                  "status":"finished" if typ.get("completed") is True else ""}
        elif source=="sportscore":
            item={"original_id":event.get("id") or event.get("match_id"),
                  "home_team":native_name(event.get("home")),
                  "away_team":native_name(event.get("away")),
                  "league":native_name(event.get("competition") or event.get("league")),
                  "kickoff_utc":event.get("time") or event.get("date") or event.get("start_time"),
                  "home_score":event.get("home_score") if event.get("home_score") is not None else event.get("score_home"),
                  "away_score":event.get("away_score") if event.get("away_score") is not None else event.get("score_away"),
                  "status":event.get("status") or event.get("status_text")}
        if item:
            rows.append(item)
    return rows


def permitted(provider: str, licenses: dict) -> bool:
    """Operator-controlled, fail-closed right to USE HISTORICAL DATA IN A MODEL."""
    if provider not in SOURCES:
        return False
    terms=licenses.get(provider)
    return bool(isinstance(terms,dict) and terms.get("approved") is True
                and terms.get("historical_model_use") is True
                and terms.get("commercial_product") is True
                and isinstance(terms.get("legal_basis"),str)
                and len(terms["legal_basis"].strip()) >= 12
                and terms.get("attribution_compliant") is True)


def ingest(snapshots: list[dict], licenses: dict, *,
           as_of: datetime) -> tuple[list[dict],dict]:
    """Ingest already-acquired snapshots. Zero internet calls, quotas or writes."""
    if as_of.tzinfo is None:
        raise ValueError("UTC analysis time required")
    as_of=as_of.astimezone(timezone.utc)
    rows=[]
    counts=Counter()
    origins=Counter()
    ids_by_provider=set()
    if not isinstance(snapshots,list) or not isinstance(licenses,dict):
        raise ValueError("Expected list of provider snapshots and rights manifest")
    for snapshot in snapshots:
        if not isinstance(snapshot,dict):
            counts["invalid_snapshot"]+=1
            continue
        provider=str(snapshot.get("provider") or "")
        if not permitted(provider,licenses):
            counts["rights_not_confirmed"]+=1
            continue
        seen_at=aware(snapshot.get("observed_at"))
        if seen_at is None or seen_at>as_of:
            counts["snapshot_not_available_at_analysis"]+=1
            continue
        batch=flat_records(provider,snapshot.get("data") or snapshot.get("rows") or [])
        if len(rows)+len(batch)>LIMIT_ROWS:
            raise ValueError("Historical ingestion row limit exceeded")
        for item in batch:
            kickoff=aware(item.get("kickoff_utc"))
            score_h,score_a=score(item.get("home_score")),score(item.get("away_score"))
            state=str(item.get("status") or "").strip().lower().replace(" ","").replace("-","").replace("_","")
            h,a,lg=item.get("home_team"),item.get("away_team"),item.get("league")
            native=item.get("original_id")
            if not kickoff or not native or not h or not a or not lg or score_h is None or score_a is None:
                counts["invalid_identity_or_score"]+=1
                continue
            if state not in FINAL:
                counts["not_confirmed_final"]+=1
                continue
            if kickoff+timedelta(hours=4)>=as_of:
                counts["not_settled_as_of"]+=1
                continue
            if (provider,str(native)) in ids_by_provider:
                counts["duplicate_provider_id"]+=1
                continue
            ids_by_provider.add((provider,str(native)))
            rows.append({
                "source":provider,"source_id":str(native),"status":"finished",
                "season":str(kickoff.year),
                "league":lg,"home_team":h,"away_team":a,
                "match_date":kickoff.date().isoformat(),
                "kickoff_utc":kickoff.isoformat(),"home_score":score_h,"away_score":score_a,
                "observed_at":seen_at.isoformat(),"time_precision":"instant",
            })
            origins[provider]+=1
    return rows,{"loaded_historical_rows":len(rows),
                 "permitted_provider_rows":dict(sorted(origins.items())),
                 "rejections":dict(sorted(counts.items())),
                 "no_auto_rights_override":True,
                 "no_api_called":True,
                 "production_changed":False}



def trusted_private_bsd_rows(events: list[dict], *, as_of: datetime,
                             explicitly_authorized: bool = False,
                             public_bsd_feed: dict | None = None) -> tuple[list[dict],dict]:
    """BSD archive scores + STRICT authentic-ID display labels; report counts only.

    BSD archive is intentionally ID-centric. Never invent team or competition
    labels. Recover labels only when the *same BSD numeric IDs* occur in a
    trusted, previously published BSD feed (and have no competing names).
    """
    if not explicitly_authorized:
        return [], {"status":"permission_required","converted":0}
    from scripts.football_history_shadow import canonical_team
    from scripts.football_history_features import competition
    if as_of.tzinfo is None:
        raise ValueError("Timezone-aware analysis time required")
    as_of=as_of.astimezone(timezone.utc)
    counts=Counter()
    native_names=defaultdict(set)
    prepared=[]
    official_leagues=defaultdict(set)
    official_teams=defaultdict(set)
    # First pass: exact, internally consistent labels belonging to the same
    # native BSD identifiers within the encrypted archive. Never infer from
    # similar-looking club names or an unrelated competition.
    archival_leagues=defaultdict(set)
    archival_teams=defaultdict(set)
    for row in events:
        if not isinstance(row,dict) or str(row.get("status") or "").lower()!="finished":
            continue
        stamp=aware(row.get("event_date"))
        if stamp is None or stamp+timedelta(hours=4)>=as_of:
            continue
        try:
            rid=int(row.get("league_id"))
        except (TypeError,ValueError):
            continue
        if rid<=0:
            continue
        meta=row.get("league_name") or row.get("competition_name") or row.get("league")
        if isinstance(meta,dict):
            meta=meta.get("name")
        label=competition(str(meta or ""))
        if label:
            archival_leagues[rid].add(label)
        for position in ("home","away"):
            entity=row.get(position+"_team")
            native_id=row.get(position+"_team_id") or (entity.get("id") if isinstance(entity,dict) else None)
            try:
                native_id=int(native_id)
            except (TypeError,ValueError):
                continue
            title=canonical_team(native_name(entity))
            if native_id>0 and title:
                archival_teams[(rid,native_id)].add(title)
    if public_bsd_feed is not None:
        if not isinstance(public_bsd_feed,dict) or public_bsd_feed.get("source")!="bsd":
            raise ValueError("Identity hints require authentic BSD published feed")
        for row in public_bsd_feed.get("matches",[]):
            if not isinstance(row,dict) or row.get("source")!="bsd":
                continue
            try:
                lid=int(row.get("league_id"))
                hid=int(row.get("home_team_id"))
                aid=int(row.get("away_team_id"))
            except (TypeError,ValueError):
                continue
            if min(lid,hid,aid)<=0 or hid==aid:
                continue
            league=competition(str(row.get("league") or ""))
            if not league:
                continue
            official_leagues[lid].add(league)
            for side,tid in (("home",hid),("away",aid)):
                name=canonical_team(native_name(row.get(side+"_team")))
                if name:
                    official_teams[(lid,tid)].add(name)
    # Only add missing identity hints if every observation under the same
    # native ID agrees. Public BSD names remain authoritative where present.
    for rid,aliases in archival_leagues.items():
        if rid not in official_leagues and len(aliases)==1:
            official_leagues[rid].update(aliases)
    for native_key,aliases in archival_teams.items():
        if native_key not in official_teams and len(aliases)==1:
            official_teams[native_key].update(aliases)
    for event in events:
        if not isinstance(event,dict) or str(event.get("status") or "").lower()!="finished":
            counts["not_completed"]+=1
            continue
        instant=aware(event.get("event_date"))
        hscore,ascore=score(event.get("home_score")),score(event.get("away_score"))
        if instant is None or instant+timedelta(hours=4)>=as_of:
            counts["not_settled_by_analysis"]+=1
            continue
        home,away=(event.get("home_team"),event.get("away_team"))
        try:
            lid=event.get("league_id") or (
                event.get("league",{}).get("id") if isinstance(event.get("league"),dict) else None)
            ht=event.get("home_team_id") or (home.get("id") if isinstance(home,dict) else None)
            at=event.get("away_team_id") or (away.get("id") if isinstance(away,dict) else None)
            lid,ht,at=int(lid),int(ht),int(at)
        except (ValueError,TypeError):
            counts["missing_native_ids"]+=1
            continue
        if min(lid,ht,at)<=0 or ht==at or hscore is None or ascore is None or event.get("id") is None:
            counts["invalid_native_ids_or_scores"]+=1
            continue
        rawleague=event.get("league_name") or event.get("competition_name") or event.get("league")
        if isinstance(rawleague,dict):
            rawleague=rawleague.get("name")
        names=set(official_leagues.get(lid,()))
        native_league=competition(str(rawleague or ""))
        if native_league:
            names.add(native_league)
        if len(names)!=1:
            counts["missing_or_ambiguous_league_label"]+=1
            continue
        league=next(iter(names))
        hname=native_name(home)
        aname=native_name(away)
        if not hname:
            options=official_teams.get((lid,ht),set())
            hname=next(iter(options)) if len(options)==1 else ""
        if not aname:
            options=official_teams.get((lid,at),set())
            aname=next(iter(options)) if len(options)==1 else ""
        if not hname or not aname:
            counts["missing_or_ambiguous_team_name"]+=1
            continue
        if canonical_team(hname)==canonical_team(aname):
            counts["identical_team_names"]+=1
            continue
        if official_teams.get((lid,ht)) and canonical_team(hname) not in official_teams[(lid,ht)]:
            counts["conflicting_home_name"]+=1
            continue
        if official_teams.get((lid,at)) and canonical_team(aname) not in official_teams[(lid,at)]:
            counts["conflicting_away_name"]+=1
            continue
        native_names[(league,canonical_team(hname))].add(ht)
        native_names[(league,canonical_team(aname))].add(at)
        prepared.append((event,instant,league,hname,aname,hscore,ascore))
    rows=[]
    for event,instant,league,hname,aname,hscore,ascore in prepared:
        if (len(native_names[(league,canonical_team(hname))])!=1 or
                len(native_names[(league,canonical_team(aname))])!=1):
            counts["ambiguous_team_ids_for_name"]+=1
            continue
        rows.append({
            "source":"bsd","source_id":str(event["id"]),
            "status":"finished","league":league,
            "home_team":hname,"away_team":aname,
            "kickoff_utc":instant.isoformat(),"match_date":instant.date().isoformat(),
            "home_score":hscore,"away_score":ascore,
            "time_precision":"instant",
        })
    counts["converted"]=len(rows)
    return rows,{
        "status":"private_internal_research_only",
        "converted":len(rows),
        "identity_hints":{"known_league_ids":sum(len(x)==1 for x in official_leagues.values()),
                          "known_team_ids":sum(len(x)==1 for x in official_teams.values()),
                          "archival_consistent_league_ids":sum(len(v)==1 for v in archival_leagues.values()),
                          "archival_consistent_team_ids":sum(len(v)==1 for v in archival_teams.values())},
        "rejections":dict(sorted(counts.items())),
        "private_ids_exposed_in_report":False,
        "model_modified":False,
    }
