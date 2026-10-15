#!/usr/bin/env python3
"""Safe production canary: match BSD native fixtures to CC0 football calendars.

No predictions, odds, publisher, checkout write permission, secrets in logs,
Telegram or external-derived synthetic IDs. Never modify data.json.
Only exact date, ordered names, unique fixture, verified official BSD league
name produce a corroboration. UTC calendar day may exclude local-midnight
games on purpose: silence is safer than guessing.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

CALENDAR_CODES = ("en.1", "en.2", "de.1", "es.1", "fr.1", "it.1", "nl.1", "pt.1")
MAX_BSD_CALLS = 12
MAX_METADATA = 6


def clean(value):
    if not isinstance(value, str):
        return ""
    s = unicodedata.normalize("NFKD", value.casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def ident(value):
    if type(value) is int and 0 < value < 7_000_000_000_000_000:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal() and not value.startswith("0"):
        number = int(value)
        return number if 0 < number < 7_000_000_000_000_000 else None
    return None


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None


def team(row, side):
    value = row.get(f"{side}_team")
    return clean(value.get("name")) if isinstance(value, dict) else clean(value)


def extract_calendar(payload, code):
    if code not in CALENDAR_CODES or not isinstance(payload, dict):
        raise ValueError("Unapproved calendar")
    games = payload.get("matches")
    if not isinstance(games, list) or len(games) > 1000:
        raise ValueError("Calendar size/schema")
    result = []
    for match in games:
        if not isinstance(match, dict):
            raise ValueError("Invalid calendar row")
        day = str(match.get("date") or "")
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", day):
            continue
        h, a = clean(match.get("team1")), clean(match.get("team2"))
        if h and a and h != a:
            result.append((day, h, a, code))
    return result


def native_record(row, now):
    if not isinstance(row, dict):
        return None
    bid = ident(row.get("id"))
    league_value = row.get("league")
    league_id = ident(row.get("league_id"))
    if league_id is None and isinstance(league_value, dict):
        league_id = ident(league_value.get("id"))
    home, away = team(row, "home"), team(row, "away")
    kickoff = timestamp(row.get("event_date"))
    status = str(row.get("status") or "").lower()
    if not bid or not league_id or not home or not away or home == away or not kickoff:
        return None
    if kickoff <= now or status not in ("upcoming", "notstarted"):
        return None
    return bid, league_id, kickoff.date().isoformat(), home, away


def candidate_leagues(calendar, native, *, at):
    by_pair = defaultdict(set)
    for day, h, a, code in calendar:
        by_pair[(day, h, a)].add(code)
    result = set()
    for row in native:
        value = native_record(row, at)
        if value is None:
            continue
        _, league_id, day, h, a = value
        if len(by_pair.get((day, h, a), ())) == 1:
            result.add(league_id)
    return sorted(result)


def corroborate(calendar, native, names, *, at):
    if at.tzinfo is None:
        raise ValueError("Timezone-aware clock required")
    by_pair = defaultdict(set)
    for day, home, away, league_code in calendar:
        by_pair[(day, home, away)].add(league_code)
    pairs = defaultdict(set)
    counts = Counter()
    seen_native = set()
    for row in native:
        record = native_record(row, at)
        if record is None:
            counts["invalid_or_non_future_native"] += 1
            continue
        bid, lid, day, home, away = record
        if bid in seen_native:
            counts["duplicate_native_id"] += 1
            continue
        seen_native.add(bid)
        leagues = by_pair.get((day, home, away), set())
        if len(leagues) != 1:
            counts["not_unique_in_cc0_calendar"] += 1
            continue
        counts["matched_cc0_day_and_ordered_teams"] += 1
        expected = next(iter(leagues))
        official = names.get(lid)
        if not isinstance(official, str) or not official:
            counts["official_league_name_unavailable"] += 1
            continue
        # Exact competition names (not inferred from numeric IDs or fuzzy).
        # For CC0 filenames the sanctioned expected full labels are listed.
        canonical = {
            "en.1": "premier league", "en.2": "championship",
            "de.1": "bundesliga", "es.1": "la liga", "fr.1": "ligue 1",
            "it.1": "serie a", "nl.1": "eredivisie", "pt.1": "primeira liga",
        }
        if clean(official) != canonical[expected]:
            counts["official_league_name_mismatch"] += 1
            continue
        pairs[(day, home, away, expected)].add(bid)
    valid = sum(len(ids) == 1 for ids in pairs.values())
    duplicates = sum(len(ids) > 1 for ids in pairs.values())
    return {
        "cc0_calendar_rows": len(calendar),
        "native_events_considered": len(native),
        "cc0_day_team_pairs_matched": counts["matched_cc0_day_and_ordered_teams"],
        "officially_corrobated_unique_native_matches": valid,
        "duplicate_native_fixture_conflicts": duplicates,
        "rejections": dict(sorted(counts.items())),
        "monitor_only": True,
        "production_publication_enabled": False,
        "bookmaker_odds_requested": False,
        "raw_match_data_or_ids_exported": False,
    }


def run():
    import requests
    from bsd.bsd_api import BSDClient
    import tempfile

    token = os.environ.get("BSD_API_KEY")
    if not token:
        raise RuntimeError("BSD_API_KEY secret missing, stop (never fallback to public fake event IDs)")
    now = datetime.now(timezone.utc)
    session = requests.Session()
    calendar = []
    for code in CALENDAR_CODES:
        url = f"https://raw.githubusercontent.com/openfootball/football.json/master/2026-27/{code}.json"
        response = session.get(url, timeout=16, allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError("One of the eight CC0 calendars unavailable")
        if len(response.content) > 2_000_000:
            raise RuntimeError("CC0 calendar too large")
        calendar.extend(extract_calendar(response.json(), code))
    with tempfile.TemporaryDirectory() as directory:
        os.environ["FOOTBALL_MULTI_SOURCE"] = "0"
        client = BSDClient(api_key=token, cache_dir=Path(directory), max_requests=MAX_BSD_CALLS,
                           min_interval=0.2, max_retries=1)
        native = []
        for offset in (1, 2):
            date = (now + timedelta(days=offset)).date()
            page = client.list_events(date, date, max_pages=3, ttl=0)
            if not page.complete:
                raise RuntimeError("Incomplete BSD native fixture page: fail closed")
            native.extend(page.events)
        league_ids = candidate_leagues(calendar, native, at=now)
        names = {}
        for lid in league_ids[:MAX_METADATA]:
            details = client.get_json(f"/leagues/{lid}/", ttl=0)
            if isinstance(details, dict) and ident(details.get("id")) == lid:
                name = details.get("name") or details.get("league_name")
                if isinstance(name, str):
                    names[lid] = name
        report = corroborate(calendar, native, names, at=now)
        report["cc0_files_loaded"] = len(CALENDAR_CODES)
        report["native_league_metadata_checked"] = len(names)
        report["native_league_ids_omitted_by_budget"] = max(0, len(league_ids)-MAX_METADATA)
        report["bsd_api_calls"] = client.requests_made
        report["bsd_api_budget"] = MAX_BSD_CALLS
    print("BSD_CC0_READONLY_CANARY", json.dumps(report, sort_keys=True))
    output = os.environ.get("GITHUB_STEP_SUMMARY")
    if output:
        with open(output, "a", encoding="utf8") as file:
            file.write("## BSD/CC0 canary — read only\n\n")
            file.write(f"Official BSD event/country competition corroborations: **{report['officially_corrobated_unique_native_matches']}**\n\n")
            file.write(f"Calendar records checked: {report['cc0_calendar_rows']}; BSD calls: {report['bsd_api_calls']}/{MAX_BSD_CALLS}.\n\n")
            file.write("No bookmaker prices, predictions, data.json writes or Telegram sends.\n")


if __name__ == "__main__":
    run()
