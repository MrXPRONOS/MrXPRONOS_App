#!/usr/bin/env python3
"""Adapt legally reusable history and other-provider fixtures to BSD V2's INPUT SCHEMA.

NO change to bsd_v2_core.py, its formulas, calibration, market logic or thresholds.
Separate history index for third-party fixtures prevents changing existing BSD
team ratings/global priors. External provider IDs stay in provenance only.

Historical OpenFootball observations have date-only precision. A past result
is conservatively attributed to 23:59 UTC on its reported day. Thus it cannot
be used for a same-day prediction or as part of earlier-day same-day H2H.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, date, time, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
if str(ROOT / "bsd") not in sys.path: sys.path.insert(0, str(ROOT / "bsd"))

from scripts.football_history_shadow import canonical_team
from scripts.football_history_features import competition
from scripts.football_match_source_router import aware_time
from scripts.football_multi_api_history_inputs import (ingest as ingest_provider_history,
                                                      trusted_private_bsd_rows)
from scripts.football_verified_identity_crosswalk import (generate as confirmed_aliases,
                                                          resolve as resolve_confirmed_alias)
from bsd_v2_core import V2History, estimate_goals, predict_v2
from bsd_h2h import local_h2h

PROVIDER = "openfootball"
MAX_JS_SAFE = (1 << 53) - 1
# Distinct high numeric namespaces, disjoint from real BSD IDs and one another.
HISTORY_START, FIXTURE_START, TEAM_START, LEAGUE_START = (
    7_000_000_000_000_000, 7_500_000_000_000_000,
    8_000_000_000_000_000, 8_500_000_000_000_000,
)
SLOT = 400_000_000_000_000
H2H_YEARS = 10


def numbered(start: int, token: str) -> int:
    ident = start + (int.from_bytes(sha256(token.encode("utf-8")).digest()[:8], "big") % SLOT)
    assert 0 < ident <= MAX_JS_SAFE
    return ident


def league_label(value: str) -> str:
    return competition(str(value or ""))


def safe_names(fixture: dict) -> tuple[str, str, str] | None:
    if (fixture.get("ambiguous_match") or fixture.get("scores_conflict")
            or fixture.get("league_conflict") or fixture.get("league_verified") is False
            or fixture.get("status") != "prematch"):
        return None
    labels = {league_label(v) for v in (fixture.get("league_labels") or []) if league_label(v)}
    if len(labels) != 1:
        return None
    home = canonical_team(str(fixture.get("home_team") or ""))
    away = canonical_team(str(fixture.get("away_team") or ""))
    if not home or not away or home == away:
        return None
    return next(iter(labels)), home, away


def ids(league: str, team: str) -> int:
    # Deliberately league-scoped: identical club names in different national,
    # reserves, women's, or junior leagues must not become the same team.
    return numbered(TEAM_START, league + "|" + team)


def normalize_history(rows: list[dict], *,
                      accepted_sources: frozenset[str] = frozenset({PROVIDER}),
                      team_aliases: dict | None = None) -> tuple[list[dict], dict]:
    """BSD-native-format history, preserving ALL verified providers per result.

    Multisource rows may only be passed after a dedicated rights/timestamp
    validation step. Original fixture IDs are metadata; hashed internal IDs
    are deterministic and distinct from authentic BSD IDs.
    """
    seen: dict[tuple, dict | None] = {}
    rejected = Counter()
    for row in rows:
        if not isinstance(row, dict) or row.get("source") not in accepted_sources or row.get("status") != "finished":
            rejected["not_approved_result"] += 1
            continue
        try:
            league = league_label(row["league"])
            dt = date.fromisoformat(str(row["match_date"]))
            home = resolve_confirmed_alias(league,str(row["home_team"]),team_aliases or {})
            away = resolve_confirmed_alias(league,str(row["away_team"]),team_aliases or {})
            hs, aws = row.get("home_score"), row.get("away_score")
            source = str(row["source"])
        except (KeyError, TypeError, ValueError):
            rejected["invalid_history_record"] += 1
            continue
        if (not league or not home or not away or home == away
                or type(hs) is not int or type(aws) is not int
                or not (0 <= hs <= 30 and 0 <= aws <= 30)):
            rejected["invalid_teams_or_scores"] += 1
            continue
        actual = aware_time(row.get("kickoff_utc"))
        if actual is not None and actual.date() != dt:
            rejected["historical_date_mismatch"] += 1
            continue
        # Uncertain date-only archive cannot be placed in an earlier hour.
        moment = actual or datetime.combine(dt, time(23, 59), timezone.utc)
        key = (league, dt, home, away)
        if key not in seen:
            ident = numbered(HISTORY_START, f"match|{league}|{dt}|{home}|{away}")
            seen[key] = {
                "id": ident, "status": "finished",
                "event_date": moment.isoformat(),
                "league_id": numbered(LEAGUE_START, league), "league_name": league,
                "home_team_id": ids(league,home), "away_team_id": ids(league,away),
                "home_team": {"id":ids(league,home), "name":row["home_team"]},
                "away_team": {"id":ids(league,away), "name":row["away_team"]},
                "home_score":hs, "away_score":aws,
                "_history_source":source, "_history_sources":[source],
                "_date_precision":"minute" if actual else "day",
                "_original_provider_ids":{source: str(row.get("source_id") or "")},
            }
        elif seen[key] is not None:
            old = seen[key]
            if (old["home_score"], old["away_score"]) != (hs, aws):
                seen[key] = None
                rejected["conflicting_duplicate_quarantined"] += 1
            elif actual and old["_date_precision"] == "minute" and abs(
                    (aware_time(old["event_date"])-actual).total_seconds()) > 120*60:
                seen[key] = None
                rejected["conflicting_kickoff_quarantined"] += 1
            else:
                if source not in old["_history_sources"]:
                    old["_history_sources"].append(source)
                    old["_original_provider_ids"][source] = str(row.get("source_id") or "")
                else:
                    rejected["duplicate_dropped"] += 1
                # Use only more accurate timestamps when existing date-only.
                if actual and old["_date_precision"] == "day":
                    old["event_date"] = actual.isoformat()
                    old["_date_precision"] = "minute"
    events = [event for event in seen.values() if event is not None]
    events.sort(key=lambda e: (e["event_date"],e["id"]))
    return events, {
        "input_results":len(rows), "usable_historic_matches":len(events),
        "distinct_sources":sorted({p for e in events for p in e["_history_sources"]}),
        "multi_provider_corroborated":sum(len(e["_history_sources"]) > 1 for e in events),
        "quarantined_reasons":dict(sorted(rejected.items())),
        "original_ids_preserved_only_in_private_research":True,
        "independent_upstream_verification_assumed":False,
    }


def adapt_daily(fixtures: list[dict], history: list[dict], *, as_of: datetime,
                min_recent: int = 4, team_aliases: dict | None = None) -> tuple[list[dict], dict]:
    """Adapt external discoveries only. Reject duplicates already carrying BSD ID."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)
    team_counts = Counter()
    team_latest = {}
    for row in history:
        when = aware_time(row["event_date"])
        if when is None or when+timedelta(hours=4) >= as_of:
            continue
        for side in ("home", "away"):
            key = (int(row["league_id"]),int(row[side+"_team_id"]))
            team_counts[key] += 1
            if key not in team_latest or when > team_latest[key]:
                team_latest[key] = when
    models=[]
    stats=Counter()
    for item in fixtures:
        sources = item.get("sources") or {}
        if not isinstance(sources, dict) or not sources:
            stats["no_discovery_source"] += 1
            continue
        if "bsd" in sources:
            stats["already_in_bsd_do_not_duplicate"] += 1
            continue
        names = safe_names(item)
        if names is None:
            stats["unverified_competition_or_teams"] += 1
            continue
        league, home, away = names
        home = resolve_confirmed_alias(league,home,team_aliases or {})
        away = resolve_confirmed_alias(league,away,team_aliases or {})
        if home == away:
            stats["alias_caused_identical_teams"] += 1
            continue
        kickoff = aware_time(item.get("kickoff_utc"))
        if kickoff is None or kickoff <= as_of:
            stats["not_future"] += 1
            continue
        lid = numbered(LEAGUE_START,league)
        hid, aid = ids(league,home), ids(league,away)
        if min(team_counts[(lid,hid)],team_counts[(lid,aid)]) < min_recent:
            stats["insufficient_prior_matches"] += 1
            continue
        if max((kickoff-team_latest[(lid,hid)]).days,(kickoff-team_latest[(lid,aid)]).days) > 240:
            stats["stale_prior_matches"] += 1
            continue
        # This is intentionally a local derived ID: original per-provider refs remain.
        synth_id = numbered(FIXTURE_START, f"{league}|{kickoff.isoformat()}|{home}|{away}")
        models.append({
            "id":synth_id,
            "home_team":{"id":hid,"name":item["home_team"]},
            "away_team":{"id":aid,"name":item["away_team"]},
            "home_team_id":hid, "away_team_id":aid,
            "event_date":kickoff.isoformat(),
            "status":"notstarted",
            "league_id":lid, "league_name":league,
            "home_score":None, "away_score":None,
            "_external_source":"|".join(sorted(sources)),
            "_original_fixture_refs":sources,
            "_derived_research_id":True,
            "_fixture_key":item.get("fixture_key"),
            "_history_provider":PROVIDER,
        })
        stats["adapted_external"] += 1
    return models, {"input_discovered_fixtures":len(fixtures),
                    "ready_for_unchanged_core":len(models),
                    "ignored":dict(sorted(stats.items())),
                    "model_code_changed":False}


def h2h_report(event: dict, history: list[dict], *, as_of: datetime | None = None) -> dict:
    """Uses project's EXISTING H2H aggregation; never feeds new model weight."""
    confirmed=history
    if as_of is not None:
        confirmed=[r for r in history if (stamp:=aware_time(r.get("event_date"))) is not None
                   and stamp+timedelta(hours=4) < as_of]
    result=local_h2h(
        confirmed,event["home_team_id"],event["away_team_id"],
        event["event_date"],years=H2H_YEARS,recent_limit=10)
    return {
        "total_previous_meetings":result["total_matches"],
        "home_wins":result["home_wins"],
        "draws":result["draws"],
        "away_wins":result["away_wins"],
        "available_for_diagnostics_only":True,
    }


def evaluate_existing_v2(fixtures: list[dict], history: list[dict], *,
                         as_of: datetime, calibration=None, policy=None,
                         rho: float = 0.0, btts_model=None, total_model=None,
                         dc_model=None) -> tuple[list[dict], dict]:
    """Run exact existing predict_v2 code path, WITHOUT pricing or publishing.

    No new model or formula. Full published-quality prediction requires SAME
    trained BSD model artifacts, bookmaker prices, and publication guardrails.
    """
    at=as_of.astimezone(timezone.utc)
    available=[e for e in history if (dt:=aware_time(e.get("event_date"))) is not None
               and dt+timedelta(hours=4)<at]
    index=V2History(available)
    output=[]
    reasons=Counter()
    for event in fixtures:
        h2h=h2h_report(event,available,as_of=at)
        estimated, why=estimate_goals(event,index)
        if estimated is None:
            reasons["goals:"+str(why)]+=1
            output.append({"_research_id":event["id"],"status":"missing_history",
                           "h2h":h2h,"reason":why})
            continue
        decision,reason=predict_v2(event,index,clock=at,
            calibration=calibration,quality_policy=policy,rho=rho,
            mode="reliability",odds_by_market={},require_odds=False,
            btts_model=btts_model,total_model=total_model,dc_model=dc_model)
        if decision is None:
            reasons["predict_v2:"+str(reason)]+=1
        else:
            reasons["model_candidate"]+=1
        output.append({
            "_research_id":event["id"],
            "source":event["_external_source"],
            "status":"model_candidate" if decision else "model_abstained",
            "h2h":h2h,
            "expected_goals":estimated,
            "internal_candidate_key":(decision or {}).get("prediction",{}).get("key"),
            "reason":reason,
            "published":False,
            "unchanged_v2_calculation":True,
        })
    return output,{
        "examined":len(fixtures),
        "v2_candidate_count":reasons["model_candidate"],
        "v2_abstentions":dict(sorted(reasons.items())),
        "h2h_nonzero_fixtures":sum(x.get("h2h",{}).get("total_previous_meetings",0)>0 for x in output),
        "calculation_module_modified":False,
        "core_predict_v2_function_used":True,
        "production_published":False,
        "telegram_posts":0,
        "price_qualification_performed":False,
    }


def main() -> None:
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--historical-jsonl",help="Licensed OpenFootball historical results")
    p.add_argument("--private-bsd-history-json",help="Decrypted private BSD archive, local trusted execution only")
    p.add_argument("--bsd-public-identity-feed",help="Public BSD data.json with original team and league IDs")
    p.add_argument("--authorize-bsd-private-internal-use",action="store_true",help="Requires rights and trusted runner")
    p.add_argument("--daily-union",required=True)
    p.add_argument("--provider-history-snapshots",help="Offline provider history snapshots, never auto-fetched")
    p.add_argument("--provider-rights-manifest",help="Explicit legal authorization per source for commercial historical model use")
    p.add_argument("--analysis-at",required=True,help="ISO timezone-aware validation clock")
    p.add_argument("--report",required=True)
    a=p.parse_args()
    when=aware_time(a.analysis_at)
    if when is None: p.error("--analysis-at must be timezone-aware")
    fixtures=json.loads(Path(a.daily_union).read_text(encoding="utf-8"))
    if not (a.historical_jsonl or a.private_bsd_history_json or a.provider_history_snapshots):
        p.error("At least one authorized historical input is required")
    if a.historical_jsonl:
        with open(a.historical_jsonl,encoding="utf-8") as handle:
            hist=[json.loads(x) for x in handle if x.strip()]
    else:
        hist=[]
    multi_report={"loaded_historical_rows":0,"no_api_called":True}
    approved=frozenset({PROVIDER})
    if bool(a.private_bsd_history_json) != bool(a.authorize_bsd_private_internal_use):
        p.error("Private BSD archive requires BOTH path and explicit internal-use authorization")
    if a.bsd_public_identity_feed and not a.private_bsd_history_json:
        p.error("--bsd-public-identity-feed requires a trusted local private archive")
    if a.private_bsd_history_json:
        private_archive=json.loads(Path(a.private_bsd_history_json).read_text(encoding="utf-8"))
        if not isinstance(private_archive,list):
            p.error("Private BSD archive must contain a list of historical matches")
        feed=(json.loads(Path(a.bsd_public_identity_feed).read_text(encoding="utf-8"))
              if a.bsd_public_identity_feed else None)
        private_rows,private_stats=trusted_private_bsd_rows(
            private_archive,as_of=when,explicitly_authorized=True,public_bsd_feed=feed)
        hist.extend(private_rows)
        approved=frozenset({*approved,"bsd"})
        multi_report["private_bsd"]=private_stats
    if bool(a.provider_history_snapshots) != bool(a.provider_rights_manifest):
        p.error("Both historical snapshots and provider-rights-manifest are required")
    if a.provider_history_snapshots:
        snapshots=json.loads(Path(a.provider_history_snapshots).read_text(encoding="utf-8"))
        rights=json.loads(Path(a.provider_rights_manifest).read_text(encoding="utf-8"))
        additions,multi_report=ingest_provider_history(snapshots,rights,as_of=when)
        approved=frozenset({*approved,*multi_report["permitted_provider_rows"].keys()})
        hist.extend(additions)
    alias_map,alias_quality=confirmed_aliases(hist)
    archive,archive_report=normalize_history(hist,accepted_sources=approved,team_aliases=alias_map)
    ready,ready_report=adapt_daily(fixtures,archive,as_of=when,team_aliases=alias_map)
    # Raw per-event calculations remain only IN MEMORY. Never write match IDs
    # or individual picks in logs or artifacts.
    _,analysis_report=evaluate_existing_v2(ready,archive,as_of=when)
    report={
        "historical":archive_report,
        "verified_team_aliases":alias_quality,
        "multi_api_historical_inputs":multi_report,
        "fixtures":ready_report,
        "bsd_v2_core":analysis_report,
        "used_h2h_existing_function":True,
        "all_inputs_to_existing_v2_format":True,
        "published":False,
    }
    destination=Path(a.report)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("BSD_V2_UNCHANGED_CORE_EXTERNAL_H2H",json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
