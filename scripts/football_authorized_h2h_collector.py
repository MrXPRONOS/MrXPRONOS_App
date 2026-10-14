#!/usr/bin/env python3
"""Quota-capped, LICENSE-GATED SportScore H2H history acquisition for BSD V2.

Uses existing football adapters, only for unresolved PREMATCH fixtures.
Other providers are handled by offline licensed history snapshots; this
collector never invents results, bypasses API protections, or posts bets.

Output is a PRIVATE provider snapshot suitable for
football_external_bsd_v2_adapter.py --provider-history-snapshots.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from bsd.free_football_sources import fetch_sportscore_h2h, fetch_sportscore_team
from scripts.football_daily_multisource_shadow import BudgetSession, kickoff
from scripts.football_multi_api_history_inputs import permitted

MAX_PAIRS=4
MAX_HTTP=12


def collect(fixtures: list[dict], licenses: dict, *,
            now: datetime | None = None,
            session=None, fetcher=None, team_fetcher=None,
            max_pairs: int = MAX_PAIRS,
            max_http: int = MAX_HTTP) -> tuple[list[dict],dict]:
    if not permitted("sportscore",licenses):
        return [], {"status":"rights_not_authorized","requests":0,"pairs_attempted":0,
                    "finished_history_rows":0,"no_model_calculation_changed":True}
    if not 1<=max_pairs<=12 or not 3<=max_http<=24:
        raise ValueError("H2H rate limit out of bounds")
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timestamp must be offset-aware")
    session=session or BudgetSession(max_http)
    fetcher=fetcher or fetch_sportscore_h2h
    team_fetcher=team_fetcher or fetch_sportscore_team
    chosen=set()
    cached_team_games={}
    out=[]
    metrics=Counter()
    for match in fixtures:
        if len(chosen)>=max_pairs:
            break
        if (not isinstance(match,dict) or match.get("status") != "prematch"
                or match.get("ambiguous_match") or match.get("league_conflict")
                or match.get("scores_conflict") or match.get("league_verified") is False):
            metrics["ineligible_fixture"]+=1
            continue
        sources=match.get("sources") or {}
        if not isinstance(sources,dict) or "bsd" in sources:
            metrics["already_bsd_or_no_source"]+=1
            continue
        when=kickoff(match.get("kickoff_utc"))
        home,away=match.get("home_team"),match.get("away_team")
        if (when is None or when<=now or not isinstance(home,str)
                or not isinstance(away,str) or not home.strip() or not away.strip()):
            metrics["not_future_or_missing_team"]+=1
            continue
        key=(home.strip().casefold(),away.strip().casefold())
        if key in chosen:
            continue
        chosen.add(key)
        try:
            candidates=[]
            for team in (home,away):
                keyname=team.strip().casefold()
                if keyname not in cached_team_games:
                    cached_team_games[keyname]=team_fetcher(session,team,limit=12)
                    metrics["team_history_lookups"]+=1
                candidates.extend(cached_team_games[keyname] or [])
            hits=fetcher(session,home,away,limit=20)
            metrics["pairs_attempted"]+=1
            metrics["h2h_results_received"]+=len(hits or [])
            candidates.extend(hits or [])
            for event in candidates:
                if (isinstance(event,dict) and
                        event.get("home_score") is not None and
                        event.get("away_score") is not None and
                        event.get("league") and event.get("provider_event_id")):
                    # Source identity and scores are STILL checked by the
                    # separate license-gated finished-result ingester.
                    out.append(event)
        except Exception as exc:
            metrics["error_"+type(exc).__name__]+=1
            if "budget" in str(exc).lower() or "exceeded" in str(exc).lower():
                break
    # A fixture can be returned by home-team, away-team and H2H endpoints.
    # Never count it multiple times or silently accept contradictions.
    keyed={}
    for item in out:
        ident=str(item["provider_event_id"])
        evidence=(str(item.get("home_team")),str(item.get("away_team")),
                  str(item.get("event_date")),str(item.get("league")),
                  item.get("home_score"),item.get("away_score"))
        if ident not in keyed:
            keyed[ident]=(evidence,item)
        elif keyed[ident] is not None and keyed[ident][0]!=evidence:
            keyed[ident]=None
            metrics["contradictory_provider_event"]+=1
    deduped=[entry[1] for entry in keyed.values() if entry is not None]
    metrics["duplicate_historical_rows_removed"]=len(out)-len(deduped)
    cap=getattr(session,"total",0)
    return ([{"provider":"sportscore","observed_at":now.isoformat(),"rows":deduped}]
            if out else []), {
                "status":"authorized_research_only",
                "requests":cap,
                "pairs_attempted":metrics["pairs_attempted"],
                "raw_h2h_rows_with_scores":metrics["h2h_results_received"],
                "team_history_lookups":metrics["team_history_lookups"],
                "distinct_historical_rows_with_scores":len(deduped),
                "skipped":dict(sorted(metrics.items())),
                "max_http":max_http,
                "no_model_calculation_changed":True,
                "results_must_pass_status_identity_and_time_validation":True,
                "production_published":False,
            }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--fixtures",required=True)
    p.add_argument("--rights-manifest",required=True)
    p.add_argument("--private-out",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--max-pairs",type=int,default=MAX_PAIRS)
    p.add_argument("--max-http",type=int,default=MAX_HTTP)
    a=p.parse_args()
    fixtures=json.loads(Path(a.fixtures).read_text(encoding="utf-8"))
    rights=json.loads(Path(a.rights_manifest).read_text(encoding="utf-8"))
    if not isinstance(fixtures,list) or not isinstance(rights,dict):
        p.error("Fixtures must be a list and rights manifest a map")
    if Path(a.private_out).resolve()==(ROOT/"data.json").resolve():
        p.error("Cannot overwrite the production feed")
    if not permitted("sportscore",rights):
        p.error("SportScore history/model/commercial rights not confirmed; zero requests made")
    snapshots,report=collect(fixtures,rights,max_pairs=a.max_pairs,max_http=a.max_http)
    path=Path(a.private_out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(snapshots,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    path.chmod(0o600)
    out=Path(a.report)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LICENSED_SPORTSCORE_H2H_RESEARCH",json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
