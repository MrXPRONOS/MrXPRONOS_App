#!/usr/bin/env python3
"""Research-only documented SportScore upcoming filter coverage audit.

Queries /api/v1/fixtures/ with the documented status=upcoming parameter only
on days where the original general query reached its limit of 200 events.
Counts additional references in aggregate; NEVER merges filtered records into
the model, writes raw responses, claims completeness, or posts predictions.
Do not try undocumented page/offset APIs or rotate identities to evade limits.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bsd.free_football_sources import SPORTSCORE_FIXTURES, _sportscore_rows
from scripts.football_daily_multisource_shadow import BudgetSession

MAX_PROBE_DAYS = 4
SPORTSCORE_PAGE_CAP = 200


def inspect_filtered(baseline: list[dict], health: dict, *,
                     session=None, max_requests: int = 4) -> dict:
    """A capped, read-only comparison; returning no fixture/club-level details."""
    if not isinstance(baseline, list) or not isinstance(health, dict):
        raise ValueError("Expected baseline fixtures list and source-health dictionary")
    if not 1 <= max_requests <= MAX_PROBE_DAYS:
        raise ValueError("Probe budget must be 1..4")
    days = health.get("days")
    if not isinstance(days, list) or not 1 <= len(days) <= MAX_PROBE_DAYS:
        raise ValueError("Source-health must have 1..4 days")
    if len(set(days)) != len(days):
        raise ValueError("Duplicate day in health")
    for day in days:
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("Invalid calendar day")

    sources = health.get("sources") or {}
    if not isinstance(sources, dict):
        raise ValueError("Invalid source-health structure")
    known = set()
    for item in baseline:
        if not isinstance(item, dict):
            continue
        references = item.get("sources")
        if not isinstance(references, dict):
            continue
        origin = references.get("sportscore")
        if isinstance(origin, dict) and str(origin.get("id") or "").strip():
            known.add(str(origin["id"]).strip())

    audit_session = session if session is not None else BudgetSession(max_requests)
    summary = {}
    reasons = Counter()
    for day in days:
        source_day = sources.get(day) or {}
        provider_health = source_day.get("provider_health") or {}
        original = provider_health.get("sportscore") or {}
        reported = original.get("reported", 0)
        if type(reported) is not int or reported < 0:
            raise ValueError("Invalid original SportScore reported count")
        record = {
            "general_query_reported": reported,
            "general_query_at_cap": reported >= SPORTSCORE_PAGE_CAP,
            "filtered_returned": 0,
            "filtered_pre_match": 0,
            "matched_general_source_ids": 0,
            "not_in_general_source_ids": 0,
            "unusable_or_conflicting_source_ids": 0,
            "filtered_also_at_cap": False,
            "attempted": False,
            "successful": False,
        }
        summary[day] = record
        if reported < SPORTSCORE_PAGE_CAP:
            reasons["not_at_cap"] += 1
            continue
        if reasons["attempted"] >= max_requests:
            reasons["budget_exhausted"] += 1
            continue
        reasons["attempted"] += 1
        record["attempted"] = True
        try:
            response = audit_session.get(
                SPORTSCORE_FIXTURES,
                params={"sport": "football", "date": day,
                        "status": "upcoming", "limit": SPORTSCORE_PAGE_CAP},
                headers={"Accept": "application/json",
                         "User-Agent": "MrXPRONOS-ReadOnlySourceAudit/1.0",
                         "Authorization": None},
                timeout=(6, 16), allow_redirects=False)
            status = getattr(response, "status_code", None)
            if type(status) is not int or status != 200:
                raise ValueError("Unexpected HTTP status (including redirect)")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Unexpected response envelope")
            values = payload.get("matches")
            if not isinstance(values, list) or len(values) > SPORTSCORE_PAGE_CAP:
                raise ValueError("Invalid or oversized filtered matches array")
            record["filtered_returned"] = len(values)
            record["filtered_also_at_cap"] = len(values) >= SPORTSCORE_PAGE_CAP
            rows = _sportscore_rows(payload)
            filtered_ids = set()
            conflicting_ids = set()
            signatures = {}
            for row in rows:
                # Count only pre-match events whose UTC date matches the
                # requested day. This NEVER changes a production fixture.
                from scripts.football_daily_multisource_shadow import kickoff
                stamp = kickoff(row.get("event_date"))
                if stamp is None or stamp.date().isoformat() != day or row.get("state") != "pre":
                    continue
                record["filtered_pre_match"] += 1
                source_id = str(row.get("provider_event_id") or "").strip()
                home = str(row.get("home_team") or "").strip()
                away = str(row.get("away_team") or "").strip()
                if not source_id or not home or not away:
                    record["unusable_or_conflicting_source_ids"] += 1
                    continue
                signature = (home, away, stamp.isoformat())
                if source_id in signatures and signatures[source_id] != signature:
                    conflicting_ids.add(source_id)
                else:
                    signatures[source_id] = signature
                filtered_ids.add(source_id)
            verified_ids = filtered_ids - conflicting_ids
            record["unusable_or_conflicting_source_ids"] += len(conflicting_ids)
            record["matched_general_source_ids"] = len(verified_ids & known)
            record["not_in_general_source_ids"] = len(verified_ids - known)
            record["successful"] = True
            reasons["successful"] += 1
        except Exception as exc:
            # Do not print URLs or response bodies; never log credentials.
            record["error_category"] = type(exc).__name__
            reasons["fetch_or_schema_failure"] += 1
    return {
        "provider": "sportscore",
        "endpoint_filter": "status=upcoming",
        "documented_filter_only": True,
        "undocumented_pagination_used": False,
        "competition_or_fixture_identity_inferred": False,
        "raw_event_data_written": False,
        "new_source_references_proven_as_official_match_ids": False,
        "new_events_added_to_prediction_pipeline": 0,
        "calendar_matching_or_odds_approved": False,
        "general_page_cap": SPORTSCORE_PAGE_CAP,
        "probe_max_requests": max_requests,
        "attempts": reasons["attempted"],
        "per_day": summary,
        "reasons": dict(sorted(reasons.items())),
        "possible_incomplete_coverage": any(
            r["general_query_at_cap"] or r["filtered_also_at_cap"]
            for r in summary.values()),
        "no_production_writes": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--baseline-health", required=True)
    parser.add_argument("--max-http", type=int, default=4)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    output = Path(args.report).resolve()
    if output == (ROOT / "data.json").resolve():
        parser.error("Production data.json cannot be replaced")
    baseline = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    health = json.loads(Path(args.baseline_health).read_text(encoding="utf-8"))
    result = inspect_filtered(baseline, health, max_requests=args.max_http)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SPORTSCORE_FILTERED_COVERAGE_AUDIT", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
