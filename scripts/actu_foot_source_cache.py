#!/usr/bin/env python3
"""Cache Neon très court des sources Actu Foot.

Il mutualise les appels des runners full/lifecycle sans remplacer la timeline
canonique Neon ni les caches propres aux fournisseurs.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import requests
try:
    from scripts.neon_rest_compat import NeonRestSession
except ModuleNotFoundError:
    from neon_rest_compat import NeonRestSession

_SHARED_SNAPSHOT_FIELDS = (
    "source", "id", "provider_event_id", "home_team", "away_team",
    "home_team_id", "away_team_id", "home_logo", "away_logo",
    "home_score", "away_score", "home_shootout_score", "away_shootout_score",
    "minute", "period", "state", "status_detail", "event_date", "league",
    "venue", "attendance", "espn_id", "espn_url", "sportscore_slug",
)


def _config() -> tuple[str, str]:
    base = "neon://private" if os.getenv("NEON_DATABASE_URL") else ""
    key = "server" if os.getenv("NEON_DATABASE_URL") else ""
    return base, key


def fetch_shared_source_snapshot(
    session: requests.Session,
    fixture_day: date,
) -> list[dict] | None:
    base, key = _config()
    if not base or not key:
        return None
    session = NeonRestSession(session)
    snapshot_key = "football:" + fixture_day.isoformat()
    try:
        response = session.get(
            base + "/rest/v1/actu_foot_source_snapshots",
            params={
                "select": "payload,expires_at",
                "snapshot_key": "eq." + snapshot_key,
                "expires_at": "gt." + datetime.now(timezone.utc).isoformat(),
                "limit": "1",
            },
            headers={"apikey": key, "Authorization": "Bearer " + key},
            timeout=(4, 8),
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return None
        payload = rows[0].get("payload")
        if not isinstance(payload, list):
            return None
        result = [item for item in payload if isinstance(item, dict)]
        print("ACTU_FOOT_SOURCE_SNAPSHOT_HIT", fixture_day.isoformat(), len(result))
        return result
    except (requests.RequestException, ValueError):
        return None


def persist_shared_source_snapshot(
    session: requests.Session,
    fixture_day: date,
    rows: list[dict],
) -> None:
    base, key = _config()
    if not base or not key or not rows:
        return
    session = NeonRestSession(session)
    try:
        ttl = max(30, min(180, int(os.getenv("FOOTBALL_SHARED_SNAPSHOT_TTL", "150"))))
    except ValueError:
        ttl = 150
    now = datetime.now(timezone.utc)
    safe_rows = [
        {field: row.get(field) for field in _SHARED_SNAPSHOT_FIELDS if row.get(field) is not None}
        for row in rows if isinstance(row, dict)
    ]
    sources = sorted({
        str(row.get("source") or "") for row in safe_rows if row.get("source")
    })
    payload = {
        "snapshot_key": "football:" + fixture_day.isoformat(),
        "fixture_day": fixture_day.isoformat(),
        "payload": safe_rows,
        "sources": sources,
        "fetched_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
    }
    try:
        response = session.post(
            base + "/rest/v1/actu_foot_source_snapshots",
            params={"on_conflict": "snapshot_key"},
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=payload,
            timeout=(4, 8),
        )
        response.raise_for_status()
        print("ACTU_FOOT_SOURCE_SNAPSHOT_STORED", fixture_day.isoformat(), len(safe_rows))
    except requests.RequestException as exc:
        print("ACTU_FOOT_SOURCE_SNAPSHOT_SKIP", type(exc).__name__)
