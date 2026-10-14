#!/usr/bin/env python3
"""Read-only real BSD archive coverage validation. Aggregated, privacy-safe report.

Must run on an isolated trusted CI runner. Inputs include decrypted BSD
historical matches, but neither records nor fixture identifiers are logged or
uploaded; no secrets and no HTTP clients are used by this module.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.football_daily_multisource_shadow import compatible
from scripts.football_bsd_private_history import attach
from scripts.football_match_source_router import route_all, aware_time

WINDOW_HOURS = 36


def native_current(public_feed: dict) -> list[dict]:
    """Derive historical comparison candidates from ALREADY published BSD feed."""
    if public_feed.get("source") != "bsd":
        raise ValueError("Unexpected production feed provenance")
    result = []
    for row in public_feed.get("matches", []):
        if not isinstance(row, dict) or row.get("source") != "bsd":
            continue
        ident = str(row.get("id") or "").removeprefix("bsd:")
        if not ident.isdecimal() or int(ident) <= 0:
            continue
        if not aware_time(row.get("event_date")):
            continue
        hid, aid = row.get("home_team_id"), row.get("away_team_id")
        if not isinstance(row.get("home_team"), str) or not isinstance(row.get("away_team"), str):
            continue
        result.append({
            "id": int(ident),
            "home_team": {"name": row["home_team"], "id": hid},
            "away_team": {"name": row["away_team"], "id": aid},
            "home_team_id": hid, "away_team_id": aid,
            "league_name": row.get("league"),
            "league_id": row.get("league_id"),
            "event_date": row["event_date"],
            "status": "finished" if row.get("is_finished") else "notstarted",
        })
    return result


def as_projection(event: dict) -> dict:
    return {
        "home": str(event["home_team"]["name"]),
        "away": str(event["away_team"]["name"]),
        "kickoff_utc": str(event["event_date"]),
        "league": str(event.get("league_name") or ""),
    }


def union_with_bsd(public_union: list[dict], bsd_events: list[dict]) -> tuple[list[dict], dict]:
    """Append BSD published future fixtures, conservatively reusing exact union matches."""
    merged = [dict(f, sources=dict(f.get("sources") or {})) for f in public_union]
    summary = Counter()
    for event in bsd_events:
        native = as_projection(event)
        possible = []
        for i, item in enumerate(merged):
            if "bsd" in item["sources"] or item.get("ambiguous_match") or item.get("league_conflict"):
                continue
            candidate = {
                "home": item.get("home_team", ""), "away": item.get("away_team", ""),
                "kickoff_utc": item.get("kickoff_utc", ""),
                "league": item.get("league_labels", [""])[0] if item.get("league_labels") else "",
            }
            if compatible(native, candidate):
                possible.append(i)
        if len(possible) == 1:
            row = merged[possible[0]]
            row["sources"]["bsd"] = {"id": str(event["id"]), "source_kind": "native_bsd_fixture"}
            row["matched_with_bsd"] = True
            if not row.get("league_labels") and event.get("league_name"):
                row["league_labels"] = [event["league_name"]]
                row["league_verified"] = True
            summary["bsd_joined_existing"] += 1
        elif len(possible) > 1:
            for i in possible:
                merged[i]["ambiguous_match"] = True
            summary["bsd_ambiguous_join"] += 1
        else:
            kickoff = native["kickoff_utc"]
            merged.append({
                "fixture_key": "bsd:public:" + str(event["id"]),
                "discovered_by": "bsd",
                "home_team": native["home"], "away_team": native["away"],
                "kickoff_utc": kickoff,
                "league_labels": [native["league"]] if native["league"] else [],
                "league_verified": bool(native["league"]),
                "sources": {"bsd": {"id": str(event["id"]), "source_kind": "native_bsd_fixture"}},
                "source_count": 1, "scores_conflict": False, "ambiguous_match": False,
                "league_conflict": False, "status": "prematch",
            })
            summary["bsd_added_from_published"] += 1
    return merged, dict(summary)


def measure(public_union: list[dict], public_feed: dict, history: list[dict],
            *, at: datetime | None = None) -> dict:
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("Audit timestamp must be timezone aware")
    current = native_current(public_feed)
    union, joined = union_with_bsd(public_union, current)
    cutoff = at + timedelta(hours=WINDOW_HOURS)
    eligible = [x for x in union if (t := aware_time(x.get("kickoff_utc"))) and at < t <= cutoff]
    raw_before = len(eligible)
    # Explicit authorization is exclusively for this in-memory research pass.
    augmented, snapshots, private = attach(eligible, history, current, as_of=at, explicitly_authorized=True)
    routed, routing = route_all(augmented, snapshots, analysis_at=at)
    assert private["production_modified"] is False and private["secret_archive_exposed"] is False
    return {
        "audit_time_utc": at.isoformat(),
        "scope": "available public providers plus already published BSD fixtures, next 36h only",
        "private_archive": {
            "records_restored": len(history),
            "valid_finished_history": private["historic_match_count"],
        },
        "public_published_bsd_rows_considered": len(current),
        "public_union_input_fixtures": len(public_union),
        "union_total_after_public_bsd_insertion": len(union),
        "future_fixtures_next_36h": raw_before,
        "public_bsd_fixture_joins": joined,
        "private_historical_coverage": {
            "added_statistics": private["attached_fixtures"],
            "native_bsd_fixtures": private["native_fixture_count"],
            "third_party_discovery_bsd_history": private["cross_provider_history_count"],
            "rejections": private["rejection_summary"],
        },
        "routed_stats": {
            "any_valid_family": routing["with_any_valid_family"],
            "goals": routing["with_goal_family"],
            "all_families": routing["with_all_families"],
            "chosen_provider_per_market": routing["source_selection"],
        },
        "test_only": True,
        "no_api_calls_in_private_phase": True,
        "production_model_modified": False,
        "public_data_json_modified": False,
        "private_fixture_ids_written": False,
        "private_archive_uploaded": False,
        "telegram_posts": 0,
        "predictions_published": 0,
        "bsd_v2_performance_benchmark_completed": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--history", required=True, help="restored BSD archive in trusted CI")
    p.add_argument("--union", required=True, help="public fixture union from earlier step")
    p.add_argument("--bsd-site-data", required=True, help="already-published site feed")
    p.add_argument("--out", required=True, help="aggregate counts only; never private rows")
    a = p.parse_args()
    hist = json.loads(Path(a.history).read_text(encoding="utf-8"))
    public = json.loads(Path(a.union).read_text(encoding="utf-8"))
    feed = json.loads(Path(a.bsd_site_data).read_text(encoding="utf-8"))
    if not isinstance(hist, list) or not isinstance(public, list):
        p.error("Expected arrays of historical rows and public fixtures")
    report = measure(public, feed, hist)
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BSD_PRIVATE_AGGREGATE_VALIDATION", json.dumps(report, ensure_ascii=False))
    assert report["private_archive_uploaded"] is False
    assert report["production_model_modified"] is False
    assert report["telegram_posts"] == 0


if __name__ == "__main__":
    main()
