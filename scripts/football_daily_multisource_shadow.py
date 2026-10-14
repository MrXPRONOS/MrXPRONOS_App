#!/usr/bin/env python3
"""Read-only daily multi-provider fixture index for BSD V2 research.

Uses *existing* ESPN, SportScore, TheSportsDB, OpenLigaDB adapters. BSD events
may be read from a local snapshot but never fetched or published by this tool.
No odds, no picks, no historical prediction accuracy is inferred from agreement.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from bsd.free_football_sources import collect_free_day
from scripts.football_history_shadow import normalized, canonical_team

ALLOWED = ("bsd", "api_football", "espn", "sportscore", "thesportsdb", "openligadb")
ALLOWED_HOSTS = {
    "site.api.espn.com", "sportscore.com",
    "www.thesportsdb.com", "api.openligadb.de",
}


def kickoff(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        when = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        # Ambiguous local kickoff is not safe for cross-provider matching.
        return None
    return when.astimezone(timezone.utc)


def team_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("displayName") or "")
    return str(value or "")


def clean_row(row: dict, source: str) -> dict | None:
    home = team_name(row.get("home_team"))
    away = team_name(row.get("away_team"))
    dt = kickoff(row.get("event_date") or row.get("date") or row.get("start_time"))
    if not dt or not normalized(home) or not normalized(away) or normalized(home) == normalized(away):
        return None
    return {
        "source": source,
        "source_id": str(row.get("provider_event_id") or row.get("id") or ""),
        "home": home,
        "away": away,
        "kickoff_utc": dt.isoformat(),
        "league": str(row.get("league") or row.get("league_name") or ""),
        "state": str(row.get("state") or row.get("status") or ""),
        "home_score": row.get("home_score") if type(row.get("home_score")) is int else None,
        "away_score": row.get("away_score") if type(row.get("away_score")) is int else None,
    }



def api_football_rows(payload: Any) -> list[dict]:
    """Adapt a separately obtained API-Football /fixtures JSON response.

    Do not perform any additional API-Football calls: LIVE workflow already has
    its own strictly limited account quota and request schedule.
    """
    if isinstance(payload, dict):
        payload = payload.get("response", [])
    if not isinstance(payload, list):
        return []
    result = []
    for value in payload:
        if not isinstance(value, dict):
            continue
        fixture, teams, goals, league = (
            value.get("fixture") or {}, value.get("teams") or {},
            value.get("goals") or {}, value.get("league") or {},
        )
        if not isinstance(fixture, dict) or not isinstance(teams, dict):
            continue
        home, away = teams.get("home") or {}, teams.get("away") or {}
        if not isinstance(home, dict) or not isinstance(away, dict):
            continue
        if not isinstance(goals, dict):
            goals = {}
        if not isinstance(league, dict):
            league = {}
        status = str((fixture.get("status") or {}).get("short") or "").upper()
        state = "post" if status in ("FT", "AET", "PEN") else "pre" if status in ("NS", "TBD") else "in"
        result.append({
            "id": fixture.get("id"), "provider_event_id": fixture.get("id"),
            "home_team": home.get("name"), "away_team": away.get("name"),
            "event_date": fixture.get("date"), "state": state,
            "home_score": goals.get("home"), "away_score": goals.get("away"),
            "league": league.get("name") or "",
        })
    return result


def compatible(a: dict, b: dict, minutes: int = 90) -> bool:
    if canonical_team(a["home"]) != canonical_team(b["home"]) or canonical_team(a["away"]) != canonical_team(b["away"]):
        return False
    da, db = kickoff(a["kickoff_utc"]), kickoff(b["kickoff_utc"])
    return da is not None and db is not None and abs((da - db).total_seconds()) <= minutes * 60


def merge(snapshots: dict[str, Any], *, bsd_events: list | None = None) -> tuple[list[dict], dict]:
    # Canonical normalized names and UTC kickoff window; no unreviewed fuzzy match.
    rows = []
    health = {}
    for provider in ALLOWED:
        if provider == "bsd":
            provider_rows = bsd_events or []
            error = ""
        else:
            snap = snapshots.get(provider)
            provider_rows = (snap.rows if hasattr(snap, "rows") else snap.get("rows", [])) if snap is not None else []
            error = (snap.error if hasattr(snap, "error") else snap.get("error", "")) if snap is not None else "not queried"
        valid = [x for x in (clean_row(row, provider) for row in provider_rows) if x]
        health[provider] = {
            "reported": len(provider_rows), "valid": len(valid),
            "rejected": len(provider_rows) - len(valid), "error": str(error)[:160],
        }
        # Same provider must not be treated as multiple independent sources.
        unique = {}
        for row in valid:
            key = (row["source_id"], row["kickoff_utc"], normalized(row["home"]), normalized(row["away"]))
            unique[key] = row
        rows += list(unique.values())
    # Quality order affects canonical display only, never predicted win probabilities.
    priority = {name: index for index, name in enumerate(ALLOWED)}
    rows.sort(key=lambda r: (priority[r["source"]], r["kickoff_utc"], r["home"], r["away"]))
    groups: list[dict] = []
    ambiguities = []
    for row in rows:
        candidates = [g for g in groups if row["source"] not in g["providers"] and compatible(g["anchor"], row)]
        if len(candidates) != 1:
            if len(candidates) > 1:
                ambiguities.append({"source": row["source"], "source_id": row["source_id"], "candidate_ids": [g["anchor"]["source_id"] for g in candidates]})
            groups.append({"anchor": row, "providers": {row["source"]: row}, "ambiguous": len(candidates) > 1})
        else:
            candidates[0]["providers"][row["source"]] = row
    fixtures = []
    for group in groups:
        providers = group["providers"]
        anchor = group["anchor"]
        final_scores = {(r["home_score"], r["away_score"]) for r in providers.values() if r["state"].lower() in ("post", "finished", "ft", "completed") and r["home_score"] is not None and r["away_score"] is not None}
        scores_conflict = len(final_scores) > 1
        leagues = sorted({r["league"] for r in providers.values() if r["league"]})
        fixtures.append({
            "home_team": anchor["home"], "away_team": anchor["away"],
            "kickoff_utc": anchor["kickoff_utc"], "league_labels": leagues,
            "sources": {provider: {"id": item["source_id"], "kickoff_utc": item["kickoff_utc"], "state": item["state"]} for provider, item in sorted(providers.items())},
            "source_count": len(providers), "scores_conflict": scores_conflict,
            "ambiguous_match": group["ambiguous"],
            "eligible_for_model": False,  # feature compatibility / out-of-sample test needed
            "matched_with_bsd": "bsd" in providers,
        })
    fixtures.sort(key=lambda row: (row["kickoff_utc"], row["home_team"], row["away_team"]))
    stats = {
        "total_unique_fixtures": len(fixtures),
        "providers": health,
        "corroborated_by_two_or_more": sum(f["source_count"] >= 2 for f in fixtures),
        "bsd_matches_corrobated": sum(f["matched_with_bsd"] and f["source_count"] >= 2 for f in fixtures),
        "score_conflicts": sum(f["scores_conflict"] for f in fixtures),
        "ambiguous_joins": len(ambiguities),
        "ambiguities": ambiguities[:50],
        "model_input_enabled": False, "telegram_posts": 0,
    }
    return fixtures, stats


class BudgetSession:
    """Share a single capped requests session; reject unknown hosts and redirects."""
    def __init__(self, max_requests: int = 12):
        import requests
        self.session = requests.Session()
        self.limit = max_requests
        self.calls = Counter()
        self.total = 0

    def get(self, url: str, **kwargs):
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        if urlparse(url).scheme != "https" or host not in ALLOWED_HOSTS:
            raise ValueError("Provider outside allowlist")
        if self.total >= self.limit:
            raise RuntimeError("HTTP request budget reached")
        self.calls[host] += 1
        self.total += 1
        kwargs["allow_redirects"] = False
        return self.session.get(url, **kwargs)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--day", default=date.today().isoformat())
    p.add_argument("--snapshots", help="Offline fixture snapshots JSON keyed by provider; no network")
    p.add_argument("--bsd-fixtures", help="Optional private BSD local list JSON, never uploaded")
    p.add_argument("--api-football-fixtures", help="Offline JSON /fixtures response; no new API calls")
    p.add_argument("--max-http", type=int, default=12)
    p.add_argument("--out", required=True, help="Research-only output, not data.json")
    p.add_argument("--report", required=True)
    args = p.parse_args()
    day = date.fromisoformat(args.day)
    bsd_events = json.loads(Path(args.bsd_fixtures).read_text(encoding="utf-8")) if args.bsd_fixtures else None
    if bsd_events is not None and not isinstance(bsd_events, list):
        p.error("--bsd-fixtures must be a list")
    if args.snapshots:
        snapshots = json.loads(Path(args.snapshots).read_text(encoding="utf-8"))
        calls = {}
    else:
        if not 1 <= args.max_http <= 24:
            p.error("--max-http must be 1..24")
        session = BudgetSession(args.max_http)
        snapshots = collect_free_day(session, day, include_espn=True)
        calls = dict(session.calls)
    if args.api_football_fixtures:
        payload = json.loads(Path(args.api_football_fixtures).read_text(encoding="utf-8"))
        snapshots["api_football"] = {"rows": api_football_rows(payload), "error": ""}
    fixtures, report = merge(snapshots, bsd_events=bsd_events)
    report.update({"day": day.isoformat(), "http_requests": calls, "total_http_requests": sum(calls.values())})
    for path, data in ((args.out, fixtures), (args.report, report)):
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "ambiguities"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
