#!/usr/bin/env python3
"""Sources gratuites et détection d'états pour le cycle d'un match Actu Foot.

Priorité par qualité de données:
1. ESPN pour les événements détaillés.
2. SportScore pour couverture/live, timeline et lineups.
3. Cache Supabase/BSD pour continuité et couverture.
4. TheSportsDB pour enrichissement ciblé.
5. OpenLigaDB pour confirmation des ligues disponibles.

Aucune source payante n'est requise par ce module.
"""
from __future__ import annotations

import os
import re
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bsd"))
from free_football_sources import (  # noqa: E402
    SOURCE_QUALITY,
    collect_free_day,
    fetch_sportscore_match,
    sportscore_detail_enrichment,
    sportscore_lineups,
    sportscore_goals,
    fetch_thesportsdb_event_detail,
    thesportsdb_lineups,
    thesportsdb_timeline,
)

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary"
ESPN_MATCH_PAGE = "https://www.espn.com/soccer/match/_/gameId/{event_id}"
OPENLIGA_BASE = "https://api.openligadb.de"

_ESPN_CACHE: dict[str, tuple[float, dict]] = {}
_ESPN_REQUESTS = 0


def _espn_budget() -> int:
    try:
        return max(8, min(120, int(os.getenv("FOOTBALL_ESPN_REQUEST_BUDGET", "36"))))
    except ValueError:
        return 36


def _retry_after_seconds(response: requests.Response) -> float:
    raw = str(response.headers.get("Retry-After") or "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, min(120.0, float(raw)))
    except ValueError:
        return 0.0


def _espn_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, str],
    cache_key: str,
    ttl: float,
    force: bool = False,
) -> dict:
    """Client ESPN borné: cache court, budget, retry 429/5xx et validation JSON."""
    global _ESPN_REQUESTS
    now = time.monotonic()
    cached = _ESPN_CACHE.get(cache_key)
    if not force and cached and now - cached[0] <= ttl:
        return cached[1]

    last_error: Exception | None = None
    for attempt in range(3):
        if _ESPN_REQUESTS >= _espn_budget():
            break
        _ESPN_REQUESTS += 1
        try:
            response = session.get(
                url,
                params=params,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; MrXPRONOS-ActuFoot/3.0)",
                    "Accept": "application/json,text/plain,*/*",
                    "Referer": "https://www.espn.com/soccer/",
                },
                timeout=(7, 18),
                allow_redirects=True,
            )
            if response.status_code == 429:
                if attempt < 2:
                    time.sleep(_retry_after_seconds(response) or (0.7 * (2 ** attempt)))
                    continue
                response.raise_for_status()
            if response.status_code >= 500:
                if attempt < 2:
                    time.sleep(0.7 * (2 ** attempt))
                    continue
                response.raise_for_status()
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("ESPN payload is not an object")
            _ESPN_CACHE[cache_key] = (time.monotonic(), payload)
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.45 * (2 ** attempt))
    if cached:
        return cached[1]
    if last_error:
        print("ESPN_DIRECT_ERROR", cache_key, type(last_error).__name__, str(last_error)[:120])
    return {}


def espn_match_url(event_id: str) -> str:
    event_id = re.sub(r"[^0-9]", "", str(event_id or ""))
    return ESPN_MATCH_PAGE.format(event_id=event_id) if event_id else ""


def _minute_total(value: Any) -> int | None:
    text = _plain(value)
    if not text:
        return None
    match = re.search(r"(\d+)(?:\D*\+\D*(\d+))?", text)
    if not match:
        return None
    return int(match.group(1)) + int(match.group(2) or 0)


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _plain(value)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(fc|cf|sc|afc|club|the|de|da|do|calcio|football)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _score(value: Any) -> int | None:
    if value in (None, "", "-", "None"):
        return None
    try:
        number = int(float(str(value)))
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def _minute(value: Any) -> int:
    if value in (None, "", "None"):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    match = re.search(r"\d+", str(value))
    return max(0, int(match.group())) if match else 0


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _tokens_similarity(a: str, b: str) -> float:
    aa, bb = set(_norm(a).split()), set(_norm(b).split())
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    return len(aa & bb) / max(len(aa | bb), 1)


def match_similarity(home_a: str, away_a: str, home_b: str, away_b: str) -> float:
    direct = (_tokens_similarity(home_a, home_b) + _tokens_similarity(away_a, away_b)) / 2
    swapped = (_tokens_similarity(home_a, away_b) + _tokens_similarity(away_a, home_b)) / 2
    return max(direct, swapped)


def _team_name(event: dict, side: str) -> str:
    value = event.get(side + "_team")
    if isinstance(value, dict):
        value = value.get("name") or value.get("displayName")
    return _plain(value)


def _event_time(event: dict) -> datetime | None:
    return _moment(event.get("event_date") or event.get("date") or event.get("start_time"))


def fetch_supabase_live(session: requests.Session, max_age_seconds: int = 360) -> list[dict]:
    base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    if not base or not key:
        return []
    since = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
    try:
        response = session.get(
            base + "/rest/v1/matches_live",
            params={
                "select": "id,home_team,away_team,home_score,away_score,current_minute,league_name,status,raw_data,updated_at",
                "updated_at": "gte." + since,
                "order": "updated_at.desc",
            },
            headers={"apikey": key, "Authorization": "Bearer " + key},
            timeout=(7, 18),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    rows = []
    for row in payload if isinstance(payload, list) else []:
        if not isinstance(row, dict):
            continue
        raw = row.get("raw_data") if isinstance(row.get("raw_data"), dict) else {}
        merge_meta = raw.get("merge_meta") if isinstance(raw.get("merge_meta"), dict) else {}
        raw_source = _plain(raw.get("source") or merge_meta.get("primary_source")).lower()
        espn_id = str(
            raw.get("event_id")
            or raw.get("espn_id")
            or merge_meta.get("espn_match_id")
            or (str(row.get("id") or "").removeprefix("espn:") if str(row.get("id") or "").startswith("espn:") else "")
            or ""
        )
        rows.append({
            "source": "supabase_live",
            "id": str(row.get("id") or raw.get("id") or ""),
            "home_team": _plain(row.get("home_team") or raw.get("home_team")),
            "away_team": _plain(row.get("away_team") or raw.get("away_team")),
            "home_score": _score(row.get("home_score")),
            "away_score": _score(row.get("away_score")),
            "minute": _score(row.get("current_minute") or raw.get("current_minute") or raw.get("minute")) or 0,
            "league": _plain(row.get("league_name") or raw.get("league_name") or (raw.get("league") or {}).get("name")),
            "state": "post" if raw.get("is_finished") else "in" if raw.get("is_live") else _plain(row.get("status")).lower(),
            "status_detail": _plain(row.get("status") or raw.get("status")),
            "event_date": row.get("event_date") or raw.get("event_date") or raw.get("date"),
            "espn_id": espn_id,
            "espn_url": espn_match_url(espn_id),
            "live_stats": raw.get("live_stats") if isinstance(raw.get("live_stats"), dict) else {},
            "raw_source": raw_source,
            "raw": raw,
        })
    return rows


def parse_espn_event(event: dict) -> dict | None:
    competitions = event.get("competitions") or []
    competition = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    competitors = competition.get("competitors") or []
    home = next((x for x in competitors if x.get("homeAway") == "home"), None)
    away = next((x for x in competitors if x.get("homeAway") == "away"), None)
    if not isinstance(home, dict) or not isinstance(away, dict):
        return None
    status = competition.get("status") or event.get("status") or {}
    typ = status.get("type") if isinstance(status.get("type"), dict) else {}
    state = _plain(typ.get("state") or "").lower()
    completed = bool(typ.get("completed"))
    if completed:
        state = "post"
    team_h = home.get("team") if isinstance(home.get("team"), dict) else {}
    team_a = away.get("team") if isinstance(away.get("team"), dict) else {}
    minute = _minute(status.get("displayClock") or status.get("clock") or 0)
    period = _score(status.get("period") or competition.get("period") or 0) or 0
    return {
        "source": "espn",
        "id": str(event.get("id") or competition.get("id") or ""),
        "home_team": _plain(team_h.get("displayName") or team_h.get("name")),
        "away_team": _plain(team_a.get("displayName") or team_a.get("name")),
        "home_team_id": str(team_h.get("id") or ""),
        "away_team_id": str(team_a.get("id") or ""),
        "home_logo": team_h.get("logo") or "",
        "away_logo": team_a.get("logo") or "",
        "home_score": _score(home.get("score")),
        "away_score": _score(away.get("score")),
        "minute": minute,
        "period": period,
        "state": state,
        "status_detail": " ".join(filter(None, dict.fromkeys(_plain(typ.get(k)) for k in ("shortDetail", "detail", "description", "name")))),
        "event_date": event.get("date") or competition.get("date"),
        "league": _plain((competition.get("league") or {}).get("name") or event.get("league")),
        "venue": _plain(((competition.get("venue") or {}).get("fullName") if isinstance(competition.get("venue"), dict) else "")),
        "attendance": _score(competition.get("attendance")),
        "espn_url": espn_match_url(str(event.get("id") or competition.get("id") or "")),
        "raw": event,
    }


def fetch_espn_day(session: requests.Session, day: date, *, force: bool = False) -> list[dict]:
    key = day.strftime("%Y%m%d")
    payload = _espn_json(
        session,
        ESPN_SCOREBOARD,
        params={"dates": key, "limit": "1000"},
        cache_key="scoreboard:" + key,
        ttl=25.0 if day == datetime.now(timezone.utc).date() else 900.0,
        force=force,
    )
    result = []
    for event in payload.get("events", []) if isinstance(payload, dict) else []:
        if isinstance(event, dict):
            parsed = parse_espn_event(event)
            if parsed and parsed["home_team"] and parsed["away_team"]:
                result.append(parsed)
    return result


def fetch_espn_summary(
    session: requests.Session,
    event_id: str,
    *,
    force: bool = False,
) -> dict:
    event_id = re.sub(r"[^0-9]", "", str(event_id or ""))
    if not event_id:
        return {}
    return _espn_json(
        session,
        ESPN_SUMMARY,
        params={"event": event_id},
        cache_key="summary:" + event_id,
        ttl=18.0,
        force=force,
    )


def parse_espn_summary_match(summary: dict) -> dict | None:
    header = summary.get("header") if isinstance(summary, dict) else None
    if not isinstance(header, dict):
        return None
    competitions = header.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return None
    event = {
        "id": header.get("id") or competitions[0].get("id"),
        "date": competitions[0].get("date") or header.get("date"),
        "competitions": competitions,
        "league": header.get("league") or {},
        "season": header.get("season") or {},
    }
    return parse_espn_event(event)


def extract_lineups(summary: dict) -> dict[str, list[str]]:
    """Retourne uniquement les 11 titulaires confirmés par équipe."""
    result: dict[str, list[str]] = {"home": [], "away": []}
    rosters = summary.get("rosters") if isinstance(summary, dict) else None
    if not isinstance(rosters, list):
        return result
    for roster in rosters:
        if not isinstance(roster, dict):
            continue
        side = _plain(roster.get("homeAway")).lower()
        if side not in result:
            continue
        entries = roster.get("roster") or roster.get("players") or []
        starters = []
        for item in entries if isinstance(entries, list) else []:
            if not isinstance(item, dict) or item.get("starter") is not True:
                continue
            athlete = item.get("athlete") if isinstance(item.get("athlete"), dict) else item
            name = _plain(athlete.get("displayName") or athlete.get("fullName") or athlete.get("name"))
            if name:
                starters.append(name)
        if len(starters) >= 11:
            result[side] = starters[:11]
    return result


def _athlete_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    athlete = value.get("athlete") if isinstance(value.get("athlete"), dict) else value
    return _plain(athlete.get("displayName") or athlete.get("fullName") or athlete.get("name"))


def extract_goals(summary: dict) -> list[dict]:
    details = summary.get("details") if isinstance(summary, dict) else None
    if not isinstance(details, list):
        return []
    goals = []
    for item in details:
        if not isinstance(item, dict):
            continue
        typ = item.get("type") if isinstance(item.get("type"), dict) else {}
        label = _plain(typ.get("text") or typ.get("abbreviation") or item.get("text")).lower()
        if not (item.get("scoringPlay") is True or "goal" in label or "but" in label):
            continue
        athletes = item.get("athletes") or []
        athletes = athletes if isinstance(athletes, list) else []
        player = _athlete_name(athletes[0]) if athletes else ""
        player_id = ""
        if athletes and isinstance(athletes[0], dict):
            athlete = athletes[0].get("athlete") if isinstance(athletes[0].get("athlete"), dict) else athletes[0]
            player_id = str(athlete.get("id") or "")
        assists = []
        explicit_assists = item.get("assists")
        if isinstance(explicit_assists, list):
            assists = [_athlete_name(x) for x in explicit_assists if _athlete_name(x)]
        elif isinstance(item.get("assist"), dict):
            name = _athlete_name(item["assist"])
            assists = [name] if name else []
        else:
            for athlete in athletes[1:]:
                role = _plain(athlete.get("type") or athlete.get("role")).lower() if isinstance(athlete, dict) else ""
                name = _athlete_name(athlete)
                if name and "assist" in role:
                    assists.append(name)

        clock = item.get("clock") if isinstance(item.get("clock"), dict) else {}
        minute_text = _plain(clock.get("displayValue") or item.get("time") or "")
        minute_total = _minute_total(minute_text)
        minute = int(re.search(r"\d+", minute_text).group()) if re.search(r"\d+", minute_text) else None
        team_obj = item.get("team") if isinstance(item.get("team"), dict) else {}
        home_score = _score(item.get("homeScore") if item.get("homeScore") is not None else item.get("home_score"))
        away_score = _score(item.get("awayScore") if item.get("awayScore") is not None else item.get("away_score"))
        goals.append({
            "player": player,
            "player_id": player_id,
            "minute": minute,
            "minute_total": minute_total,
            "minute_text": minute_text,
            "team_id": str(team_obj.get("id") or ""),
            "team": _plain(team_obj.get("displayName") or team_obj.get("name")),
            "assists": assists,
            "home_score": home_score,
            "away_score": away_score,
            "own_goal": bool(item.get("ownGoal")) or "own goal" in label or "c.s.c" in label,
            "penalty": bool(item.get("penaltyKick")) or "penalty" in label or "pen." in label,
            "label": _plain(typ.get("text") or item.get("text")),
        })
    goals.sort(key=lambda x: (x.get("minute_total") is None, x.get("minute_total") or 999))
    return goals


def extract_cards(summary: dict) -> list[dict]:
    details = summary.get("details") if isinstance(summary, dict) else None
    if not isinstance(details, list):
        return []
    cards: list[dict] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        typ = item.get("type") if isinstance(item.get("type"), dict) else {}
        label = _plain(typ.get("text") or typ.get("abbreviation") or item.get("text")).lower()
        yellow = item.get("yellowCard") is True or "yellow card" in label
        red = item.get("redCard") is True or "red card" in label
        if not (yellow or red):
            continue
        athletes = item.get("athletes") or []
        athlete = athletes[0] if isinstance(athletes, list) and athletes else {}
        clock = item.get("clock") if isinstance(item.get("clock"), dict) else {}
        team_obj = item.get("team") if isinstance(item.get("team"), dict) else {}
        minute_text = _plain(clock.get("displayValue") or item.get("time") or "")
        cards.append({
            "player": _athlete_name(athlete),
            "minute": _minute_total(minute_text),
            "minute_text": minute_text,
            "team_id": str(team_obj.get("id") or ""),
            "type": "red" if red else "yellow",
        })
    return cards


def extract_substitutions(summary: dict) -> list[dict]:
    details = summary.get("details") if isinstance(summary, dict) else None
    if not isinstance(details, list):
        return []
    changes: list[dict] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        typ = item.get("type") if isinstance(item.get("type"), dict) else {}
        label = _plain(typ.get("text") or typ.get("abbreviation") or item.get("text")).lower()
        if item.get("substitution") is not True and "substitution" not in label and "sub " not in label:
            continue
        athletes = item.get("athletes") or []
        athletes = athletes if isinstance(athletes, list) else []
        names = [_athlete_name(x) for x in athletes if _athlete_name(x)]
        clock = item.get("clock") if isinstance(item.get("clock"), dict) else {}
        minute_text = _plain(clock.get("displayValue") or item.get("time") or "")
        team_obj = item.get("team") if isinstance(item.get("team"), dict) else {}
        changes.append({
            "players": names[:2],
            "minute": _minute_total(minute_text),
            "minute_text": minute_text,
            "team_id": str(team_obj.get("id") or ""),
        })
    return changes


def _stat_value(stat: dict) -> Any:
    return stat.get("displayValue") if stat.get("displayValue") not in (None, "") else stat.get("value")


def _normalize_stat_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _plain(value).casefold())


def extract_team_stats(summary: dict) -> dict[str, dict[str, Any]]:
    boxscore = summary.get("boxscore") if isinstance(summary, dict) else None
    teams = boxscore.get("teams") if isinstance(boxscore, dict) else None
    header = parse_espn_summary_match(summary)
    result: dict[str, dict[str, Any]] = {"home": {}, "away": {}}
    if not isinstance(teams, list):
        return result

    home_id = str((header or {}).get("home_team_id") or "")
    away_id = str((header or {}).get("away_team_id") or "")
    aliases = {
        "corners": {"woncorners", "corners", "cornerkicks"},
        "shots": {"totalshots", "shotstotal", "shots"},
        "shots_on_target": {"shotsontarget", "shotsongoal"},
        "possession": {"possessionpct", "possession", "possessionpercentage"},
        "fouls": {"foulscommitted", "fouls"},
        "offsides": {"offsides"},
        "saves": {"saves", "goalkeepersaves"},
        "yellow_cards": {"yellowcards"},
        "red_cards": {"redcards"},
    }
    for row in teams:
        if not isinstance(row, dict):
            continue
        team_obj = row.get("team") if isinstance(row.get("team"), dict) else {}
        team_id = str(team_obj.get("id") or "")
        side = "home" if team_id and team_id == home_id else "away" if team_id and team_id == away_id else ""
        if not side:
            continue
        available = {}
        for stat in row.get("statistics") or []:
            if isinstance(stat, dict):
                available[_normalize_stat_name(stat.get("name") or stat.get("label"))] = _stat_value(stat)
        for target, names in aliases.items():
            for name in names:
                if name in available:
                    result[side][target] = available[name]
                    break
    return result


def extract_match_info(summary: dict) -> dict[str, Any]:
    game = summary.get("gameInfo") if isinstance(summary, dict) else None
    game = game if isinstance(game, dict) else {}
    venue = game.get("venue") if isinstance(game.get("venue"), dict) else {}
    address = venue.get("address") if isinstance(venue.get("address"), dict) else {}
    officials = game.get("officials") if isinstance(game.get("officials"), list) else []
    weather = game.get("weather") if isinstance(game.get("weather"), dict) else {}
    return {
        "venue": _plain(venue.get("fullName") or venue.get("name")),
        "city": _plain(address.get("city")),
        "country": _plain(address.get("country")),
        "attendance": _score(game.get("attendance")),
        "referees": [
            _plain((x.get("official") or {}).get("displayName") if isinstance(x.get("official"), dict) else x.get("displayName"))
            for x in officials if isinstance(x, dict)
            and _plain((x.get("official") or {}).get("displayName") if isinstance(x.get("official"), dict) else x.get("displayName"))
        ],
        "weather": _plain(weather.get("displayValue") or weather.get("conditionId") or weather.get("condition")),
        "temperature": weather.get("temperature"),
    }


def extract_player_stats(summary: dict) -> list[dict[str, Any]]:
    """Aplati les groupes de statistiques joueurs ESPN quand ils existent."""
    boxscore = summary.get("boxscore") if isinstance(summary, dict) else None
    groups = boxscore.get("players") if isinstance(boxscore, dict) else None
    if not isinstance(groups, list):
        return []
    rows: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        team_obj = group.get("team") if isinstance(group.get("team"), dict) else {}
        team_id = str(team_obj.get("id") or "")
        for category in group.get("statistics") or []:
            if not isinstance(category, dict):
                continue
            names = [str(x) for x in (category.get("names") or category.get("labels") or [])]
            category_name = _plain(
                category.get("name") or category.get("displayName") or category.get("label")
            )
            for item in category.get("athletes") or []:
                if not isinstance(item, dict):
                    continue
                athlete = item.get("athlete") if isinstance(item.get("athlete"), dict) else {}
                player = _plain(athlete.get("displayName") or athlete.get("fullName") or athlete.get("name"))
                if not player:
                    continue
                values = item.get("stats") if isinstance(item.get("stats"), list) else []
                mapped = {
                    names[i]: values[i]
                    for i in range(min(len(names), len(values)))
                    if names[i]
                }
                rows.append({
                    "player": player,
                    "player_id": str(athlete.get("id") or ""),
                    "team_id": team_id,
                    "category": category_name,
                    "starter": item.get("starter"),
                    "did_not_play": item.get("didNotPlay"),
                    "stats": mapped,
                })
    return rows[:80]


def extract_timeline(summary: dict) -> list[dict[str, Any]]:
    """Chronologie éditoriale structurée : buts, cartons et remplacements."""
    timeline: list[dict[str, Any]] = []
    for goal in extract_goals(summary):
        timeline.append({"kind": "goal", **goal})
    for card in extract_cards(summary):
        timeline.append({"kind": "card", **card})
    for change in extract_substitutions(summary):
        timeline.append({"kind": "substitution", **change})
    timeline.sort(key=lambda x: (
        x.get("minute") is None and x.get("minute_total") is None,
        x.get("minute_total") if x.get("minute_total") is not None else x.get("minute") or 999,
        x.get("kind") or "",
    ))
    return timeline


def extract_match_enrichment(summary: dict) -> dict[str, Any]:
    goals = extract_goals(summary)
    cards = extract_cards(summary)
    substitutions = extract_substitutions(summary)
    return {
        "goals": goals,
        "cards": cards,
        "substitutions": substitutions,
        "timeline": extract_timeline(summary),
        "stats": extract_team_stats(summary),
        "player_stats": extract_player_stats(summary),
        "lineups": extract_lineups(summary),
        "info": extract_match_info(summary),
    }


def verify_espn_public_page(
    session: requests.Session,
    event_id: str,
    home: str = "",
    away: str = "",
) -> dict[str, Any]:
    """Second contrôle sur la page publique ESPN; un challenge anti-bot reste 'indisponible'."""
    url = espn_match_url(event_id)
    if not url:
        return {"reachable": False, "content_verified": False, "url": ""}
    try:
        response = session.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/154 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=(7, 16),
            allow_redirects=True,
        )
        final_host = (urlparse(response.url).hostname or "").lower()
        body = response.text[:1_500_000] if response.status_code == 200 else ""
        challenge = "verify that you're not a robot" in body.lower() or "javascript is disabled" in body.lower()
        normalized = _norm(body[:500_000])
        home_tokens = [x for x in _norm(home).split() if len(x) >= 4]
        away_tokens = [x for x in _norm(away).split() if len(x) >= 4]
        home_ok = not home_tokens or any(x in normalized for x in home_tokens)
        away_ok = not away_tokens or any(x in normalized for x in away_tokens)
        reachable = response.ok and final_host.endswith("espn.com") and not challenge
        return {
            "reachable": reachable,
            "content_verified": bool(reachable and home_ok and away_ok),
            "url": response.url if final_host.endswith("espn.com") else url,
            "status": response.status_code,
            "challenge": challenge,
        }
    except requests.RequestException as exc:
        return {
            "reachable": False,
            "content_verified": False,
            "url": url,
            "error": type(exc).__name__,
        }


def verify_espn_before_publish(
    session: requests.Session,
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Vérifie le fait éditorial directement chez ESPN juste avant l'envoi."""
    event_id = re.sub(r"[^0-9]", "", str(expected.get("event_id") or ""))
    if not event_id:
        return {"ok": False, "quality": 0, "reason": "missing_espn_event_id"}

    summary = fetch_espn_summary(session, event_id, force=True)
    direct = parse_espn_summary_match(summary)
    if not summary or not direct:
        return {"ok": False, "quality": 0, "reason": "espn_summary_unavailable", "event_id": event_id}

    home = _plain(expected.get("home"))
    away = _plain(expected.get("away"))
    if home and _tokens_similarity(home, direct.get("home_team", "")) < 0.55:
        return {"ok": False, "quality": 0, "reason": "home_team_mismatch", "event_id": event_id}
    if away and _tokens_similarity(away, direct.get("away_team", "")) < 0.55:
        return {"ok": False, "quality": 0, "reason": "away_team_mismatch", "event_id": event_id}

    kind = _plain(expected.get("kind")).lower()
    expected_score = _plain(expected.get("score"))
    if re.fullmatch(r"\d+-\d+", expected_score):
        hs, aws = (int(x) for x in expected_score.split("-"))
        if direct.get("home_score") != hs or direct.get("away_score") != aws:
            return {
                "ok": False, "quality": 0, "reason": "score_mismatch",
                "event_id": event_id,
                "espn_score": f"{direct.get('home_score')}-{direct.get('away_score')}",
            }

    if kind == "resultat_final" and direct.get("state") != "post":
        return {"ok": False, "quality": 0, "reason": "final_state_not_confirmed", "event_id": event_id}
    if kind == "mi_temps" and not is_halftime(direct):
        return {"ok": False, "quality": 0, "reason": "halftime_not_confirmed", "event_id": event_id}
    if kind == "kickoff" and not is_live(direct):
        return {"ok": False, "quality": 0, "reason": "kickoff_not_live", "event_id": event_id}

    enrichment = extract_match_enrichment(summary)
    if kind == "composition":
        lineups = extract_lineups(summary)
        if len(lineups["home"]) != 11 or len(lineups["away"]) != 11:
            return {"ok": False, "quality": 0, "reason": "lineup_not_complete", "event_id": event_id}
    if kind == "goal":
        wanted = expected.get("goal") if isinstance(expected.get("goal"), dict) else {}
        scorer = _norm(wanted.get("player"))
        minute = wanted.get("minute_total")
        if minute is None:
            minute = _minute_total(wanted.get("minute_text") or wanted.get("minute"))
        found = False
        for goal in enrichment["goals"]:
            if scorer and _norm(goal.get("player")) != scorer:
                continue
            current_minute = goal.get("minute_total")
            if minute is not None and current_minute is not None and abs(int(current_minute) - int(minute)) > 1:
                continue
            found = True
            break
        if not found:
            return {"ok": False, "quality": 0, "reason": "goal_not_confirmed", "event_id": event_id}

    page = verify_espn_public_page(session, event_id, home, away)
    quality = 100 if page.get("content_verified") else 94 if page.get("reachable") else 90
    return {
        "ok": True,
        "quality": quality,
        "reason": "confirmed",
        "event_id": event_id,
        "source_url": page.get("url") or espn_match_url(event_id),
        "page": page,
        "direct": direct,
        "enrichment": enrichment,
    }



def verify_espn_fixtures_before_publish(
    session: requests.Session,
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Contrôle direct du scoreboard ESPN pour les publications issues d'autres sources.

    L'absence de couverture ESPN n'est pas une contradiction. En revanche, si ESPN
    retrouve le match et indique un horaire/score/statut incompatible, la publication
    est rejetée.
    """
    fixtures = verification.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        return {"ok": True, "quality": 70, "reason": "no_fixtures_to_verify", "covered": 0}

    kind = _plain(verification.get("kind")).lower()
    by_day: dict[date, list[dict]] = {}
    invalid = 0
    for fixture in fixtures[:8]:
        if not isinstance(fixture, dict):
            invalid += 1
            continue
        when = _moment(fixture.get("event_date") or fixture.get("kickoff"))
        home = _plain(fixture.get("home"))
        away = _plain(fixture.get("away"))
        if not when or not home or not away:
            invalid += 1
            continue
        by_day.setdefault(when.astimezone(timezone.utc).date(), []).append(fixture)

    if not by_day:
        return {
            "ok": True,
            "quality": 65,
            "reason": "fixtures_missing_identity",
            "covered": 0,
            "invalid": invalid,
        }

    covered = 0
    missing = 0
    contradictions: list[dict[str, Any]] = []
    verified_rows: list[dict[str, Any]] = []
    first_public_page: dict[str, Any] | None = None

    for day, day_fixtures in by_day.items():
        # force=True garantit un contrôle réseau ESPN au moment de publier.
        rows = fetch_espn_day(session, day, force=True)
        # Une rencontre proche de minuit peut être rangée sur le jour voisin selon
        # le calendrier de la compétition. On tente seulement ce fallback si rien
        # n'a été retrouvé sur le jour principal.
        adjacent_cache: dict[date, list[dict]] = {}

        for fixture in day_fixtures:
            base = {
                "home_team": _plain(fixture.get("home")),
                "away_team": _plain(fixture.get("away")),
                "event_date": fixture.get("event_date") or fixture.get("kickoff"),
                "follow_ref": "espn-preflight",
            }
            match = best_external_match(base, rows)
            if match is None:
                when = _moment(base["event_date"])
                if when and (when.hour <= 1 or when.hour >= 23):
                    for alt_day in (day - timedelta(days=1), day + timedelta(days=1)):
                        if alt_day not in adjacent_cache:
                            adjacent_cache[alt_day] = fetch_espn_day(session, alt_day, force=True)
                        match = best_external_match(base, adjacent_cache[alt_day])
                        if match is not None:
                            break

            if match is None or match.get("source") != "espn":
                missing += 1
                continue

            home_score = _tokens_similarity(base["home_team"], match.get("home_team", ""))
            away_score = _tokens_similarity(base["away_team"], match.get("away_team", ""))
            if min(home_score, away_score) < 0.45:
                missing += 1
                continue

            expected_time = _moment(base["event_date"])
            espn_time = _moment(match.get("event_date"))
            if expected_time and espn_time:
                delta_minutes = abs((expected_time - espn_time).total_seconds()) / 60
                # Un changement ESPN >45 min signifie que notre horaire est trop ancien.
                if delta_minutes > 45:
                    contradictions.append({
                        "reason": "kickoff_mismatch",
                        "home": base["home_team"],
                        "away": base["away_team"],
                        "expected": expected_time.isoformat(),
                        "espn": espn_time.isoformat(),
                    })
                    continue

            detail = _plain(match.get("status_detail")).lower()
            state = _plain(match.get("state")).lower()
            if any(token in detail for token in ("cancel", "postpon", "abandon", "suspend")):
                contradictions.append({
                    "reason": "espn_fixture_not_playable",
                    "home": base["home_team"],
                    "away": base["away_team"],
                    "status": match.get("status_detail"),
                })
                continue

            expected_score = _plain(fixture.get("score"))
            if expected_score and re.fullmatch(r"\d+-\d+", expected_score):
                hs, aws = (int(value) for value in expected_score.split("-"))
                if match.get("home_score") != hs or match.get("away_score") != aws:
                    contradictions.append({
                        "reason": "score_mismatch",
                        "home": base["home_team"],
                        "away": base["away_team"],
                        "expected": expected_score,
                        "espn": f"{match.get('home_score')}-{match.get('away_score')}",
                    })
                    continue

            if kind in {"resultat", "resultat_final", "statistique_match"} and state != "post":
                contradictions.append({
                    "reason": "final_state_not_confirmed",
                    "home": base["home_team"],
                    "away": base["away_team"],
                    "state": state,
                })
                continue
            if kind in {"programme", "avant_match", "sondage"} and state == "post":
                contradictions.append({
                    "reason": "fixture_already_finished",
                    "home": base["home_team"],
                    "away": base["away_team"],
                })
                continue

            covered += 1
            row = {
                "event_id": str(match.get("id") or ""),
                "home": match.get("home_team"),
                "away": match.get("away_team"),
                "state": state,
                "status": match.get("status_detail"),
                "event_date": match.get("event_date"),
                "home_score": match.get("home_score"),
                "away_score": match.get("away_score"),
                "venue": match.get("venue") or "",
                "attendance": match.get("attendance"),
                "espn_url": match.get("espn_url") or espn_match_url(str(match.get("id") or "")),
            }
            verified_rows.append(row)
            if first_public_page is None and row["event_id"]:
                first_public_page = verify_espn_public_page(
                    session, row["event_id"], row["home"] or "", row["away"] or ""
                )

    total = sum(len(items) for items in by_day.values())
    if contradictions:
        return {
            "ok": False,
            "quality": 0,
            "reason": "espn_fixture_contradiction",
            "covered": covered,
            "missing": missing,
            "total": total,
            "contradictions": contradictions,
            "verified": verified_rows,
        }

    enrichment: dict[str, Any] = {}
    if covered == 1 and verified_rows and kind in {"avant_match", "resultat", "resultat_final", "statistique_match"}:
        event_id = str(verified_rows[0].get("event_id") or "")
        if event_id:
            summary = fetch_espn_summary(session, event_id, force=True)
            if summary:
                enrichment = extract_match_enrichment(summary)

    page_bonus = 5 if first_public_page and first_public_page.get("content_verified") else 0
    coverage_ratio = covered / max(total, 1)
    quality = min(100, round(72 + coverage_ratio * 23 + page_bonus))
    reason = "confirmed" if covered == total else "partial_espn_coverage" if covered else "espn_not_covered"
    return {
        "ok": True,
        "quality": quality,
        "reason": reason,
        "covered": covered,
        "missing": missing,
        "invalid": invalid,
        "total": total,
        "verified": verified_rows,
        "page": first_public_page or {},
        "enrichment": enrichment,
    }

def _season_for(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def fetch_openligadb_bundesliga(session: requests.Session, day: date) -> list[dict]:
    """Contrôle gratuit Bundesliga. API sans inscription ni clé."""
    season = _season_for(day)
    try:
        response = session.get(
            f"{OPENLIGA_BASE}/getmatchdata/bl1/{season}",
            headers={"User-Agent": "MrXPRONOS-ActuFoot/2.0"},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []
    result = []
    for item in payload if isinstance(payload, list) else []:
        when = _moment(item.get("matchDateTimeUTC") or item.get("matchDateTime"))
        if when is None or when.date() != day:
            continue
        team1 = item.get("team1") if isinstance(item.get("team1"), dict) else {}
        team2 = item.get("team2") if isinstance(item.get("team2"), dict) else {}
        results = item.get("matchResults") or []
        latest = None
        for row in results if isinstance(results, list) else []:
            if not isinstance(row, dict):
                continue
            if latest is None or int(row.get("resultOrderID") or 0) > int(latest.get("resultOrderID") or 0):
                latest = row
        goals = item.get("goals") or []
        hs = _score((latest or {}).get("pointsTeam1"))
        aws = _score((latest or {}).get("pointsTeam2"))
        result.append({
            "source": "openligadb",
            "id": str(item.get("matchID") or ""),
            "home_team": _plain(team1.get("teamName")),
            "away_team": _plain(team2.get("teamName")),
            "home_score": hs,
            "away_score": aws,
            "minute": 0,
            "period": 0,
            "state": "post" if item.get("matchIsFinished") else "pre",
            "status_detail": "Finished" if item.get("matchIsFinished") else "Scheduled",
            "event_date": when.isoformat(),
            "league": "Bundesliga",
            "goals": goals if isinstance(goals, list) else [],
            "raw": item,
        })
    return result


def best_external_match(base: dict, external: list[dict]) -> dict | None:
    bh, ba = _team_name(base, "home"), _team_name(base, "away")
    bt = _event_time(base)
    best = None
    best_score = 0.0
    for item in external:
        similarity = match_similarity(bh, ba, item.get("home_team", ""), item.get("away_team", ""))
        # Sur un match déjà annoncé, les deux équipes doivent être dans le même
        # ordre: une correspondance inversée fausserait le score affiché.
        if base.get("follow_ref") and min(
            _tokens_similarity(bh, item.get("home_team", "")),
            _tokens_similarity(ba, item.get("away_team", "")),
        ) < 0.45:
            continue
        if similarity < 0.48:
            continue
        et = _moment(item.get("event_date"))
        if bt and et:
            hours = abs((bt - et).total_seconds()) / 3600
            if hours > (3 if base.get("follow_ref") else 8):
                continue
            similarity += max(0, 0.18 - hours * 0.02)
        if base.get("follow_ref"):
            detail = _plain(item.get("status_detail")).lower()
            state = _plain(item.get("state")).lower()
            if state == "post" and not any(w in detail for w in ("cancel", "postpon", "abandon")):
                similarity += 0.08
            elif is_live(item):
                similarity += 0.03
        quality = SOURCE_QUALITY.get(str(item.get("source") or ""), {}).get("overall", 60)
        similarity += max(0.0, (float(quality) - 60.0) / 500.0)
        if similarity > best_score:
            best, best_score = item, similarity
    return best


def collect_external(session: requests.Session, day: date, base_events: list[dict]) -> list[dict]:
    days = {day}
    for event in base_events:
        when = _event_time(event)
        if when and abs((when.date() - day).days) <= 1:
            days.add(when.date())
    rows: list[dict] = []
    for fixture_day in sorted(days):
        snapshots = collect_free_day(session, fixture_day, include_espn=True)
        for provider in ("espn", "sportscore", "thesportsdb", "openligadb"):
            snapshot = snapshots.get(provider)
            if snapshot:
                rows.extend(snapshot.rows)
    rows.extend(fetch_supabase_live(session))
    return rows


def is_halftime(match: dict) -> bool:
    detail = _plain(match.get("status_detail")).lower()
    return (
        "half time" in detail or "halftime" in detail or "mi-temps" in detail
        or "half-time" in detail or detail in {"ht", "status_halftime"}
    )


def is_live(match: dict) -> bool:
    state = _plain(match.get("state")).lower()
    detail = _plain(match.get("status_detail")).lower()
    return state in {"in", "live", "in_play", "in progress"} or any(
        token in detail for token in ("1st half", "2nd half", "live", "in progress")
    )


def lifecycle_signals(
    base_events: list[dict],
    sent_keys: set[str],
    now: datetime,
    session: requests.Session,
    importance_fn,
    tracked_only: bool = False,
) -> list[dict]:
    """Construit les transitions publiables, triées par urgence éditoriale."""
    today = now.astimezone(timezone.utc).date()
    external = collect_external(session, today, base_events)
    # Mode lifecycle léger : si aucun calendrier BSD n'est fourni, ESPN/cache
    # live devient temporairement la liste de base. Cela évite toute requête
    # BSD dans les passages rapides de 10 minutes.
    if not base_events and not tracked_only:
        base_events = [
            item for item in external
            if item.get("source") in {"espn", "sportscore", "thesportsdb", "openligadb", "supabase_live"}
            and item.get("home_team") and item.get("away_team")
        ]
    signals: list[dict] = []
    summary_cache: dict[str, dict] = {}
    detail_cache: dict[str, dict] = {}

    def provider_detail(ext: dict) -> dict:
        provider = str(ext.get("source") or "")
        provider_id = str(ext.get("provider_event_id") or ext.get("id") or "").split(":")[-1]
        cache_key = provider + ":" + provider_id + ":" + str(ext.get("sportscore_slug") or "")
        if cache_key in detail_cache:
            return detail_cache[cache_key]
        detail: dict[str, Any] = {}
        if provider == "sportscore":
            payload = fetch_sportscore_match(session, str(ext.get("sportscore_slug") or ""), ttl=18)
            detail = sportscore_detail_enrichment(payload)
            detail["lineups"] = sportscore_lineups(payload)
            detail["goals"] = sportscore_goals(payload)
        elif provider == "thesportsdb":
            payload = fetch_thesportsdb_event_detail(session, provider_id, ttl=45)
            timeline = thesportsdb_timeline(payload)
            detail = {
                "lineups": thesportsdb_lineups(payload),
                "goals": [x for x in timeline if x.get("kind") == "goal"],
                "timeline": timeline,
                "raw": payload,
            }
        detail_cache[cache_key] = detail
        return detail

    def summary_for(event_id: str) -> dict:
        if event_id not in summary_cache:
            # Budget implicite: uniquement les matchs importants et proches/live
            # appellent ce helper.
            summary_cache[event_id] = fetch_espn_summary(session, event_id)
        return summary_cache[event_id]

    def espn_identity(ext: dict) -> tuple[str, str]:
        raw_id = str(ext.get("id") or "")
        explicit = str(ext.get("espn_id") or "")
        if ext.get("source") == "espn":
            explicit = raw_id.removeprefix("espn:")
        elif raw_id.startswith("espn:") and not explicit:
            explicit = raw_id.removeprefix("espn:")
        explicit = re.sub(r"[^0-9]", "", explicit)
        return explicit, espn_match_url(explicit)

    for base in base_events:
        signal_start = len(signals)
        follow_ref = str(base.get("follow_ref") or "")
        ext = best_external_match(base, external)
        if not ext:
            continue
        event_id = str(ext.get("id") or base.get("id") or "").removeprefix("espn:")
        espn_event_id, espn_url = espn_identity(ext)
        key_id = follow_ref or event_id
        home = _team_name(base, "home")
        away = _team_name(base, "away")
        league = _plain(base.get("league_name") or base.get("competition_name") or ext.get("league") or "Football")
        kickoff = _event_time(base) or _moment(ext.get("event_date"))
        minute = int(ext.get("minute") or 0)
        hs = _score(ext.get("home_score"))
        aws = _score(ext.get("away_score"))
        score_text = f"{hs}-{aws}" if hs is not None and aws is not None else ""
        importance = int(importance_fn(base) or 0)
        if importance <= 0 and not follow_ref and not (is_live(ext) or is_halftime(ext)):
            continue
        source = _plain(ext.get("source") or "source live")

        # Composition: on ne demande le résumé ESPN que pour des matchs proches.
        if kickoff and -timedelta(minutes=8) <= kickoff - now <= timedelta(minutes=85):
            lineup_key = "composition:" + key_id
            if lineup_key not in sent_keys and ext.get("source") in {"espn", "sportscore", "thesportsdb"}:
                if ext.get("source") == "espn":
                    summary = summary_for(event_id)
                    lineups = extract_lineups(summary)
                    match_data = extract_match_enrichment(summary)
                    composition_source = "ESPN"
                else:
                    detail = provider_detail(ext)
                    lineups = detail.get("lineups") if isinstance(detail.get("lineups"), dict) else {"home": [], "away": []}
                    match_data = detail
                    composition_source = "SportScore" if ext.get("source") == "sportscore" else "TheSportsDB"
                if len(lineups.get("home", [])) == 11 and len(lineups.get("away", [])) == 11:
                    base_home = base.get("home_team")
                    base_away = base.get("away_team")
                    home_logo = _plain(ext.get("home_logo") or (base_home.get("logo") if isinstance(base_home, dict) else ""))
                    away_logo = _plain(ext.get("away_logo") or (base_away.get("logo") if isinstance(base_away, dict) else ""))
                    signals.append({
                        "kind": "composition", "key": lineup_key, "priority": 70 + importance,
                        "home": home, "away": away, "league": league, "kickoff": kickoff,
                        "lineups": lineups, "source": composition_source,
                        "home_logo": home_logo, "away_logo": away_logo,
                        "espn_event_id": espn_event_id or "",
                        "espn_url": espn_url or "",
                        "match_data": match_data,
                    })

        # Coup d'envoi: uniquement au tout début.
        if is_live(ext) and 0 <= minute <= 12:
            key = "kickoff:" + key_id
            if key not in sent_keys:
                signals.append({
                    "kind": "kickoff", "key": key, "priority": 80 + importance,
                    "home": home, "away": away, "league": league, "minute": minute,
                    "score": score_text or "0-0", "source": source,
                    "espn_event_id": espn_event_id,
                    "espn_url": espn_url,
                })

        if is_halftime(ext):
            key = "mi_temps:" + key_id
            if key not in sent_keys:
                signals.append({
                    "kind": "mi_temps", "key": key, "priority": 135 + importance,
                    "home": home, "away": away, "league": league,
                    "score": score_text, "source": source,
                    "espn_event_id": espn_event_id,
                    "espn_url": espn_url,
                    "match_data": (
                        extract_match_enrichment(summary_for(espn_event_id))
                        if espn_event_id else provider_detail(ext)
                    ),
                })

        # But/changement de score: fournisseur détaillé requis pour identifier le buteur.
        if (
            is_live(ext) and ext.get("source") in {"espn", "sportscore", "thesportsdb"}
            and hs is not None and aws is not None and hs + aws > 0
        ):
            if ext.get("source") == "espn":
                summary = summary_for(event_id)
                goals = extract_goals(summary)
                goal_match_data = extract_match_enrichment(summary)
            else:
                detail = provider_detail(ext)
                goals = detail.get("goals") if isinstance(detail.get("goals"), list) else []
                goal_match_data = detail
            last_goal = goals[-1] if goals else {}
            goal_minute = last_goal.get("minute_total")
            if goal_minute is None:
                goal_minute = last_goal.get("minute")
            # Pour un BUT, pas de publication sans événement ESPN identifiable.
            # Cela évite de transformer un score découvert tardivement en alerte instantanée.
            recent_goal = (
                bool(last_goal)
                and goal_minute is not None
                and (minute <= 0 or 0 <= minute - goal_minute <= 14)
            )
            scorer_key = _norm(last_goal.get("player") or "unknown").replace(" ", "-")[:42]
            key = f"goal:{key_id}:{hs}-{aws}:{goal_minute}:{scorer_key}"
            if (key not in sent_keys and recent_goal
                    and f"score_update:{key_id}:{score_text}" not in sent_keys):
                signals.append({
                    "kind": "goal", "key": key, "priority": 145 + importance,
                    "home": home, "away": away, "league": league, "minute": minute,
                    "score": score_text, "source": source,
                    "goal": last_goal,
                    "home_team_id": ext.get("home_team_id"),
                    "away_team_id": ext.get("away_team_id"),
                    "espn_event_id": espn_event_id or event_id,
                    "espn_url": espn_url or espn_match_url(event_id),
                    "match_data": goal_match_data,
                })

        # Le match se conclut UNIQUEMENT avec un état final + un score confirmé.
        if (follow_ref and any(token in _plain(ext.get("status_detail")).lower()
                               for token in ("postpon", "cancel", "abandon", "suspend"))):
            key = "suivi_interrompu:" + follow_ref
            if key not in sent_keys:
                signals.append({
                    "kind": "suivi_interrompu", "key": key, "priority": 250 + importance,
                    "home": home, "away": away, "league": league,
                    "status": _plain(ext.get("status_detail")), "source": source,
                    "espn_event_id": espn_event_id, "espn_url": espn_url,
                })
        elif _plain(ext.get("state")).lower() in {"post", "finished", "ft", "full_time"}:
            if hs is not None and aws is not None and follow_ref:
                base_home_obj = base.get("home_team") if isinstance(base.get("home_team"), dict) else {}
                base_away_obj = base.get("away_team") if isinstance(base.get("away_team"), dict) else {}
                home_logo = _plain(ext.get("home_logo") or base_home_obj.get("logo"))
                away_logo = _plain(ext.get("away_logo") or base_away_obj.get("logo"))
                final_key = "resultat:" + follow_ref
                if final_key not in sent_keys:
                    signals.append({
                        "kind": "resultat_final", "key": final_key,
                        "priority": 240 + importance, "home": home, "away": away,
                        "league": league, "score": score_text, "source": source,
                        "home_logo": home_logo, "away_logo": away_logo,
                        "day": now.strftime("%d/%m/%Y"),
                        "espn_event_id": espn_event_id,
                        "espn_url": espn_url,
                        "match_data": (
                            extract_match_enrichment(summary_for(espn_event_id))
                            if espn_event_id else provider_detail(ext)
                        ),
                    })
        for signal in signals[signal_start:]:
            signal["follow_ref"] = follow_ref
            signal.setdefault(
                "event_date",
                ext.get("event_date") or base.get("event_date") or base.get("date") or base.get("start_time"),
            )
            for side in ("home", "away"):
                logo_url = ext.get(side + "_logo")
                raw = base.get(side + "_team")
                if not logo_url and isinstance(raw, dict):
                    logo_url = raw.get("logo")
                if logo_url and not signal.get(side + "_logo"):
                    signal[side + "_logo"] = logo_url

    # Relevé de score, toujours limité aux rencontres explicitement retenues.
    goal_score_pairs = {(item.get("follow_ref"), item.get("score"))
                        for item in signals if item.get("kind") == "goal"}
    for base in base_events:
        match = best_external_match(base, external)
        if not match or not (is_live(match) or is_halftime(match)):
            continue
        hs, aws = _score(match.get("home_score")), _score(match.get("away_score"))
        if hs is None or aws is None or hs + aws == 0:
            continue
        ref = str(base.get("follow_ref") or "")
        event_id = ref or str(match.get("id") or "").removeprefix("espn:")
        score_text = f"{hs}-{aws}"
        key = f"score_update:{event_id}:{score_text}"
        if (key in sent_keys or (ref, score_text) in goal_score_pairs
                or any(k.startswith(f"goal:{event_id}:{score_text}:") for k in sent_keys)):
            continue
        score_espn_id, score_espn_url = espn_identity(match)
        signals.append({
            "kind": "score_update", "key": key, "priority": 110 + int(importance_fn(base) or 0),
            "home": _team_name(base, "home"), "away": _team_name(base, "away"),
            "league": base.get("league_name") or match.get("league") or "Football",
            "score": score_text, "minute": match.get("minute"),
            "source": match.get("source") or "source live", "follow_ref": ref,
            "espn_event_id": score_espn_id, "espn_url": score_espn_url,
        })

    # Un même match peut produire kickoff + goal si le but tombe immédiatement.
    # La priorité garde seulement le signal le plus important par match/key family.
    signals.sort(key=lambda item: (-int(item["priority"]), item["key"]))
    return signals
