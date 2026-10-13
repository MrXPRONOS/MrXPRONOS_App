#!/usr/bin/env python3
"""Sources gratuites et détection d'états pour le cycle d'un match Actu Foot.

Priorité:
1. Cache live Supabase déjà alimenté par BSD + ESPN (si secrets disponibles).
2. ESPN public Site API, sans clé.
3. OpenLigaDB, sans inscription ni clé, comme contrôle supplémentaire Bundesliga.

Aucune source payante n'est requise par ce module.
"""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary"
OPENLIGA_BASE = "https://api.openligadb.de"


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
        "status_detail": _plain(typ.get("shortDetail") or typ.get("detail") or typ.get("description") or typ.get("name")),
        "event_date": event.get("date") or competition.get("date"),
        "league": _plain((competition.get("league") or {}).get("name") or event.get("league")),
        "raw": event,
    }


def fetch_espn_day(session: requests.Session, day: date) -> list[dict]:
    try:
        response = session.get(
            ESPN_SCOREBOARD,
            params={"dates": day.strftime("%Y%m%d"), "limit": "1000"},
            headers={"User-Agent": "MrXPRONOS-ActuFoot/2.0"},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []
    result = []
    for event in payload.get("events", []) if isinstance(payload, dict) else []:
        if isinstance(event, dict):
            parsed = parse_espn_event(event)
            if parsed and parsed["home_team"] and parsed["away_team"]:
                result.append(parsed)
    return result


def fetch_espn_summary(session: requests.Session, event_id: str) -> dict:
    if not event_id:
        return {}
    try:
        response = session.get(
            ESPN_SUMMARY,
            params={"event": event_id},
            headers={"User-Agent": "MrXPRONOS-ActuFoot/2.0"},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except (requests.RequestException, ValueError):
        return {}


def extract_lineups(summary: dict) -> dict[str, list[str]]:
    """Retourne seulement des compositions suffisamment complètes (>=8 titulaires)."""
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
        if len(starters) >= 8:
            result[side] = starters[:11]
    return result


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
        player = ""
        if isinstance(athletes, list) and athletes and isinstance(athletes[0], dict):
            player = _plain(athletes[0].get("displayName") or athletes[0].get("fullName"))
        clock = item.get("clock") if isinstance(item.get("clock"), dict) else {}
        minute_text = _plain(clock.get("displayValue") or item.get("time") or "")
        minute_match = re.search(r"\d+", minute_text)
        minute = int(minute_match.group()) if minute_match else None
        team_obj = item.get("team") if isinstance(item.get("team"), dict) else {}
        goals.append({
            "player": player,
            "minute": minute,
            "minute_text": minute_text,
            "team_id": str(team_obj.get("id") or ""),
            "own_goal": "own goal" in label or "c.s.c" in label,
            "penalty": "penalty" in label or "pen." in label,
        })
    return goals


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
        if similarity < 0.48:
            continue
        et = _moment(item.get("event_date"))
        if bt and et:
            hours = abs((bt - et).total_seconds()) / 3600
            if hours > 8:
                continue
            similarity += max(0, 0.18 - hours * 0.02)
        if similarity > best_score:
            best, best_score = item, similarity
    return best


def collect_external(session: requests.Session, day: date, base_events: list[dict]) -> list[dict]:
    # ESPN d'abord car il donne aussi les identifiants nécessaires au résumé
    # (compositions / buteurs). Le cache Supabase BSD+ESPN reste le fallback local.
    rows = fetch_espn_day(session, day)
    rows.extend(fetch_supabase_live(session))
    # OpenLigaDB n'est interrogé que si une rencontre Bundesliga est réellement
    # présente dans notre journée BSD; pas de trafic inutile.
    if any("bundesliga" in _plain(event.get("league_name") or event.get("league")).lower() for event in base_events):
        rows.extend(fetch_openligadb_bundesliga(session, day))
    return rows


def is_halftime(match: dict) -> bool:
    detail = _plain(match.get("status_detail")).lower()
    return (
        "half time" in detail or "halftime" in detail or "mi-temps" in detail
        or "half-time" in detail
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
) -> list[dict]:
    """Construit les transitions publiables, triées par urgence éditoriale."""
    today = now.astimezone(timezone.utc).date()
    external = collect_external(session, today, base_events)
    # Mode lifecycle léger : si aucun calendrier BSD n'est fourni, ESPN/cache
    # live devient temporairement la liste de base. Cela évite toute requête
    # BSD dans les passages rapides de 10 minutes.
    if not base_events:
        base_events = [
            item for item in external
            if item.get("source") in {"espn", "supabase_live"}
            and item.get("home_team") and item.get("away_team")
        ]
    signals: list[dict] = []
    summary_cache: dict[str, dict] = {}

    def summary_for(event_id: str) -> dict:
        if event_id not in summary_cache:
            # Budget implicite: uniquement les matchs importants et proches/live
            # appellent ce helper.
            summary_cache[event_id] = fetch_espn_summary(session, event_id)
        return summary_cache[event_id]

    for base in base_events:
        ext = best_external_match(base, external)
        if not ext:
            continue
        event_id = str(ext.get("id") or base.get("id") or "")
        home = _team_name(base, "home")
        away = _team_name(base, "away")
        league = _plain(base.get("league_name") or base.get("competition_name") or ext.get("league") or "Football")
        kickoff = _event_time(base) or _moment(ext.get("event_date"))
        minute = int(ext.get("minute") or 0)
        hs = _score(ext.get("home_score"))
        aws = _score(ext.get("away_score"))
        score_text = f"{hs}-{aws}" if hs is not None and aws is not None else ""
        importance = int(importance_fn(base) or 0)
        if importance <= 0:
            continue
        source = _plain(ext.get("source") or "source live")

        # Composition: on ne demande le résumé ESPN que pour des matchs proches.
        if kickoff and -timedelta(minutes=8) <= kickoff - now <= timedelta(minutes=85):
            lineup_key = "composition:" + event_id
            if lineup_key not in sent_keys and ext.get("source") == "espn":
                summary = summary_for(event_id)
                lineups = extract_lineups(summary)
                if len(lineups["home"]) >= 8 and len(lineups["away"]) >= 8:
                    signals.append({
                        "kind": "composition", "key": lineup_key, "priority": 70 + importance,
                        "home": home, "away": away, "league": league, "kickoff": kickoff,
                        "lineups": lineups, "source": "ESPN",
                    })

        # Coup d'envoi: uniquement au tout début.
        if is_live(ext) and 0 <= minute <= 12:
            key = "kickoff:" + event_id
            if key not in sent_keys:
                signals.append({
                    "kind": "kickoff", "key": key, "priority": 80 + importance,
                    "home": home, "away": away, "league": league, "minute": minute,
                    "score": score_text or "0-0", "source": source,
                })

        if is_halftime(ext):
            key = "mi_temps:" + event_id
            if key not in sent_keys:
                signals.append({
                    "kind": "mi_temps", "key": key, "priority": 90 + importance,
                    "home": home, "away": away, "league": league,
                    "score": score_text, "source": source,
                })

        # But/changement de score: ESPN permet d'identifier le dernier buteur.
        if (
            is_live(ext) and ext.get("source") == "espn"
            and hs is not None and aws is not None and hs + aws > 0
        ):
            summary = summary_for(event_id)
            goals = extract_goals(summary)
            last_goal = goals[-1] if goals else {}
            goal_minute = last_goal.get("minute")
            # Pour un BUT, pas de publication sans événement ESPN identifiable.
            # Cela évite de transformer un score découvert tardivement en alerte instantanée.
            recent_goal = (
                bool(last_goal)
                and goal_minute is not None
                and (minute <= 0 or 0 <= minute - goal_minute <= 14)
            )
            scorer_key = _norm(last_goal.get("player") or "unknown").replace(" ", "-")[:42]
            key = f"goal:{event_id}:{hs}-{aws}:{goal_minute}:{scorer_key}"
            if key not in sent_keys and recent_goal:
                signals.append({
                    "kind": "goal", "key": key, "priority": 100 + importance,
                    "home": home, "away": away, "league": league, "minute": minute,
                    "score": score_text, "source": "ESPN" if summary else source,
                    "goal": last_goal,
                    "home_team_id": ext.get("home_team_id"),
                    "away_team_id": ext.get("away_team_id"),
                })

    # Un même match peut produire kickoff + goal si le but tombe immédiatement.
    # La priorité garde seulement le signal le plus important par match/key family.
    signals.sort(key=lambda item: (-int(item["priority"]), item["key"]))
    return signals
