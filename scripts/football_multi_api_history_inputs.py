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
from collections import Counter
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
