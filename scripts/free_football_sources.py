#!/usr/bin/env python3
"""Free football providers shared by Mr XPRONOS.

Quality/reliability rank (data quality, not fetch cost):
  1. BSD          96/100 - structured commercial feed + betting odds, quota constrained.
  2. ESPN         94/100 - rich live/event data, public site endpoints, no contractual SLA.
  3. SportScore   86/100 - documented free live API, 60s edge cache, attribution required.
  4. TheSportsDB  78/100 - documented/stable V1 API, free tier heavily result-limited.
  5. OpenLigaDB   72/100 - fully open/community DB, very reliable on high-quality leagues,
                           but coverage varies by competition.

Fetch policy is deliberately different: FREE sources first, BSD only for gaps/odds.
"""
from __future__ import annotations

import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

SPORTSCORE_BASE = "https://sportscore.com"
TSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"
OPENLIGA_BASE = "https://api.openligadb.de"

PROVIDER_RANK = {
    "bsd": {"quality": 96, "reliability": 95, "cost": "quota"},
    "espn": {"quality": 94, "reliability": 89, "cost": "free"},
    "sportscore": {"quality": 86, "reliability": 84, "cost": "free"},
    "thesportsdb": {"quality": 78, "reliability": 82, "cost": "free_limited"},
    "openligadb": {"quality": 72, "reliability": 76, "cost": "free"},
}
FREE_FETCH_ORDER = ("espn", "sportscore", "thesportsdb", "openligadb")

_CACHE: dict[str, tuple[float, Any]] = {}


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _number(value: Any) -> int | float | None:
    if value in (None, "", "-", "null"):
        return None
    try:
        n = float(str(value).replace("%", "").replace(",", "."))
        return int(n) if n.is_integer() else n
    except (TypeError, ValueError):
        return None


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _cached_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    ttl: float = 60.0,
    timeout: tuple[int, int] = (7, 18),
    headers: dict[str, str] | None = None,
) -> Any:
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    key = url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] <= ttl:
        return cached[1]
    try:
        response = session.get(
            url,
            params=params,
            timeout=timeout,
            headers=headers or {
                "User-Agent": "MrXPRONOS-FreeFootball/1.0",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        _CACHE[key] = (time.monotonic(), payload)
        return payload
    except (requests.RequestException, ValueError) as exc:
        if cached:
            return cached[1]
        print("FREE_PROVIDER_ERROR", url, type(exc).__name__, str(exc)[:120])
        return None


def _canonical(
    *,
    source: str,
    source_id: Any,
    home: Any,
    away: Any,
    event_date: Any,
    home_score: Any = None,
    away_score: Any = None,
    status: Any = "",
    league: Any = "",
    home_logo: Any = "",
    away_logo: Any = "",
    slug: Any = "",
    raw: Any = None,
) -> dict | None:
    home = _text(home)
    away = _text(away)
    if not home or not away:
        return None
    state_raw = _norm(status)
    if any(x in state_raw for x in ("finished", "full time", "after penalties", "ft")):
        state = "post"
    elif any(x in state_raw for x in ("live", "in progress", "1st half", "2nd half", "half time", "halftime")):
        state = "in"
    else:
        state = "pre"
    return {
        "source": source,
        "id": f"{source}:{source_id or slug or _norm(home+'-'+away)}",
        "source_match_id": str(source_id or ""),
        "home_team": home,
        "away_team": away,
        "home_score": _number(home_score),
        "away_score": _number(away_score),
        "state": state,
        "status": "finished" if state == "post" else "live" if state == "in" else "scheduled",
        "status_detail": _text(status),
        "minute": _minute_value(status) or 0,
        "event_date": event_date,
        "league": _text(league),
        "home_logo": _text(home_logo),
        "away_logo": _text(away_logo),
        "provider_slug": _text(slug),
        "provider_quality": PROVIDER_RANK[source]["quality"],
        "raw": raw if isinstance(raw, dict) else {},
    }


def fetch_sportscore_day(
    session: requests.Session,
    day: date,
    *,
    status: str | None = None,
) -> list[dict]:
    params: dict[str, Any] = {
        "sport": "football",
        "date": day.isoformat(),
        "limit": 200,
        "src": "mrxpronos",
    }
    if status in {"live", "finished", "upcoming"}:
        params["status"] = status
    payload = _cached_json(
        session,
        f"{SPORTSCORE_BASE}/api/v1/fixtures/",
        params=params,
        ttl=55.0 if day == datetime.now(timezone.utc).date() else 900.0,
    )
    rows = []
    if isinstance(payload, dict):
        rows = payload.get("matches") or payload.get("fixtures") or payload.get("results") or payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    out: list[dict] = []
    for item in rows if isinstance(rows, list) else []:
        if not isinstance(item, dict):
            continue
        home_obj = item.get("home_team") if isinstance(item.get("home_team"), dict) else {}
        away_obj = item.get("away_team") if isinstance(item.get("away_team"), dict) else {}
        comp = item.get("competition") if isinstance(item.get("competition"), dict) else {}
        match = _canonical(
            source="sportscore",
            source_id=item.get("id") or item.get("match_id"),
            home=item.get("home") or item.get("home_name") or home_obj.get("name"),
            away=item.get("away") or item.get("away_name") or away_obj.get("name"),
            event_date=item.get("time") or item.get("start_time") or item.get("kickoff") or item.get("date"),
            home_score=item.get("home_score") if item.get("home_score") is not None else item.get("score_home"),
            away_score=item.get("away_score") if item.get("away_score") is not None else item.get("score_away"),
            status=" ".join(filter(None, (
                _text(item.get("status")),
                _text(item.get("status_text")),
            ))),
            league=item.get("league") or item.get("competition_name") or comp.get("name"),
            home_logo=item.get("home_logo") or home_obj.get("logo"),
            away_logo=item.get("away_logo") or away_obj.get("logo"),
            slug=item.get("slug"),
            raw=item,
        )
        if match:
            out.append(match)
    return out


def fetch_sportscore_detail(session: requests.Session, slug: str) -> dict:
    slug = _text(slug)
    if not slug:
        return {}
    payload = _cached_json(
        session,
        f"{SPORTSCORE_BASE}/api/v1/match/",
        params={"sport": "football", "slug": slug, "src": "mrxpronos"},
        ttl=55.0,
    )
    if not isinstance(payload, dict):
        return {}
    return payload.get("match") if isinstance(payload.get("match"), dict) else payload


def fetch_thesportsdb_day(session: requests.Session, day: date) -> list[dict]:
    payload = _cached_json(
        session,
        f"{TSDB_BASE}/eventsday.php",
        params={"d": day.isoformat(), "s": "Soccer"},
        ttl=120.0 if day == datetime.now(timezone.utc).date() else 1800.0,
    )
    rows = payload.get("events") if isinstance(payload, dict) else []
    out: list[dict] = []
    for item in rows if isinstance(rows, list) else []:
        if not isinstance(item, dict):
            continue
        ts = item.get("strTimestamp")
        if not ts and item.get("dateEvent"):
            ts = f"{item.get('dateEvent')}T{item.get('strTime') or '00:00:00'}Z"
        match = _canonical(
            source="thesportsdb",
            source_id=item.get("idEvent"),
            home=item.get("strHomeTeam"),
            away=item.get("strAwayTeam"),
            event_date=ts,
            home_score=item.get("intHomeScore"),
            away_score=item.get("intAwayScore"),
            status=" ".join(filter(None, (
                _text(item.get("strStatus")),
                _text(item.get("strProgress")),
            ))),
            league=item.get("strLeague"),
            home_logo=item.get("strHomeTeamBadge") or item.get("strHomeTeamLogo"),
            away_logo=item.get("strAwayTeamBadge") or item.get("strAwayTeamLogo"),
            raw=item,
        )
        if match:
            out.append(match)
    return out


def fetch_thesportsdb_details(session: requests.Session, event_id: str) -> dict[str, Any]:
    event_id = re.sub(r"\D", "", str(event_id or ""))
    if not event_id:
        return {}
    result: dict[str, Any] = {}
    endpoints = {
        "event": "lookupevent.php",
        "stats": "lookupeventstats.php",
        "timeline": "lookuptimeline.php",
        "lineup": "lookuplineup.php",
    }
    for key, endpoint in endpoints.items():
        payload = _cached_json(
            session,
            f"{TSDB_BASE}/{endpoint}",
            params={"id": event_id},
            ttl=120.0,
        )
        if isinstance(payload, dict):
            result[key] = payload
    return result


def _openliga_season(day: date) -> str:
    return str(day.year if day.month >= 7 else day.year - 1)


def fetch_openligadb_day(session: requests.Session, day: date, *, max_leagues: int = 8) -> list[dict]:
    season = _openliga_season(day)
    leagues = _cached_json(
        session,
        f"{OPENLIGA_BASE}/getavailableleagues/{season}",
        ttl=6 * 3600.0,
    )
    if not isinstance(leagues, list):
        return []

    preferred = (
        "bundesliga", "premier league", "champions league", "europa league",
        "conference league", "laliga", "la liga", "dfb", "nations league",
        "weltmeister", "world cup",
    )
    selected = []
    trusted_shortcuts = {
        "bl1", "bl2", "bl3", "ucl", "dfb", "wm26",
        "fbl1", "fbl2", "fef", "dfbnat2526",
    }
    for league in leagues:
        if not isinstance(league, dict):
            continue
        name = _norm(league.get("leagueName") or league.get("name"))
        shortcut = _text(league.get("leagueShortcut"))
        if not shortcut:
            continue
        sport_obj = league.get("sport") if isinstance(league.get("sport"), dict) else {}
        sport_name = _norm(sport_obj.get("sportName") or league.get("sportName"))
        if sport_name and not any(x in sport_name for x in ("football", "soccer", "fussball")):
            continue
        quality_raw = _number(league.get("leagueQuality") or league.get("qualityIndex"))
        quality = int(quality_raw) if quality_raw is not None else 90
        known = shortcut.lower() in trusted_shortcuts or any(term in name for term in preferred)
        if known and (quality_raw is None or quality >= 90):
            selected.append((quality, shortcut, league))
    selected.sort(key=lambda x: (-x[0], x[1]))

    out: list[dict] = []
    for _, shortcut, league in selected[:max_leagues]:
        payload = _cached_json(
            session,
            f"{OPENLIGA_BASE}/getmatchdata/{shortcut}/{season}",
            ttl=300.0,
        )
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            when = _moment(item.get("matchDateTimeUTC") or item.get("matchDateTime"))
            if not when or when.date() != day:
                continue
            team1 = item.get("team1") if isinstance(item.get("team1"), dict) else {}
            team2 = item.get("team2") if isinstance(item.get("team2"), dict) else {}
            results = item.get("matchResults") if isinstance(item.get("matchResults"), list) else []
            final = next((x for x in results if isinstance(x, dict) and int(x.get("resultOrderID") or 0) == 2), None)
            if final is None and results:
                final = results[-1] if isinstance(results[-1], dict) else None
            goals = item.get("goals") if isinstance(item.get("goals"), list) else []
            match = _canonical(
                source="openligadb",
                source_id=item.get("matchID"),
                home=team1.get("teamName"),
                away=team2.get("teamName"),
                event_date=when.isoformat(),
                home_score=(final or {}).get("pointsTeam1"),
                away_score=(final or {}).get("pointsTeam2"),
                status="finished" if item.get("matchIsFinished") else "scheduled",
                league=league.get("leagueName"),
                home_logo=team1.get("teamIconUrl"),
                away_logo=team2.get("teamIconUrl"),
                raw={**item, "goals": goals},
            )
            if match:
                out.append(match)
    return out


def _similar(a: str, b: str) -> float:
    aa = set(_norm(a).split())
    bb = set(_norm(b).split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def merge_provider_matches(rows: list[dict]) -> list[dict]:
    """De-duplicate sources, retaining provider provenance and best available fields."""
    ordered = sorted(
        [x for x in rows if isinstance(x, dict)],
        key=lambda x: -int(x.get("provider_quality") or PROVIDER_RANK.get(x.get("source"), {}).get("quality", 0)),
    )
    merged: list[dict] = []
    for row in ordered:
        when = _moment(row.get("event_date"))
        best_idx = -1
        best_score = 0.0
        for i, current in enumerate(merged):
            current_when = _moment(current.get("event_date"))
            if when and current_when and abs((when-current_when).total_seconds()) > 4 * 3600:
                continue
            score = (_similar(row.get("home_team", ""), current.get("home_team", "")) +
                     _similar(row.get("away_team", ""), current.get("away_team", ""))) / 2
            if score > best_score:
                best_idx, best_score = i, score
        if best_idx < 0 or best_score < 0.68:
            row = dict(row)
            row["provider_sources"] = [row.get("source")]
            merged.append(row)
            continue
        current = merged[best_idx]
        sources = list(dict.fromkeys((current.get("provider_sources") or [current.get("source")]) + [row.get("source")]))
        for key in ("home_score", "away_score", "home_logo", "away_logo", "league", "status_detail", "event_date"):
            if current.get(key) in (None, "", 0) and row.get(key) not in (None, ""):
                current[key] = row[key]
        # Live/final state can be upgraded by corroboration.
        state_order = {"pre": 0, "in": 1, "post": 2}
        if state_order.get(row.get("state"), -1) > state_order.get(current.get("state"), -1):
            current["state"] = row["state"]
        current["provider_sources"] = sources
        current.setdefault("provider_ids", {})[str(row.get("source"))] = row.get("source_match_id")
        if row.get("provider_slug"):
            current.setdefault("provider_slugs", {})[str(row.get("source"))] = row.get("provider_slug")
    return merged


def collect_free_day(
    session: requests.Session,
    day: date,
    *,
    include_openliga: bool = True,
) -> list[dict]:
    rows: list[dict] = []
    rows.extend(fetch_sportscore_day(session, day))
    rows.extend(fetch_thesportsdb_day(session, day))
    if include_openliga:
        rows.extend(fetch_openligadb_day(session, day))
    return merge_provider_matches(rows)


def _player_name(value: Any) -> str:
    if isinstance(value, str):
        return _text(value)
    if not isinstance(value, dict):
        return ""
    nested = value.get("player") if isinstance(value.get("player"), dict) else value.get("athlete")
    if isinstance(nested, dict):
        value = {**value, **nested}
    return _text(
        value.get("name") or value.get("displayName") or value.get("strPlayer")
        or value.get("player_name") or value.get("fullName")
    )


def _minute_value(value: Any) -> int | None:
    raw = _text(value)
    if not raw:
        return None
    match = re.search(r"(\d+)(?:\D*\+\D*(\d+))?", raw)
    if not match:
        return None
    return int(match.group(1)) + int(match.group(2) or 0)


def _lineup_side(value: Any) -> list[str]:
    rows = value if isinstance(value, list) else []
    players: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            starter = row.get("starter")
            position = _text(row.get("type") or row.get("role") or row.get("position")).lower()
            # When the provider explicitly labels substitutes, exclude them.
            if starter is False or "sub" in position or "bench" in position:
                continue
        name = _player_name(row)
        if name and name not in players:
            players.append(name)
    return players[:11] if len(players) >= 11 else []


def _extract_lineups_generic(payload: dict) -> dict[str, list[str]]:
    result = {"home": [], "away": []}
    candidate = (
        payload.get("lineups") or payload.get("lineup") or payload.get("rosters")
        or payload.get("starting_lineups")
    )
    if isinstance(candidate, dict):
        for side in ("home", "away"):
            value = candidate.get(side) or candidate.get(side + "_team") or candidate.get(side + "Team")
            if isinstance(value, dict):
                value = value.get("players") or value.get("lineup") or value.get("roster") or []
            result[side] = _lineup_side(value)
    elif isinstance(candidate, list):
        for group in candidate:
            if not isinstance(group, dict):
                continue
            side = _text(group.get("homeAway") or group.get("side") or group.get("team_type")).lower()
            if side not in result:
                team = _text(group.get("team") or group.get("teamName")).lower()
                if "home" in team:
                    side = "home"
                elif "away" in team:
                    side = "away"
            if side in result:
                rows = group.get("players") or group.get("lineup") or group.get("roster") or []
                result[side] = _lineup_side(rows)
    return result


def _extract_timeline_generic(payload: dict) -> list[dict]:
    rows = (
        payload.get("timeline") or payload.get("events") or payload.get("incidents")
        or payload.get("match_events") or []
    )
    if isinstance(rows, dict):
        rows = rows.get("events") or rows.get("timeline") or rows.get("items") or []
    if not isinstance(rows, list):
        return []
    out: list[dict] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        typ = _text(
            item.get("type") or item.get("event") or item.get("event_type")
            or item.get("incidentType") or item.get("strTimeline")
        ).lower()
        minute_text = _text(
            item.get("minute") or item.get("time") or item.get("elapsed")
            or item.get("strTimelineDetail") or item.get("clock")
        )
        minute = _minute_value(minute_text)
        player = _player_name(item)
        team = item.get("team") if isinstance(item.get("team"), dict) else {}
        team_name = _text(team.get("name") or item.get("team_name") or item.get("strTeam"))
        kind = ""
        if "goal" in typ or item.get("scoring") is True:
            kind = "goal"
        elif "yellow" in typ or "red card" in typ or typ in {"card", "booking"}:
            kind = "card"
        elif "sub" in typ:
            kind = "substitution"
        if not kind:
            continue
        row = {
            "kind": kind,
            "player": player,
            "minute": minute,
            "minute_total": minute,
            "minute_text": minute_text,
            "team": team_name,
            "penalty": "pen" in typ or bool(item.get("penalty")),
            "own_goal": "own goal" in typ or bool(item.get("own_goal") or item.get("ownGoal")),
            "label": _text(item.get("type") or item.get("event") or item.get("strTimeline")),
        }
        if kind == "goal":
            assist = _text(
                item.get("assist") or item.get("assist_name") or item.get("strAssist")
            )
            row["assists"] = [assist] if assist else []
        out.append(row)
    out.sort(key=lambda x: (x.get("minute_total") is None, x.get("minute_total") or 999))
    return out


def _extract_stats_generic(payload: dict) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {"home": {}, "away": {}}
    aliases = {
        "corners": {"corner", "corners", "cornerkicks", "woncorners"},
        "shots": {"shots", "totalshots"},
        "shots_on_target": {"shotsontarget", "shotsongoal"},
        "possession": {"possession", "possessionpct", "ballpossession"},
        "fouls": {"fouls", "foulscommitted"},
        "offsides": {"offsides", "offside"},
        "saves": {"saves", "goalkeepersaves"},
        "yellow_cards": {"yellowcards", "yellowcard"},
        "red_cards": {"redcards", "redcard"},
    }
    stats = payload.get("statistics") or payload.get("stats") or payload.get("match_statistics") or {}
    if isinstance(stats, list):
        for row in stats:
            if not isinstance(row, dict):
                continue
            key = re.sub(r"[^a-z0-9]", "", _text(row.get("name") or row.get("type") or row.get("label")).lower())
            for target, names in aliases.items():
                if key in names:
                    result["home"][target] = row.get("home") if row.get("home") is not None else row.get("home_value")
                    result["away"][target] = row.get("away") if row.get("away") is not None else row.get("away_value")
    elif isinstance(stats, dict):
        home = stats.get("home") if isinstance(stats.get("home"), dict) else {}
        away = stats.get("away") if isinstance(stats.get("away"), dict) else {}
        for side, source in (("home", home), ("away", away)):
            for raw_name, value in source.items():
                key = re.sub(r"[^a-z0-9]", "", _text(raw_name).lower())
                for target, names in aliases.items():
                    if key in names:
                        result[side][target] = value
    return result


def extract_sportscore_enrichment(detail: dict) -> dict[str, Any]:
    if not isinstance(detail, dict):
        return {}
    root = detail.get("match") if isinstance(detail.get("match"), dict) else detail
    timeline = _extract_timeline_generic(root)
    return {
        "lineups": _extract_lineups_generic(root),
        "timeline": timeline,
        "goals": [x for x in timeline if x.get("kind") == "goal"],
        "cards": [x for x in timeline if x.get("kind") == "card"],
        "substitutions": [x for x in timeline if x.get("kind") == "substitution"],
        "stats": _extract_stats_generic(root),
        "player_stats": root.get("player_stats") if isinstance(root.get("player_stats"), list) else [],
        "info": {
            "venue": _text(root.get("venue") or root.get("stadium")),
            "attendance": _number(root.get("attendance")),
            "referees": [
                _text(root.get("referee"))
            ] if _text(root.get("referee")) else [],
        },
    }


def extract_thesportsdb_enrichment(details: dict) -> dict[str, Any]:
    if not isinstance(details, dict):
        return {}
    lineup_payload = details.get("lineup") if isinstance(details.get("lineup"), dict) else {}
    timeline_payload = details.get("timeline") if isinstance(details.get("timeline"), dict) else {}
    stats_payload = details.get("stats") if isinstance(details.get("stats"), dict) else {}

    lineup_rows = (
        lineup_payload.get("lineup") or lineup_payload.get("lineups")
        or lineup_payload.get("event") or lineup_payload.get("events") or []
    )
    lineups = {"home": [], "away": []}
    if isinstance(lineup_rows, list):
        for row in lineup_rows:
            if not isinstance(row, dict):
                continue
            side = _text(row.get("strTeamPosition") or row.get("strHomeAway") or row.get("homeAway")).lower()
            team_side = "home" if "home" in side else "away" if "away" in side else ""
            if not team_side:
                continue
            position = _text(row.get("strSubstitute") or row.get("strPosition")).lower()
            if "yes" in position or "sub" in position:
                continue
            name = _player_name(row)
            if name and name not in lineups[team_side]:
                lineups[team_side].append(name)
    for side in lineups:
        lineups[side] = lineups[side][:11] if len(lineups[side]) >= 11 else []

    timeline_rows = (
        timeline_payload.get("timeline") or timeline_payload.get("timelines")
        or timeline_payload.get("events") or timeline_payload.get("event") or []
    )
    wrapper = {"timeline": timeline_rows if isinstance(timeline_rows, list) else []}
    timeline = _extract_timeline_generic(wrapper)

    stats_rows = (
        stats_payload.get("eventstats") or stats_payload.get("statistics")
        or stats_payload.get("stats") or []
    )
    stats = _extract_stats_generic({"statistics": stats_rows})

    return {
        "lineups": lineups,
        "timeline": timeline,
        "goals": [x for x in timeline if x.get("kind") == "goal"],
        "cards": [x for x in timeline if x.get("kind") == "card"],
        "substitutions": [x for x in timeline if x.get("kind") == "substitution"],
        "stats": stats,
        "player_stats": [],
        "info": {},
    }


def fetch_provider_enrichment(session: requests.Session, match: dict) -> dict[str, Any]:
    """Try rich free detail providers in quality order, including secondary mappings."""
    source = _text(match.get("source")).lower()
    raw = match.get("raw_data") if isinstance(match.get("raw_data"), dict) else {}
    slugs = match.get("provider_slugs") if isinstance(match.get("provider_slugs"), dict) else {}
    ids = match.get("provider_ids") if isinstance(match.get("provider_ids"), dict) else {}
    if isinstance(raw.get("provider_slugs"), dict):
        slugs = {**raw.get("provider_slugs"), **slugs}
    if isinstance(raw.get("provider_ids"), dict):
        ids = {**raw.get("provider_ids"), **ids}

    sport_slug = (
        match.get("provider_slug") if source == "sportscore" else None
    ) or slugs.get("sportscore") or (
        (match.get("raw") or {}).get("slug") if isinstance(match.get("raw"), dict) else None
    ) or raw.get("provider_slug")
    if sport_slug:
        detail = fetch_sportscore_detail(session, _text(sport_slug))
        enriched = extract_sportscore_enrichment(detail)
        if (
            (enriched.get("goals") or [])
            or (enriched.get("lineups") or {}).get("home")
            or (enriched.get("stats") or {}).get("home")
        ):
            return enriched

    tsdb_id = ids.get("thesportsdb")
    if source == "thesportsdb" and not tsdb_id:
        tsdb_id = match.get("source_match_id") or re.sub(r"\D", "", str(match.get("id") or ""))
    if tsdb_id:
        enriched = extract_thesportsdb_enrichment(
            fetch_thesportsdb_details(session, str(tsdb_id))
        )
        if (
            (enriched.get("goals") or [])
            or (enriched.get("lineups") or {}).get("home")
            or (enriched.get("stats") or {}).get("home")
        ):
            return enriched
    return {}
