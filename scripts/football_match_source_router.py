#!/usr/bin/env python3
"""Per-fixture, per-market data-source router for PREMATCH analysis.

Only provenanced, point-in-time historical features may be selected.
Never mixes metrics from competing sources inside one market family.
Does not call APIs or alter predictions, prices or Telegram.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any

# Heuristic *tie-breakers*, NOT measured model accuracy. Coverage and valid
# observations are stronger gates than discovery order or provider reputation.
PREFERENCE = {
    "goals": ("bsd", "api_football", "espn", "sportscore", "thesportsdb", "openligadb", "football_data", "openfootball"),
    "btts": ("bsd", "api_football", "espn", "sportscore", "football_data", "openfootball", "thesportsdb", "openligadb"),
    "totals": ("bsd", "api_football", "espn", "sportscore", "football_data", "openfootball", "thesportsdb", "openligadb"),
    "corners": ("api_football", "espn", "sportscore", "football_data", "bsd", "thesportsdb", "openligadb", "openfootball"),
    "cards": ("api_football", "espn", "sportscore", "football_data", "bsd", "thesportsdb", "openligadb", "openfootball"),
}
REQUIRED = {
    "goals": ("home_goals_for", "home_goals_against", "away_goals_for", "away_goals_against"),
    "btts": ("home_btts_rate", "away_btts_rate"),
    "totals": ("home_over_2_5_rate", "away_over_2_5_rate"),
    "corners": ("home_corners_avg", "away_corners_avg"),
    "cards": ("home_yellow_cards_avg", "away_yellow_cards_avg"),
}
PROBABILITY_FIELDS = {"home_btts_rate", "away_btts_rate", "home_over_2_5_rate", "away_over_2_5_rate"}
MAX_STALE_HOURS = 168  # 7 days; historical observations must still predate kickoff
MIN_SAMPLE = 5
MIN_KICKOFF_BUFFER = timedelta(seconds=1)


def aware_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def valid_metrics(family: str, metrics: Any) -> bool:
    if not isinstance(metrics, dict):
        return False
    return all(
        type(metrics.get(k)) in (int, float)
        and isfinite(metrics[k])
        and (0 <= metrics[k] <= 1 if k in PROBABILITY_FIELDS else 0 <= metrics[k] <= (15 if family == "goals" else 40))
        for k in REQUIRED[family]
    )


def validate(provider: str, ref: dict, record: Any, kickoff: datetime, family: str) -> tuple[bool, str]:
    if not isinstance(record, dict):
        return False, "no_statistics"
    if record.get("provider_fixture_id") is not None and str(record["provider_fixture_id"]) != str(ref["id"]):
        return False, "fixture_id_mismatch"
    if record.get("phase") != "prematch":
        return False, "not_prematch"
    collected = aware_time(record.get("observed_at"))
    historic_end = aware_time(record.get("history_until"))
    if collected is None or historic_end is None:
        return False, "unverifiable_timestamps"
    if collected >= kickoff or historic_end >= kickoff:
        return False, "future_information"
    if historic_end > collected:
        return False, "history_after_collection"
    if collected < kickoff - timedelta(hours=MAX_STALE_HOURS):
        return False, "stale_snapshot"
    samples = record.get("samples") or {}
    if not isinstance(samples, dict) or type(samples.get("home")) is not int or type(samples.get("away")) is not int:
        return False, "missing_sample_sizes"
    if samples["home"] < MIN_SAMPLE or samples["away"] < MIN_SAMPLE:
        return False, "insufficient_history"
    if samples["home"] > 250 or samples["away"] > 250:
        return False, "implausible_sample_size"
    data = (record.get("families") or {}).get(family)
    if not valid_metrics(family, data):
        return False, "invalid_or_incomplete_family"
    if record.get("verified_identity") is not True:
        return False, "unverified_identity"
    if record.get("license_ok") is not True:
        return False, "unapproved_data_usage"
    return True, ""


def route_fixture(fixture: dict, statistics: dict, *, min_sample: int = MIN_SAMPLE) -> dict:
    """Select strongest eligible provider independently for each family.

    statistics format: {provider: {fixture_id: {phase, observed_at,
        history_until, samples:{home,away}, families:{family:{metric:value}},
        verified_identity:true, license_ok:true}}}.
    """
    kickoff = aware_time(fixture.get("kickoff_utc"))
    sources = fixture.get("sources") or {}
    origin = fixture.get("discovered_by") or next(iter(sources), "")
    reasons = {}
    families = {}
    if (kickoff is None or fixture.get("ambiguous_match") or fixture.get("scores_conflict")
            or fixture.get("league_conflict") or fixture.get("league_verified") is False
            or fixture.get("status", "prematch") != "prematch"):
        cause = "invalid_kickoff_or_identity_conflict"
        return {
            "fixture_key": fixture.get("fixture_key"), "discovered_by": origin,
            "preferred_overall_source": None,
            "families": {f: {"status": "rejected", "reason": cause} for f in REQUIRED},
            "ready_families": [], "needs_more_data": list(REQUIRED),
            "prediction_eligible": False,
        }
    for family in REQUIRED:
        choices = []
        rejected = {}
        for provider, ref in sources.items():
            if not isinstance(ref, dict):
                continue
            sid = str(ref.get("id") or "")
            if not sid:
                rejected[provider] = "missing_stable_source_id"
                continue
            record = (statistics.get(provider) or {}).get(sid)
            valid, reason = validate(provider, ref, record, kickoff, family)
            if not valid:
                rejected[provider] = reason
                continue
            if min_sample > MIN_SAMPLE and min(record["samples"].values()) < min_sample:
                rejected[provider] = "insufficient_history"
                continue
            order = PREFERENCE[family]
            preference = len(order) - order.index(provider) if provider in order else 0
            sample = min(record["samples"]["home"], record["samples"]["away"], 60)
            age_hours = max(0, (kickoff - aware_time(record["observed_at"])).total_seconds() / 3600)
            choices.append((
                (sample, preference, -age_hours, int(provider == origin), provider),
                provider, sid, record,
            ))
        reasons[family] = rejected
        if not choices:
            families[family] = {"status": "missing", "reason": "no_valid_stats", "rejected_providers": rejected}
            continue
        _, winner, sid, record = max(choices)
        families[family] = {
            "status": "ready",
            "provider": winner, "provider_fixture_id": sid,
            "discovery_source": origin,
            "fallback_used": winner != origin,
            "samples": dict(record["samples"]),
            "metrics": {k: record["families"][family][k] for k in REQUIRED[family]},
            "observed_at": record["observed_at"], "history_until": record["history_until"],
            "alternative_providers": sorted(p for _, p, _, _ in choices if p != winner),
            "rejected_providers": rejected,
        }
    ready = [f for f, x in families.items() if x["status"] == "ready"]
    primary = families["goals"].get("provider") if "goals" in ready else next((families[f]["provider"] for f in ready), None)
    return {
        "fixture_key": fixture.get("fixture_key"),
        "discovered_by": origin,
        "preferred_overall_source": primary,
        "families": families,
        "ready_families": ready,
        "needs_more_data": [f for f in REQUIRED if f not in ready],
        # All individual families are research-only until backtested and approved.
        "prediction_eligible": False,
    }


def route_all(fixtures: list[dict], statistics: dict, *, min_sample: int = MIN_SAMPLE) -> tuple[list[dict], dict]:
    routed = [route_fixture(f, statistics, min_sample=min_sample) for f in fixtures]
    result = {
        "fixtures": len(routed),
        "with_any_valid_family": sum(bool(r["ready_families"]) for r in routed),
        "with_goal_family": sum("goals" in r["ready_families"] for r in routed),
        "with_all_families": sum(not r["needs_more_data"] for r in routed),
        "source_selection": {
            family: {provider: sum(r["families"][family].get("provider") == provider for r in routed)
                     for provider in sorted({r["families"][family].get("provider") for r in routed} - {None})}
            for family in REQUIRED
        },
        "model_enabled": False, "telegram_posts": 0,
    }
    return routed, result
