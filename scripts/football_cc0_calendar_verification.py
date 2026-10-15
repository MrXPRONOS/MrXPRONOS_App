#!/usr/bin/env python3
"""CC0 OpenFootball schedule corroboration for multisource BSD V2.

A day-only OpenFootball calendar NEVER provides the kickoff timestamp.
Use only the already time-zoned kickoff from the discovered API fixture.
League is confirmed iff exactly one CC0 schedule matches
(day, normalized HOME name, normalized AWAY name). No fuzzy matches.
No betting outputs and no Telegram side effects.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.football_history_shadow import canonical_team
from scripts.football_history_features import competition
from scripts.football_match_source_router import aware_time

# Actual public 2026-27 season files verified in the CC0 OpenFootball repo.
SEASON_FILES={
    "de.1":"Bundesliga","en.1":"Premier League","en.2":"Championship",
    "es.1":"La Liga","fr.1":"Ligue 1","it.1":"Serie A",
    "nl.1":"Eredivisie","pt.1":"Primeira Liga",
}
HOST_PREFIX="https://raw.githubusercontent.com/openfootball/football.json/master/"
MAX_DOWNLOADS=8

def download_schedules(session, *, season: str="2026-27", timeout: int=15) -> tuple[list[dict],dict]:
    if not re.fullmatch(r"20\d{2}-\d{2}",season):
        raise ValueError("Invalid season")
    rows=[]
    health=Counter()
    for filename,league in SEASON_FILES.items():
        url=HOST_PREFIX+season+"/"+filename+".json"
        health["requests"]+=1
        try:
            response=session.get(url,timeout=timeout)
            response.raise_for_status()
            payload=response.json()
            values=payload.get("matches") if isinstance(payload,dict) else None
            if not isinstance(values,list):
                health["invalid_json_schema"]+=1
                continue
            for v in values:
                if not isinstance(v,dict):
                    continue
                try:
                    day=date.fromisoformat(str(v.get("date") or ""))
                except ValueError:
                    continue
                home=canonical_team(str(v.get("team1") or ""))
                away=canonical_team(str(v.get("team2") or ""))
                if not home or not away or home==away:
                    continue
                # Preserve ALL matches as verification evidence, including
                # previously finished: the time and source remain independent.
                rows.append({"day":day.isoformat(),"league":league,"home":home,"away":away})
            health["files_ok"]+=1
        except (ValueError,TypeError,KeyError,Exception) as exc:
            health["file_error_"+type(exc).__name__]+=1
    return rows,{"files_attempted":health["requests"],
                 "files_ok":health["files_ok"],
                 "schedule_rows":len(rows),
                 "errors":{k:v for k,v in health.items() if k.startswith("file_error_") or k=="invalid_json_schema"},
                 "source_license":"CC0-1.0/OpenFootball-public-domain",
                 "no_inferred_kickoff_time":True}


def corroborate(fixtures: list[dict], calendar: list[dict], *,
                as_of: datetime) -> tuple[list[dict],dict]:
    if as_of.tzinfo is None:
        raise ValueError("As-of must contain timezone")
    key_leagues=defaultdict(set)
    # These indexes ONLY explain missing calendar coverage; they NEVER
    # confirm an alias, fixture, team or league by approximate matching.
    clubs_by_day=defaultdict(set)
    oriented_pairs_by_day=defaultdict(set)
    days_by_oriented_pair=defaultdict(set)
    for row in calendar:
        if not isinstance(row,dict):
            continue
        home=canonical_team(str(row.get("home") or ""))
        away=canonical_team(str(row.get("away") or ""))
        league=competition(str(row.get("league") or ""))
        day=str(row.get("day") or "")
        if home and away and league and day:
            key_leagues[(day,home,away)].add(league)
            clubs_by_day[day].update((home,away))
            oriented_pairs_by_day[day].add((home,away))
            days_by_oriented_pair[(home,away)].add(day)
    reasons=Counter()
    by_discovery_source=defaultdict(Counter)
    enriched=[]
    for item in fixtures:
        provider=str(item.get("discovered_by") or "unknown")
        by_discovery_source[provider]["input"]+=1
        copy={**item}
        when=aware_time(item.get("kickoff_utc"))
        if (when is None or when<=as_of or item.get("status")!="prematch"
                or item.get("ambiguous_match") or item.get("league_conflict")
                or item.get("scores_conflict")):
            reasons["not_eligible_prematch"]+=1
            by_discovery_source[provider]["not_eligible_prematch"]+=1
            enriched.append(copy)
            continue
        # Schedule's original date refers to local football calendar.
        # Do not shift between UTC days or guess timezone.
        key=(when.date().isoformat(),
             canonical_team(str(item.get("home_team") or "")),
             canonical_team(str(item.get("away_team") or "")))
        eligible=key_leagues.get(key,set())
        existing={competition(s) for s in item.get("league_labels",[]) if competition(s)}
        if len(eligible)==1:
            league=next(iter(eligible))
            if existing and existing!={league}:
                copy["league_conflict"]=True
                copy["league_verified"]=False
                reasons["schedule_conflicts_with_source_league"]+=1
                by_discovery_source[provider]["league_conflict"]+=1
            else:
                copy["league_labels"]=[league]
                copy["league_verified"]=True
                copy["_schedule_verified_by"]="openfootball_cc0"
                reasons["schedule_exact_league_confirmed"]+=1
                by_discovery_source[provider]["confirmed"]+=1
        elif len(eligible)>1:
            copy["league_conflict"]=True
            copy["league_verified"]=False
            reasons["multiple_calendar_leagues"]+=1
            by_discovery_source[provider]["multiple_calendar_leagues"]+=1
        else:
            reasons["no_cc0_schedule_match"]+=1
            by_discovery_source[provider]["no_calendar_match"]+=1
            day,home,away=key
            # Aggregate *reasons*, not unmatched club names/fixtures.
            # UTC date mismatch and reversed sides are diagnostic only:
            # neither is permission to change a fixture automatically.
            if (away,home) in oriented_pairs_by_day.get(day,set()):
                cause="reversed_home_away_same_day"
            elif (home,away) in days_by_oriented_pair:
                cause="exact_pair_on_other_calendar_day"
            elif day not in clubs_by_day:
                cause="calendar_day_absent"
            else:
                found=sum(name in clubs_by_day[day] for name in (home,away))
                cause=("both_clubs_elsewhere_on_day" if found==2 else
                       "one_club_on_day" if found==1 else
                       "no_clubs_on_day")
            by_discovery_source[provider]["unmatched_"+cause]+=1
        enriched.append(copy)
    return enriched,{
        "input_fixtures":len(fixtures),
        "schedule_matches_confirmed":reasons["schedule_exact_league_confirmed"],
        "refused":dict(sorted(reasons.items())),
        "by_discovery_source":{k:dict(sorted(v.items())) for k,v in sorted(by_discovery_source.items())},
        "no_time_inference":True,
        "not_betting_ready":True,
        "no_production_output_modified":True,
    }


def main() -> None:
    import requests
    p=argparse.ArgumentParser()
    p.add_argument("--fixtures",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--analysis-at",required=True)
    p.add_argument("--season",default="2026-27")
    opts=p.parse_args()
    at=aware_time(opts.analysis_at)
    if at is None: p.error("analysis-at needs explicit UTC offset")
    fixtures=json.loads(Path(opts.fixtures).read_text(encoding="utf-8"))
    if not isinstance(fixtures,list): p.error("fixtures must be list")
    session=requests.Session()
    schedule,fetch=download_schedules(session,season=opts.season)
    augmented,coverage=corroborate(fixtures,schedule,as_of=at)
    for name,payload in ((opts.output,augmented),(opts.report,{"download":fetch,"coverage":coverage})):
        target=Path(name)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CC0_CALENDAR_VERIFICATION",json.dumps({"download":fetch,"coverage":coverage},ensure_ascii=False))


if __name__=="__main__":
    main()
