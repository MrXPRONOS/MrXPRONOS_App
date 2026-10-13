#!/usr/bin/env python3
"""Mise a jour quotidienne 2024-2026, uniquement des matchs termines BSD.

La premiere importation par saison n'est pas répétée. On consulte seulement
les derniers jours (scores retardés et corrections compris), et on fusionne
les donnees dans le JSON prive qui sera ensuite chiffre dans GitHub.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone

from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE, STATE_FILE, _read_json, _write_json
from bsd_history import ingest_events
from bsd_h2h import _team_id, _valid_score, _utc
from free_football_providers import FreeFootballProviders

EARLIEST = date(2024, 1, 1)
LATEST = date(2026, 12, 31)


def eligible_finished(events, *, as_of: date):
    valid = []
    rejected = 0
    for event in events:
        if not isinstance(event, dict) or event.get("id") is None:
            rejected += 1
            continue
        if str(event.get("status") or "").lower() != "finished":
            continue
        home, away = _team_id(event, "home"), _team_id(event, "away")
        if not home or not away or home == away:
            rejected += 1
            continue
        if _valid_score(event.get("home_score")) is None or _valid_score(event.get("away_score")) is None:
            rejected += 1
            continue
        try:
            day = _utc(str(event.get("event_date") or "")).date()
        except (TypeError, ValueError):
            rejected += 1
            continue
        if EARLIEST <= day <= LATEST and day <= as_of:
            valid.append(event)
        else:
            rejected += 1
    return valid, rejected


def _team_name(event, side):
    value = event.get(side + "_team")
    if isinstance(value, dict):
        return str(value.get("name") or value.get("displayName") or "").strip()
    return str(value or event.get(side + "_team_name") or "").strip()


def _fixture_ref(event):
    return {
        "home_team": _team_name(event, "home"),
        "away_team": _team_name(event, "away"),
        "event_date": event.get("event_date"),
    }


def _events_on_day(events, day):
    rows = []
    for event in events:
        if not isinstance(event, dict):
            continue
        try:
            if _utc(str(event.get("event_date") or "")).date() == day:
                rows.append(event)
        except (TypeError, ValueError):
            continue
    return rows


def _free_day_confirmation(hub, day, local_rows):
    if not local_rows:
        return False, 0, 0
    league_hints = []
    for row in local_rows:
        league = row.get("league")
        name = league.get("name") if isinstance(league, dict) else row.get("league_name") or league
        if name:
            league_hints.append(str(name))

    free_rows = []
    for result in hub.day(day, league_hints=league_hints):
        free_rows.extend(result.events)

    matched = 0
    for local in local_rows:
        if hub.best_match(_fixture_ref(local), free_rows, threshold=.68):
            matched += 1
    required = max(1, int(len(local_rows) * .90 + .999))
    return matched >= required, matched, len(free_rows)


def refresh(matches, client, *, as_of=None, days=7, max_pages=5):
    if not 1 <= days <= 14 or not 1 <= max_pages <= 15:
        raise ValueError("days 1-14, max_pages 1-15")
    as_of = as_of or datetime.now(timezone.utc).date()
    if as_of < EARLIEST or as_of > LATEST:
        return matches, {"days_checked": 0, "added": 0, "updated": 0, "rejected": 0,
                         "reason": "outside_2024_2026_window"}
    first = max(EARLIEST, as_of - timedelta(days=days - 1))
    old = {str(row["id"]): row for row in matches if isinstance(row, dict) and row.get("id") is not None}
    merged = list(matches)
    rejected = 0
    checked = 0
    bsd_days_skipped = 0
    free_confirmed_matches = 0
    hub = FreeFootballProviders(session=getattr(client, "session", None))
    for i in range((as_of - first).days + 1):
        day = first + timedelta(days=i)
        local_day = _events_on_day(merged, day)

        # Pour J-2 et plus ancien, une journée locale déjà complète et confirmée
        # par les fournisseurs gratuits ne consomme plus un appel BSD.
        if day <= as_of - timedelta(days=2) and local_day:
            confirmed, matched, free_total = _free_day_confirmation(hub, day, local_day)
            if confirmed and all(str(row.get("status") or "").lower() == "finished" for row in local_day):
                bsd_days_skipped += 1
                free_confirmed_matches += matched
                checked += 1
                print("FREE_ARCHIVE_CONFIRM", day.isoformat(), matched, "/", len(local_day), "free_rows", free_total)
                continue

        batch = client.list_events(day, day, max_pages=max_pages, ttl=0)
        if not batch.complete:
            raise RuntimeError("BSD: %s incomplet (%d/%d). Mise à jour annulée." %
                               (day.isoformat(), len(batch.events), batch.total_reported))
        valid, bad = eligible_finished(batch.events, as_of=as_of)
        rejected += bad
        merged = ingest_events(merged, valid)
        checked += 1
    current = {str(row["id"]): row for row in merged}
    added = sum(k not in old for k in current)
    updated = sum(k in old and current[k] != old[k] for k in current)
    return merged, {
        "days_checked": checked, "added": added, "updated": updated,
        "rejected": rejected, "requests_made": client.requests_made,
        "quota_remaining": client.rate_limit_remaining,
        "bsd_days_skipped": bsd_days_skipped,
        "free_confirmed_matches": free_confirmed_matches,
        "free_provider_calls": dict(hub.calls),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--max-requests", type=int, default=45)
    args = parser.parse_args()
    matches = _read_json(MATCHES_FILE, None)
    state = _read_json(STATE_FILE, None)
    if not isinstance(matches, list) or not matches or not isinstance(state, dict) or state.get("provider") != "BSD":
        parser.error("Restaurer l'archive BSD historique avant d'actualiser.")
    client = BSDClient(max_requests=args.max_requests)
    updated, report = refresh(matches, client, days=args.days, max_pages=args.max_pages)
    if updated != matches:
        _write_json(MATCHES_FILE, updated)
    state["last_daily_refresh"] = datetime.now(timezone.utc).isoformat()
    state["last_daily_refresh_report"] = report
    _write_json(STATE_FILE, state)
    print("BSD_DAILY_REFRESH:", json.dumps({"matches": len(updated), **report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
