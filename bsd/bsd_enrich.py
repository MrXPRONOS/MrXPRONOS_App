"""Resolve competition names once per generation, never one API call per match."""
from __future__ import annotations
from typing import Any, Dict, List
from bsd_api import BSDClient, BSDAPIError


def _league_id(event: dict):
    value = event.get("league_id")
    if value is None and isinstance(event.get("league"), dict):
        value = event["league"].get("id")
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _present_name(event: dict):
    for key in ("league_name", "competition", "league"):
        value = event.get(key)
        if isinstance(value, dict):
            value = value.get("name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def enrich_leagues(fixtures: List[dict], client: BSDClient) -> Dict[str, int]:
    """Adds league_name and league_id to copies of fixture dicts in-place.

    Returns diagnostics. A metadata outage does not invalidate fixture/H2H data.
    """
    need = [row for row in fixtures if not _present_name(row) and _league_id(row)]
    mapping = {}
    if need:
        try:
            payload = client.get_json("/leagues/", {"limit": 200, "offset": 0}, ttl=3600)
            if isinstance(payload, dict) and isinstance(payload.get("results"), list):
                for row in payload["results"]:
                    if isinstance(row, dict) and row.get("id") is not None:
                        try:
                            league = int(row["id"])
                        except (TypeError, ValueError):
                            continue
                        name = str(row.get("name") or row.get("display_name") or "").strip()
                        if name:
                            mapping[league] = name
        except BSDAPIError:
            # Data source still valid; log count, but do not fabricate a league name.
            pass
    resolved = 0
    missing = 0
    for row in fixtures:
        lid = _league_id(row)
        if lid:
            row["league_id"] = lid
        if _present_name(row):
            resolved += 1
        elif lid in mapping:
            row["league_name"] = mapping[lid]
            resolved += 1
        else:
            missing += 1
    return {"league_names_resolved": resolved, "league_names_missing": missing}
