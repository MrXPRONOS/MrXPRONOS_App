#!/usr/bin/env python3
"""Moteur Data & Statistiques Actu Foot - Mr XPRONOS.

Sources gratuites / freemium utilisées :
- ESPN public : classement et statistiques de tableau, sans clé.
- SportScore : classement, top buteurs/assists et données joueurs, sans clé.
- OpenLigaDB : contrôle des ligues disponibles, sans compte ni clé.
- TheSportsDB : métadonnées/statistiques complémentaires en fallback gratuit.
- football-data.org : contrôle optionnel, clé gratuite FOOTBALL_DATA_TOKEN.
- API-Football : top buteurs + contrôle optionnel, clé gratuite API_FOOTBALL_KEY.

Le moteur ne dépend d'aucune source payante et fonctionne sans les clés optionnelles.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import requests


ESPN_STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer/{league}/standings"
OPENLIGA_BASE = "https://api.openligadb.de"
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
SPORTSCORE_BASE = "https://sportscore.com"

USER_AGENT = "MrXPRONOS-Stats/1.0"


@dataclass(frozen=True)
class LeagueSpec:
    key: str
    label: str
    espn: str
    football_data: str | None = None
    api_football: int | None = None
    openliga: str | None = None
    sportscore: str | None = None


LEAGUES: tuple[LeagueSpec, ...] = (
    LeagueSpec("premier-league", "Premier League", "eng.1", "PL", 39, None, "premier-league"),
    LeagueSpec("laliga", "La Liga", "esp.1", "PD", 140, None, "la-liga"),
    LeagueSpec("serie-a", "Serie A", "ita.1", "SA", 135, None, "serie-a"),
    LeagueSpec("bundesliga", "Bundesliga", "ger.1", "BL1", 78, "bl1", "bundesliga"),
    LeagueSpec("ligue-1", "Ligue 1", "fra.1", "FL1", 61, None, "ligue-1"),
    LeagueSpec("primeira-liga", "Primeira Liga", "por.1", "PPL", 94, None, "primeira-liga"),
    LeagueSpec("eredivisie", "Eredivisie", "ned.1", "DED", 88, None, "eredivisie"),
)


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _plain(value))
    text = text.encode("ascii", "ignore").decode().casefold()
    text = re.sub(r"\b(fc|cf|sc|afc|club|the|de|da|do|calcio|football)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _number(value: Any) -> float | None:
    if value in (None, "", "-", "—"):
        return None
    try:
        n = float(str(value).replace(",", "."))
        return n if n == n else None
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    n = _number(value)
    return int(n) if n is not None else None


def _season_start(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def choose_league(day: date) -> LeagueSpec:
    # Rotation stable et reproductible : pas de hasard, donc simple à tester.
    return LEAGUES[day.toordinal() % len(LEAGUES)]


def _stats_map(stats: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in stats if isinstance(stats, list) else []:
        if not isinstance(item, dict):
            continue
        name = _plain(item.get("name") or item.get("type")).casefold()
        if not name:
            continue
        value = item.get("value")
        if value is None:
            value = item.get("displayValue")
        out[name] = value
    return out


def _pick(stats: dict[str, Any], *names: str) -> Any:
    normalized = {re.sub(r"[^a-z0-9]", "", k): v for k, v in stats.items()}
    for name in names:
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        if key in normalized:
            return normalized[key]
    return None


def _espn_entries(node: Any) -> list[dict]:
    """Cherche récursivement les tableaux standings.entries sans dépendre du groupe."""
    found: list[dict] = []
    if isinstance(node, dict):
        standings = node.get("standings")
        if isinstance(standings, dict) and isinstance(standings.get("entries"), list):
            found.extend(x for x in standings["entries"] if isinstance(x, dict))
        for value in node.values():
            if isinstance(value, (dict, list)):
                found.extend(_espn_entries(value))
    elif isinstance(node, list):
        for value in node:
            if isinstance(value, (dict, list)):
                found.extend(_espn_entries(value))
    return found


def fetch_espn_standings(
    session: requests.Session,
    spec: LeagueSpec,
    *,
    season: int | None = None,
) -> list[dict]:
    params = {"season": str(season)} if season else None
    try:
        response = session.get(
            ESPN_STANDINGS.format(league=spec.espn),
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    for entry in _espn_entries(payload):
        team = entry.get("team") if isinstance(entry.get("team"), dict) else {}
        name = _plain(team.get("displayName") or team.get("name"))
        if not name or _norm(name) in seen:
            continue
        seen.add(_norm(name))
        stats = _stats_map(entry.get("stats"))
        row = {
            "source": "ESPN",
            "team": name,
            "team_id": str(team.get("id") or ""),
            "rank": _integer(_pick(stats, "rank", "playoffSeed")),
            "played": _integer(_pick(stats, "gamesPlayed", "games", "gp")),
            "wins": _integer(_pick(stats, "wins", "win")),
            "draws": _integer(_pick(stats, "ties", "draws", "draw")),
            "losses": _integer(_pick(stats, "losses", "loss")),
            "points": _integer(_pick(stats, "points", "pts")),
            "goals_for": _integer(_pick(stats, "pointsFor", "goalsFor", "for")),
            "goals_against": _integer(_pick(stats, "pointsAgainst", "goalsAgainst", "against")),
            "goal_diff": _integer(_pick(stats, "pointDifferential", "goalDifference", "goalDiff")),
            "form": _plain(_pick(stats, "streak", "lastFive", "form")),
        }
        rows.append(row)

    # Rank peut manquer sur certains groupes ; points puis différence de buts donnent
    # un ordre de secours, sans prétendre résoudre tous les tie-breaks officiels.
    if any(row.get("rank") is not None for row in rows):
        rows.sort(key=lambda x: (x.get("rank") is None, x.get("rank") or 999))
    else:
        rows.sort(
            key=lambda x: (
                -(x.get("points") or 0),
                -(x.get("goal_diff") or 0),
                -(x.get("goals_for") or 0),
                x["team"],
            )
        )
        for idx, row in enumerate(rows, 1):
            row["rank"] = idx
    return rows


def _nested_lists(node: Any) -> list[list[dict]]:
    found: list[list[dict]] = []
    if isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node):
            found.append(node)
        for item in node:
            if isinstance(item, (dict, list)):
                found.extend(_nested_lists(item))
    elif isinstance(node, dict):
        for value in node.values():
            if isinstance(value, (dict, list)):
                found.extend(_nested_lists(value))
    return found


def fetch_sportscore_standings(
    session: requests.Session,
    spec: LeagueSpec,
) -> list[dict]:
    if not spec.sportscore:
        return []
    try:
        response = session.get(
            SPORTSCORE_BASE + "/api/v1/standings/",
            params={"sport": "football", "slug": spec.sportscore, "src": "mrxpronos"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    best: list[dict] = []
    for candidate in _nested_lists(payload):
        if len(candidate) < 3:
            continue
        score = sum(
            1 for item in candidate[:5]
            if any(k in item for k in ("team", "team_name", "name"))
            and any(k in item for k in ("position", "rank", "points", "pts"))
        )
        if score > 0 and len(candidate) > len(best):
            best = candidate

    rows: list[dict] = []
    for idx, item in enumerate(best, 1):
        team_obj = item.get("team") if isinstance(item.get("team"), dict) else {}
        name = _plain(
            team_obj.get("name") or team_obj.get("displayName")
            or item.get("team_name") or item.get("teamName")
            or (item.get("name") if not isinstance(item.get("name"), dict) else "")
        )
        if not name:
            continue
        played = _integer(item.get("played") or item.get("matches") or item.get("games"))
        wins = _integer(item.get("wins") or item.get("won"))
        draws = _integer(item.get("draws") or item.get("draw"))
        losses = _integer(item.get("losses") or item.get("lost"))
        rows.append({
            "source": "SportScore",
            "team": name,
            "team_id": str(team_obj.get("id") or item.get("team_id") or item.get("teamId") or ""),
            "rank": _integer(item.get("position") or item.get("rank")) or idx,
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points": _integer(item.get("points") or item.get("pts")),
            "goals_for": _integer(item.get("goals_for") or item.get("goalsFor") or item.get("gf")),
            "goals_against": _integer(item.get("goals_against") or item.get("goalsAgainst") or item.get("ga")),
            "goal_diff": _integer(item.get("goal_diff") or item.get("goalDifference") or item.get("gd")),
            "form": _plain(item.get("form")),
        })
    return rows


def fetch_sportscore_top_scorers(
    session: requests.Session,
    spec: LeagueSpec,
) -> list[dict]:
    if not spec.sportscore:
        return []
    try:
        response = session.get(
            SPORTSCORE_BASE + "/api/v1/topscorers/",
            params={
                "sport": "football", "slug": spec.sportscore,
                "limit": "20", "stat": "goals", "src": "mrxpronos",
            },
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    best: list[dict] = []
    for candidate in _nested_lists(payload):
        if not candidate:
            continue
        score = sum(
            1 for item in candidate[:5]
            if any(k in item for k in ("player", "name", "player_name"))
            and any(k in item for k in ("goals", "value", "total"))
        )
        if score > 0 and len(candidate) > len(best):
            best = candidate

    rows = []
    for item in best:
        player_obj = item.get("player") if isinstance(item.get("player"), dict) else {}
        team_obj = item.get("team") if isinstance(item.get("team"), dict) else {}
        name = _plain(
            player_obj.get("name") or player_obj.get("displayName")
            or item.get("player_name") or item.get("name")
        )
        goals = _integer(item.get("goals") or item.get("value") or item.get("total"))
        if not name or goals is None:
            continue
        rows.append({
            "source": "SportScore",
            "player": name,
            "goals": goals,
            "assists": _integer(item.get("assists")),
            "appearances": _integer(item.get("appearances") or item.get("played")),
            "team": _plain(team_obj.get("name") or item.get("team_name") or item.get("teamName")),
        })
    rows.sort(key=lambda x: (-x["goals"], x["player"]))
    return rows[:10]


def fetch_football_data_standings(
    session: requests.Session,
    spec: LeagueSpec,
    *,
    season: int,
) -> list[dict]:
    token = (os.getenv("FOOTBALL_DATA_TOKEN") or "").strip()
    if not token or not spec.football_data:
        return []
    try:
        response = session.get(
            f"{FOOTBALL_DATA_BASE}/competitions/{spec.football_data}/standings",
            params={"season": str(season)},
            headers={"X-Auth-Token": token, "User-Agent": USER_AGENT},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    standings = payload.get("standings") if isinstance(payload, dict) else None
    total = next(
        (x for x in standings or [] if isinstance(x, dict) and x.get("type") == "TOTAL"),
        None,
    )
    table = total.get("table") if isinstance(total, dict) else None
    rows: list[dict] = []
    for item in table if isinstance(table, list) else []:
        if not isinstance(item, dict):
            continue
        team = item.get("team") if isinstance(item.get("team"), dict) else {}
        name = _plain(team.get("name") or team.get("shortName"))
        if not name:
            continue
        rows.append({
            "source": "football-data.org",
            "team": name,
            "team_id": str(team.get("id") or ""),
            "rank": _integer(item.get("position")),
            "played": _integer(item.get("playedGames")),
            "wins": _integer(item.get("won")),
            "draws": _integer(item.get("draw")),
            "losses": _integer(item.get("lost")),
            "points": _integer(item.get("points")),
            "goals_for": _integer(item.get("goalsFor")),
            "goals_against": _integer(item.get("goalsAgainst")),
            "goal_diff": _integer(item.get("goalDifference")),
            "form": _plain(item.get("form")),
        })
    return rows


def fetch_openliga_table(
    session: requests.Session,
    spec: LeagueSpec,
    *,
    season: int,
) -> list[dict]:
    if not spec.openliga:
        return []
    try:
        response = session.get(
            f"{OPENLIGA_BASE}/getbltable/{spec.openliga}/{season}",
            headers={"User-Agent": USER_AGENT},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    rows: list[dict] = []
    for idx, item in enumerate(payload if isinstance(payload, list) else [], 1):
        if not isinstance(item, dict):
            continue
        name = _plain(item.get("TeamName") or item.get("teamName"))
        if not name:
            continue
        goals_for = _integer(item.get("Goals") if "Goals" in item else item.get("goals"))
        goals_against = _integer(
            item.get("OpponentGoals") if "OpponentGoals" in item else item.get("opponentGoals")
        )
        goal_diff = _integer(item.get("GoalDiff") if "GoalDiff" in item else item.get("goalDiff"))
        if goal_diff is None and goals_for is not None and goals_against is not None:
            goal_diff = goals_for - goals_against
        rows.append({
            "source": "OpenLigaDB",
            "team": name,
            "team_id": str(item.get("TeamInfoId") or item.get("teamInfoId") or ""),
            "rank": idx,
            "played": _integer(item.get("Matches") if "Matches" in item else item.get("matches")),
            "wins": _integer(item.get("Won") if "Won" in item else item.get("won")),
            "draws": _integer(item.get("Draw") if "Draw" in item else item.get("draw")),
            "losses": _integer(item.get("Lost") if "Lost" in item else item.get("lost")),
            "points": _integer(item.get("Points") if "Points" in item else item.get("points")),
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goal_diff": goal_diff,
            "form": "",
        })
    return rows


def fetch_openliga_top_scorers(
    session: requests.Session,
    spec: LeagueSpec,
    *,
    season: int,
) -> list[dict]:
    if not spec.openliga:
        return []
    try:
        response = session.get(
            f"{OPENLIGA_BASE}/getgoalgetters/{spec.openliga}/{season}",
            headers={"User-Agent": USER_AGENT},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    rows = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        name = _plain(item.get("goalGetterName") or item.get("GoalGetterName"))
        goals = _integer(item.get("goalCount") if "goalCount" in item else item.get("GoalCount"))
        if name and goals is not None:
            rows.append({
                "source": "OpenLigaDB",
                "player": name,
                "goals": goals,
                "assists": None,
                "appearances": None,
                "team": _plain(item.get("teamName") or item.get("TeamName")),
            })
    rows.sort(key=lambda x: (-x["goals"], x["player"]))
    return rows[:10]


def fetch_api_football_top_scorers(
    session: requests.Session,
    spec: LeagueSpec,
    *,
    season: int,
) -> list[dict]:
    key = (os.getenv("API_FOOTBALL_KEY") or "").strip()
    if not key or not spec.api_football:
        return []
    try:
        response = session.get(
            API_FOOTBALL_BASE + "/players/topscorers",
            params={"league": str(spec.api_football), "season": str(season)},
            headers={"x-apisports-key": key, "User-Agent": USER_AGENT},
            timeout=(7, 22),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []

    rows = []
    for item in payload.get("response", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        player = item.get("player") if isinstance(item.get("player"), dict) else {}
        stats = item.get("statistics") or []
        stat = stats[0] if isinstance(stats, list) and stats and isinstance(stats[0], dict) else {}
        goals = stat.get("goals") if isinstance(stat.get("goals"), dict) else {}
        games = stat.get("games") if isinstance(stat.get("games"), dict) else {}
        name = _plain(player.get("name"))
        total = _integer(goals.get("total"))
        if name and total is not None:
            rows.append({
                "source": "API-Football",
                "player": name,
                "goals": total,
                "assists": _integer(goals.get("assists")),
                "appearances": _integer(games.get("appearences") or games.get("appearances")),
                "team": _plain((stat.get("team") or {}).get("name") if isinstance(stat.get("team"), dict) else ""),
            })
    return rows[:10]


def _find_team(table: list[dict], name: str) -> dict | None:
    target = _norm(name)
    exact = next((row for row in table if _norm(row.get("team")) == target), None)
    if exact:
        return exact
    target_tokens = set(target.split())
    best, score = None, 0.0
    for row in table:
        tokens = set(_norm(row.get("team")).split())
        if not tokens or not target_tokens:
            continue
        value = len(tokens & target_tokens) / max(len(tokens | target_tokens), 1)
        if value > score:
            best, score = row, value
    return best if score >= 0.5 else None


def table_agreement(primary: list[dict], secondary: list[dict]) -> float:
    if not primary or not secondary:
        return 0.0
    checked = 0
    points = 0.0
    for row in primary[:8]:
        other = _find_team(secondary, row["team"])
        if not other:
            continue
        checked += 1
        if row.get("rank") == other.get("rank"):
            points += 1.0
        elif row.get("rank") and other.get("rank") and abs(row["rank"] - other["rank"]) == 1:
            points += 0.6
        if row.get("points") is not None and row.get("points") == other.get("points"):
            points += 0.5
    return min(1.0, points / max(checked * 1.5, 1)) if checked else 0.0


def collect_snapshot(
    session: requests.Session,
    day: date,
    *,
    spec: LeagueSpec | None = None,
) -> dict:
    spec = spec or choose_league(day)
    season = _season_start(day)
    sources: dict[str, list[dict]] = {}

    espn = fetch_espn_standings(session, spec, season=season)
    if espn:
        sources["ESPN"] = espn

    football_data = fetch_football_data_standings(session, spec, season=season)
    if football_data:
        sources["football-data.org"] = football_data

    openliga = fetch_openliga_table(session, spec, season=season)
    if openliga:
        sources["OpenLigaDB"] = openliga

    primary = espn or football_data or openliga
    source_name = "ESPN" if espn else "football-data.org" if football_data else "OpenLigaDB" if openliga else ""
    agreements = []
    for name, table in sources.items():
        if table is primary:
            continue
        agreements.append(table_agreement(primary, table))

    confidence = 0
    if primary:
        confidence = 82
        if agreements:
            confidence += round(12 * max(agreements))
        if len(sources) >= 3:
            confidence += 4
        confidence = min(98, confidence)

    return {
        "league": spec.label,
        "league_key": spec.key,
        "season": season,
        "source": source_name,
        "sources": list(sources.keys()),
        "confidence": confidence,
        "table": primary,
        "top_scorers": (
            fetch_api_football_top_scorers(session, spec, season=season)
            or fetch_openliga_top_scorers(session, spec, season=season)
        ),
    }


def _rate(row: dict, numerator: str) -> float | None:
    played = row.get("played")
    value = row.get(numerator)
    if not played or value is None:
        return None
    return round(float(value) / float(played), 2)


def build_insight(snapshot: dict, *, variant: int = 0) -> dict | None:
    table = snapshot.get("table") or []
    if len(table) < 4:
        return None
    league = snapshot.get("league") or "Football"
    sources = snapshot.get("sources") or []
    source_text = " + ".join(sources[:3])
    confidence = int(snapshot.get("confidence") or 0)

    # API-Football devient un format supplémentaire uniquement si la clé gratuite
    # est configurée et si au moins trois buteurs sont disponibles.
    scorers = snapshot.get("top_scorers") or []
    if variant % 6 == 5 and len(scorers) >= 3:
        top = scorers[:3]
        return {
            "kind": "top_scorers",
            "title": f"🎯 TOP BUTEURS • {league}",
            "headline": f"{top[0]['player']} mène avec {top[0]['goals']} buts",
            "lines": [
                f"1. {x['player']} — {x['goals']} buts" + (f" • {x['team']}" if x.get("team") else "")
                for x in top
            ],
            "source": top[0].get("source") or "source buteurs",
            "confidence": max(confidence, 90),
        }

    variant %= 5
    if variant == 0:
        top = table[:3]
        return {
            "kind": "standings",
            "title": f"🏆 CLASSEMENT • {league}",
            "headline": f"{top[0]['team']} est leader avec {top[0].get('points', '—')} points",
            "lines": [
                f"{row.get('rank', i)}. {row['team']} — {row.get('points', '—')} pts"
                for i, row in enumerate(top, 1)
            ],
            "source": source_text,
            "confidence": confidence,
        }

    if variant == 1:
        eligible = [row for row in table if row.get("goals_for") is not None and row.get("played")]
        if not eligible:
            return build_insight(snapshot, variant=0)
        best = max(eligible, key=lambda row: (row["goals_for"], _rate(row, "goals_for") or 0))
        rate = _rate(best, "goals_for")
        return {
            "kind": "attack",
            "title": f"🔥 MEILLEURE ATTAQUE • {league}",
            "headline": f"{best['team']} : {best['goals_for']} buts en {best['played']} matchs",
            "lines": [
                f"Moyenne : {rate:.2f} but{'s' if rate != 1 else ''}/match" if rate is not None else "",
                f"Classement : {best.get('rank', '—')}e • {best.get('points', '—')} pts",
            ],
            "source": source_text,
            "confidence": confidence,
        }

    if variant == 2:
        eligible = [row for row in table if row.get("goals_against") is not None and row.get("played")]
        if not eligible:
            return build_insight(snapshot, variant=0)
        best = min(eligible, key=lambda row: (row["goals_against"], -int(row.get("points") or 0)))
        rate = _rate(best, "goals_against")
        return {
            "kind": "defense",
            "title": f"🧱 MEILLEURE DÉFENSE • {league}",
            "headline": f"{best['team']} n'a encaissé que {best['goals_against']} buts",
            "lines": [
                f"{best['played']} matchs • {rate:.2f} but encaissé/match" if rate is not None else "",
                f"Classement : {best.get('rank', '—')}e • {best.get('points', '—')} pts",
            ],
            "source": source_text,
            "confidence": confidence,
        }

    if variant == 3:
        top = table[:4]
        leader_points = top[0].get("points")
        fourth_points = top[-1].get("points")
        if leader_points is None or fourth_points is None:
            return build_insight(snapshot, variant=0)
        gap = leader_points - fourth_points
        return {
            "kind": "title_race",
            "title": f"⚔️ COURSE EN TÊTE • {league}",
            "headline": f"Seulement {gap} point{'s' if gap != 1 else ''} entre le 1er et le 4e",
            "lines": [
                f"{row.get('rank', i)}. {row['team']} — {row.get('points', '—')} pts"
                for i, row in enumerate(top, 1)
            ],
            "source": source_text,
            "confidence": confidence,
        }

    eligible = [
        row for row in table
        if row.get("wins") is not None and row.get("played") and row.get("played") >= 3
    ]
    if not eligible:
        return build_insight(snapshot, variant=0)
    best = max(eligible, key=lambda row: (row["wins"] / row["played"], row["wins"]))
    win_rate = round(100 * best["wins"] / best["played"])
    return {
        "kind": "wins",
        "title": f"📈 EFFICACITÉ • {league}",
        "headline": f"{best['team']} gagne {win_rate}% de ses matchs",
        "lines": [
            f"{best['wins']} victoires en {best['played']} matchs",
            f"{best.get('points', '—')} points • différence de buts {best.get('goal_diff', '—')}",
        ],
        "source": source_text,
        "confidence": confidence,
    }


def daily_insight(session: requests.Session, day: date) -> dict | None:
    snapshot = collect_snapshot(session, day)
    # Rotation différente de la ligue pour éviter de publier le même angle
    # deux jours consécutifs.
    variant = (day.toordinal() // len(LEAGUES)) % 6
    insight = build_insight(snapshot, variant=variant)
    if insight:
        insight["league"] = snapshot["league"]
        insight["league_key"] = snapshot["league_key"]
        insight["season"] = snapshot["season"]
        insight["sources_used"] = snapshot["sources"]
    return insight


def source_health(session: requests.Session, day: date) -> dict[str, Any]:
    """Contrôle réseau léger, utilisable par la CI sans clé payante."""
    premier = LEAGUES[0]
    espn = fetch_espn_standings(session, premier, season=_season_start(day))
    openliga = fetch_openliga_table(
        session,
        next(x for x in LEAGUES if x.openliga),
        season=_season_start(day),
    )
    return {
        "espn_rows": len(espn),
        "openliga_rows": len(openliga),
        "football_data_configured": bool((os.getenv("FOOTBALL_DATA_TOKEN") or "").strip()),
        "api_football_configured": bool((os.getenv("API_FOOTBALL_KEY") or "").strip()),
    }


if __name__ == "__main__":
    session = requests.Session()
    today = datetime.now(timezone.utc).date()
    print(daily_insight(session, today))
