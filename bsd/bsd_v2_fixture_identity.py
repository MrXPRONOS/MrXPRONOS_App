"""Fail-closed identity guard for BSD fixtures with different native IDs.

Preserve the native ID and immutable publication ledger. Two records for the
same teams/league within 90 minutes are ambiguous until source verification.
Never choose the higher price or silently switch to another event ID.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import re
import unicodedata

MAX_KICKOFF_DRIFT_SECONDS = 90 * 60


def _utc(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _text(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]", "", normalized.encode("ascii", "ignore").decode().casefold())


def _event_id(match):
    raw = match.get("source_event_id") or match.get("id")
    raw = str(raw or "").removeprefix("bsd:")
    return raw if raw.isdecimal() else None


def _team(match, side):
    obj = match.get(side + "_team")
    team_id = match.get(side + "_team_id")
    if isinstance(obj, dict):
        team_id = team_id or obj.get("id")
        name = obj.get("name")
    else:
        name = obj
    if team_id is not None and str(team_id).strip():
        return ("id", str(team_id))
    cleaned = _text(name)
    return ("name", cleaned) if cleaned else None


def fixture_identity(match):
    """Return (fixture group, kickoff UTC, native ID), or None when incomplete."""
    if not isinstance(match, dict):
        return None
    eid = _event_id(match)
    kickoff = _utc(match.get("event_date"))
    home, away = _team(match, "home"), _team(match, "away")
    league = match.get("league_id")
    if league is not None and str(league).strip():
        league = ("id", str(league))
    else:
        label = match.get("league") or match.get("league_name")
        if isinstance(label, dict):
            label = label.get("name")
        cleaned = _text(label)
        league = ("name", cleaned) if cleaned else None
    if not eid or kickoff is None or home is None or away is None or league is None:
        return None
    return (league, home, away), kickoff, eid


def ambiguous_fixture_ids(matches):
    """All IDs involved in cross-ID collisions, including transitive collisions.

    Compare nearby UTC starts, not only date strings: midnight reschedules
    remain detectable. Same teams in another league/day are distinct.
    """
    groups = defaultdict(list)
    for match in matches or []:
        identity = fixture_identity(match)
        if identity is None:
            continue
        group, kickoff, eid = identity
        groups[group].append((kickoff, eid))
    ambiguous = set()
    for rows in groups.values():
        rows.sort()
        for i, (kickoff, eid) in enumerate(rows):
            for other_time, other_id in rows[i + 1:]:
                if (other_time - kickoff).total_seconds() > MAX_KICKOFF_DRIFT_SECONDS:
                    break
                if other_id != eid:
                    ambiguous.update((eid, other_id))
    return ambiguous


def quarantine_ambiguous(matches):
    """Drop every conflicting event, never arbitrarily pick a priced winner."""
    records = list(matches or [])
    blocked = ambiguous_fixture_ids(records)
    return [m for m in records if not isinstance(m, dict) or _event_id(m) not in blocked], blocked
