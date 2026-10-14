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
    by_key={}
    for f in rows:
        key=f["fixture_key"]
        if key not in by_key:
            by_key[key]=f
        else:
            # Do not combine same stable hash with incompatible league.
            if by_key[key]["home_team"]!=f["home_team"] or by_key[key]["away_team"]!=f["away_team"]:
                raise ValueError("Collision in fixture identifiers")
    return sorted(by_key.values(),key=lambda f:(f["kickoff_utc"],f["fixture_key"])),{
        "days":[d.isoformat() for d in days],
        "sources":stats,"total_fixtures":len(by_key),
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
