#!/usr/bin/env python3
"""Read-only match discovery on selected future days for BSD V2 research."""
from __future__ import annotations
import argparse
from datetime import date,timedelta,datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from bsd.free_football_sources import collect_free_day
from scripts.football_daily_multisource_shadow import BudgetSession, merge
from scripts.football_history_shadow import canonical_team
from scripts.football_history_features import competition

def collect(days:list[date], *, budget=24, session=None, collector=None):
    if not 1<=len(days)<=4 or len(set(days))!=len(days):
        raise ValueError("Use one to four distinct days")
    if not 1<=budget<=24:raise ValueError("Daily request budget exceeded")
    session=session or BudgetSession(budget)
    collector=collector or collect_free_day
    combined={}
    stats={}
    for day in days:
        snapshots=collector(session,day,include_espn=True)
        fixtures,quality=merge(snapshots)
        combined[day.isoformat()]=fixtures
        stats[day.isoformat()]={"fixtures":len(fixtures),"provider_health":quality["providers"]}
    rows=[]
    for day in days:
        rows.extend(combined[day.isoformat()])
    # Source-local fixture hashes may repeat on different calendar days.
    # Only group the SAME kickoff and same canonical teams. Never merge
    # unrelated teams even if the upstream short fixture_key is identical.
    by_key={}
    for f in rows:
        key=(str(f.get("kickoff_utc") or ""),
             canonical_team(str(f.get("home_team") or "")),
             canonical_team(str(f.get("away_team") or "")),
             str(f.get("fixture_key") or ""))
        if key not in by_key:
            by_key[key]=f
        else:
            current=by_key[key]
            common=dict(current.get("sources") or {})
            for provider,source in (f.get("sources") or {}).items():
                if provider in common and common[provider]!=source:
                    # Do not quietly overwrite contradictory native IDs.
                    current["ambiguous_match"]=True
                else:
                    common[provider]=source
            current["sources"]=common
            current["source_count"]=len(common)
            old_labels={competition(x) for x in current.get("league_labels",[]) if competition(x)}
            new_labels={competition(x) for x in f.get("league_labels",[]) if competition(x)}
            labels=old_labels|new_labels
            current["league_labels"]=sorted(labels)
            current["league_conflict"]=bool(current.get("league_conflict") or f.get("league_conflict") or len(labels)>1)
            current["league_verified"]=len(labels)==1 and not current["league_conflict"]
            current["ambiguous_match"]=bool(current.get("ambiguous_match") or f.get("ambiguous_match"))
            current["scores_conflict"]=bool(current.get("scores_conflict") or f.get("scores_conflict"))
            if current["status"]!="prematch" or f["status"]!="prematch":
                current["status"]="not_prematch"
    # SportScore day discovery requests are explicitly limited to 200 rows
    # (see bsd.free_football_sources.fetch_sportscore_day). A full page is
    # NOT evidence that the league/day slate is complete; do not claim it.
    sportscore_capped_days=[
        day for day in sorted(stats)
        if (stats[day]["provider_health"].get("sportscore") or {}).get("reported",0)>=200
    ]
    return sorted(by_key.values(),key=lambda f:(f["kickoff_utc"],f["fixture_key"])),{
        "days":[d.isoformat() for d in days],
        "sources":stats,"total_fixtures":len(by_key),
        "sportscore_page_size_limit":200,
        "sportscore_days_at_page_limit":len(sportscore_capped_days),
        "sportscore_coverage_possibly_incomplete":bool(sportscore_capped_days),
        "dedupe_key_includes_kickoff_and_both_club_names":True,
        "requests":dict(getattr(session,"calls",{})),
        "requests_total":getattr(session,"total",0),
        "max_requests":budget,
        "no_production_writes":True,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start-day",required=True)
    p.add_argument("--count-days",type=int,default=3)
    p.add_argument("--max-http",type=int,default=24)
    p.add_argument("--out",required=True)
    p.add_argument("--report",required=True)
    a=p.parse_args()
    if not 1<=a.count_days<=4:
        p.error("count-days must be 1 to 4")
    start=date.fromisoformat(a.start_day)
    dates=[start+timedelta(days=i) for i in range(a.count_days)]
    rows,report=collect(dates,budget=a.max_http)
    for name,value in ((a.out,rows),(a.report,report)):
        target=Path(name)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("THREE_DAY_PUBLIC_MATCH_COVERAGE",json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
    main()
