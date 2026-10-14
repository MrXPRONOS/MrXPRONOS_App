#!/usr/bin/env python3
"""Quota-safe API-Football enrichment for existing Mr XPRONOS LIVE fixtures.

No Telegram posting, no prediction creation, no invented statistics.
Designed for hourly GitHub Actions: at most 1 fixtures lookup and 2 detailed
statistics lookups per run (72 calls/day at 24 hourly runs).
This is dormant until API_FOOTBALL_KEY is set in GitHub Actions secrets.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://v3.football.api-sports.io"
TYPES = {
    "corners": "corner_kicks",
    "corner kicks": "corner_kicks",
    "total shots": "total_shots",
    "shots total": "total_shots",
    "fouls": "fouls",
    "fouls committed": "fouls",
    "shots on goal": "shots_on_target",
    "shots on target": "shots_on_target",
    "ball possession": "ball_possession",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
}
CORE = ("corner_kicks", "total_shots", "fouls")
BUDGET_RESERVE = 20
MAX_DETAILS_PER_RUN = 2
STOP_WORDS = {"fc", "cf", "afc", "sc", "club", "fk"}


def utcnow():
    return datetime.now(timezone.utc)


def stamp(dt):
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_date(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def norm_name(name):
    clean = unicodedata.normalize("NFKD", str(name or "").lower())
    clean = "".join(x for x in clean if not unicodedata.combining(x))
    terms = re.findall(r"[a-z0-9]+", clean)
    return " ".join(x for x in terms if x not in STOP_WORDS)


def finite_stat(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(str(value).strip().rstrip("%").replace(",", "."))
        return n if n >= 0 and n < 100000 and n == n else None
    except (ValueError, TypeError):
        return None


def parse_statistics(blocks, home_id, away_id):
    """Return only numeric pairs collected for the two *known* teams."""
    output = {"home": {}, "away": {}, "totals": {}}
    if not isinstance(blocks, list) or not home_id or not away_id or home_id == away_id:
        return output
    sides = {}
    for row in blocks:
        team_id = str((row.get("team") or {}).get("id", ""))
        if team_id == str(home_id):
            sides["home"] = row
        elif team_id == str(away_id):
            sides["away"] = row
    if len(sides) < 2:
        return output
    for side, row in sides.items():
        for stat in row.get("statistics") or []:
            key = TYPES.get(str(stat.get("type", "")).strip().casefold())
            if key:
                val = finite_stat(stat.get("value"))
                if val is not None:
                    output[side][key] = val
    for key in CORE + ("shots_on_target", "yellow_cards", "red_cards"):
        a, b = output["home"].get(key), output["away"].get(key)
        if a is not None and b is not None:
            output["totals"][{"corner_kicks": "corners"}.get(key, key)] = a+b
    return output


def find_matches(canonical_rows, live_fixtures):
    """Conservative exact normalized team names + kickoff <= 90 minutes."""
    result = []
    for match in canonical_rows:
        if not match.get("is_live") or match.get("is_finished"):
            continue
        home, away = norm_name(match.get("home_team")), norm_name(match.get("away_team"))
        date = parse_date(match.get("event_date"))
        if not home or not away or date is None:
            continue
        candidates = []
        for f in live_fixtures:
            teams = f.get("teams") or {}
            if norm_name((teams.get("home") or {}).get("name")) != home:
                continue
            if norm_name((teams.get("away") or {}).get("name")) != away:
                continue
            kickoff = parse_date((f.get("fixture") or {}).get("date"))
            if kickoff is None or abs((date-kickoff).total_seconds()) > 90*60:
                continue
            fixture_id = (f.get("fixture") or {}).get("id")
            if not isinstance(fixture_id, int) or fixture_id <= 0:
                continue
            candidates.append((f, abs((date-kickoff).total_seconds())))
        # Multiple plausible source matches: do not guess.
        if len(candidates) == 1:
            result.append((match, candidates[0][0]))
    # Prioritize fixtures with known clock, missing three market data pairs.
    def score(pair):
        match, f = pair
        minute = ((f.get("fixture") or {}).get("status") or {}).get("elapsed") or 0
        stats = match.get("merged_stats") or {}
        missing = sum(
            not isinstance((stats.get("home") or {}).get(k),(int,float)) or
            not isinstance((stats.get("away") or {}).get(k),(int,float))
            for k in CORE
        )
        return (missing, 1 if 15 <= minute <= 82 else 0, minute)
    return sorted(result,key=score,reverse=True)


def get_json(url, headers, timeout=17):
    with urlopen(Request(url,headers=headers),timeout=timeout) as r:
        payload = json.load(r)
        return payload, r.headers.get("x-ratelimit-requests-remaining")


def fetch_stats(key, url):
    payload, remaining = get_json(BASE+url,{"x-apisports-key":key,"Accept":"application/json"})
    if payload.get("errors"):
        raise RuntimeError("Provider rejected statistics request")
    return payload.get("response") or [], remaining


def db_json(base, secret, method, table, params=None, body=None):
    uri=base.rstrip("/")+"/rest/v1/"+table
    if params:
        uri+="?"+urlencode(params)
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode("utf-8")
    req=Request(uri,method=method,data=data,headers={
        "apikey":secret,"Authorization":"Bearer "+secret,
        "Content-Type":"application/json",
        "Prefer":"resolution=merge-duplicates,return=minimal",
    })
    with urlopen(req,timeout=16) as r:
        if method == "GET":
            return json.load(r)
        return r.status


def build_row(match, fixture, stats):
    minute=finite_stat(((fixture.get("fixture") or {}).get("status") or {}).get("elapsed"))
    if minute is None or minute <= 0 or minute > 130:
        return None
    if not any(k in stats["home"] and k in stats["away"] for k in CORE):
        return None
    fixture_id=(fixture.get("fixture") or {}).get("id")
    return {
        "source_name":"api_football",
        "source_match_id":str(fixture_id),
        "canonical_match_id":match["canonical_match_id"],
        "home_team":match.get("home_team"),
        "away_team":match.get("away_team"),
        "league_name":match.get("league_name"),
        "event_date":match.get("event_date"),
        "minute":int(minute),
        "home_score":(fixture.get("goals") or {}).get("home"),
        "away_score":(fixture.get("goals") or {}).get("away"),
        "is_live":True,
        "is_finished":False,
        "stats_json":stats,
        "raw_json":{
            "source":"api_football",
            "fixture_id":fixture_id,
            "statistics_verified":True,
            "fields_present":sorted(set(stats["home"]).intersection(stats["away"])),
        },
        "updated_at":stamp(utcnow()),
    }


def main():
    key=os.getenv("API_FOOTBALL_KEY","").strip()
    supabase_url=os.getenv("SUPABASE_URL","").strip()
    supabase_secret=os.getenv("SUPABASE_SERVICE_ROLE_KEY","").strip()
    if not key:
        print("API_FOOTBALL_SKIPPED: configure API_FOOTBALL_KEY in GitHub Actions secrets")
        return 0
    if not supabase_url.startswith("https://") or not supabase_secret:
        print("::error::Supabase URL / server-side key missing")
        return 1

    # Never consume a provider request when there are no fresh live fixtures.
    rows=db_json(supabase_url,supabase_secret,"GET","live_stats_merged",{
        "select":"canonical_match_id,home_team,away_team,league_name,event_date,minute,is_live,is_finished,merged_stats,updated_at",
        "is_live":"eq.true",
        "is_finished":"eq.false",
        "updated_at":"gte."+stamp(utcnow()-timedelta(minutes=7)),
        "limit":"300",
    })
    if not rows:
        print("API_FOOTBALL_NO_LIVE_MATCHES")
        return 0

    fixtures,remaining=fetch_stats(key,"/fixtures?live=all")
    if remaining is not None and int(remaining)<BUDGET_RESERVE:
        print("API_FOOTBALL_QUOTA_RESERVE",remaining)
        return 0
    pairs=find_matches(rows,fixtures)
    print("API_FOOTBALL_MATCHES",json.dumps({"local":len(rows),"remote":len(fixtures),"strict_pairs":len(pairs)}))
    completed=0
    for match,fixture in pairs[:MAX_DETAILS_PER_RUN]:
        fid=(fixture.get("fixture") or {}).get("id")
        response,remaining=fetch_stats(key,f"/fixtures/statistics?fixture={fid}")
        home_id=str((fixture.get("teams") or {}).get("home",{}).get("id",""))
        away_id=str((fixture.get("teams") or {}).get("away",{}).get("id",""))
        stats=parse_statistics(response,home_id,away_id)
        row=build_row(match,fixture,stats)
        if row is not None:
            db_json(supabase_url,supabase_secret,"POST","live_stats_sources",
                    {"on_conflict":"source_name,source_match_id"},[row])
            completed+=1
        if remaining is not None and int(remaining)<=BUDGET_RESERVE:
            break
    print("API_FOOTBALL_STATS_SAVED",json.dumps({"matches":completed,"requests_max":1+MAX_DETAILS_PER_RUN}))


if __name__=="__main__":
    try:
        sys.exit(main())
    except HTTPError as error:
        print("::error::API/DB HTTP status "+str(error.code),file=sys.stderr)
        sys.exit(1)
    except (URLError,ValueError,KeyError,RuntimeError) as error:
        # Never print exception URLs: authenticated DB requests can contain headers.
        print("::error::Stats enrichment failed: "+type(error).__name__,file=sys.stderr)
        sys.exit(1)
