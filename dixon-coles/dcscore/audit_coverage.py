"""Audit expanded ESPN football leagues before enabling them in production.

Audits public provider responses (not official-league verification). A candidate
cannot become active merely because its URL returns HTTP 200 or an empty list.
No fixture is fabricated, no scores are predicted, and nothing is published.
"""
from __future__ import annotations

import argparse
from datetime import datetime, date, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from .daily_espn import ALLOWED, ENABLED, CANDIDATES, ESPNProvider
from .daily_sources import DailySourceError
from .logo_policy import valid_logo_url
from .domain import utc_datetime


def inspect_one(league: str, now: datetime) -> dict:
    result = {"code":league,"name":ALLOWED[league],"status":"UNVERIFIED",
              "history":0,"teams_with_four_games":0,"last_result_age_days":None,
              "fixture_with_two_real_crests":0,"historical_crest_pairs":0,
              "annual_counts":{},"annual_at_400_limit":[],
              "errors":[],"safe_to_promote":False}
    provider=ESPNProvider(leagues=[league], years_back=2)
    fixture=SimpleNamespace(competition="ES:"+league.upper())
    try:
        history,warnings=provider.history(fixture,now)
        result["history"]=len(history)
        result["errors"]+=warnings[:5]
        if history:
            last=max(m.kickoff for m in history)
            result["last_result_age_days"]=round((now-last).total_seconds()/86400,2)
        # A successful calendar endpoint does not imply usable club badges.
        # Check authentic crest URLs in real archived fixtures, including
        # periods with no matches in the upcoming week.
        for year in range(now.year-2,now.year+1):
            annual = provider._fetch(league,str(year))
            result["annual_counts"][str(year)] = len(annual)
            if len(annual) >= 400:
                result["annual_at_400_limit"].append(year)
            for event in annual:
                if not isinstance(event,dict):
                    continue
                try:
                    teams=event["competitions"][0]["competitors"]
                    crest_urls=[side["team"].get("logo") for side in teams]
                    if len(crest_urls)==2 and all(valid_logo_url(u) for u in crest_urls):
                        result["historical_crest_pairs"]+=1
                except (KeyError,IndexError,TypeError):
                    continue
        counts={}
        for m in history:
            for team in (m.home_id,m.away_id):
                counts[team]=counts.get(team,0)+1
        result["teams_with_four_games"]=sum(n>=4 for n in counts.values())
        # Recent/future schedules are sampled separately from annual results.
        for offset in range(1,5):
            day=(now+timedelta(days=offset)).date()
            fixtures,issues=provider.discover(day,now)
            if issues:
                result["errors"]+=issues[:2]
            result["fixture_with_two_real_crests"]+=sum(
                valid_logo_url(f.home_logo_url) and valid_logo_url(f.away_logo_url)
                for f in fixtures)
        # Rules mirror the production history gates, plus cross-team coverage.
        # An empty upcoming schedule does not invalidate a real league.
        okay = (result["history"]>=80 and result["teams_with_four_games"]>=8
                and result["last_result_age_days"] is not None
                and result["last_result_age_days"]<=35
                and result["historical_crest_pairs"]>=5
                and not result["annual_at_400_limit"]
                and not result["errors"])
        result["safe_to_promote"]=bool(okay)
        result["status"]="ELIGIBLE_FOR_REVIEW" if okay else "DO_NOT_ENABLE"
    except (DailySourceError,TypeError,ValueError,OSError) as exc:
        result["errors"].append(f"{type(exc).__name__}: {str(exc)[:160]}")
        result["status"]="SOURCE_ERROR"
    return result


def audit(shard: int, shards: int, target: Path, now: datetime | None = None):
    if shards<1 or not 0<=shard<shards:
        raise ValueError("Invalid audit shard")
    now=utc_datetime(now or datetime.now(timezone.utc))
    pool=CANDIDATES[shard::shards]
    rows=[]
    for code in pool:
        record=inspect_one(code,now)
        rows.append(record)
        print("COVERAGE_AUDIT",json.dumps(record,ensure_ascii=False),flush=True)
    payload={
        "as_of_utc":now.isoformat(),
        "shard":shard,"shards":shards,
        "previously_enabled":list(ENABLED),
        "candidate_count":len(CANDIDATES),
        "checked":len(rows),
        "recommended_for_review":[r["code"] for r in rows if r["safe_to_promote"]],
        "results":rows,
        "interpretation":"Eligibility only, not proof of future daily availability or rights to republish",
    }
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COVERAGE_AUDIT_SUMMARY",json.dumps(
        {"shard":shard,"checked":len(rows),
         "recommended":payload["recommended_for_review"]},ensure_ascii=False),flush=True)
    return payload


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--shards",type=int,default=4)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();audit(a.shard,a.shards,a.output)


if __name__=="__main__":
    main()
