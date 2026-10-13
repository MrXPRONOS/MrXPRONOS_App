"""Free multi-source football adapters for Mr XPRONOS.

Sources are used as enrichment/fallback around BSD, never as blind replacements
for model identifiers. Public-source ranking is field-aware:
ESPN > SportScore > BSD > TheSportsDB > OpenLigaDB for live/detail quality,
while BSD remains authoritative for the historical IDs used by the prediction model.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
SPORTSCORE_FIXTURES = "https://sportscore.com/api/v1/fixtures/"
SPORTSCORE_MATCH = "https://sportscore.com/api/v1/match/"
SPORTSCORE_TEAM = "https://sportscore.com/api/v1/team/"
SPORTSCORE_H2H = "https://sportscore.com/api/v1/h2h/"
SPORTSCORE_SEARCH = "https://sportscore.com/api/v1/search/"
THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"
OPENLIGA_BASE = "https://api.openligadb.de"

SOURCE_QUALITY = {
    "espn": {"overall": 98, "live": 99, "detail": 99, "coverage": 91, "odds": 0},
    "sportscore": {"overall": 92, "live": 95, "detail": 93, "coverage": 96, "odds": 35},
    "bsd": {"overall": 89, "live": 91, "detail": 91, "coverage": 98, "odds": 90},
    "thesportsdb": {"overall": 79, "live": 55, "detail": 82, "coverage": 73, "odds": 0},
    "openligadb": {"overall": 76, "live": 66, "detail": 69, "coverage": 54, "odds": 0},
}
SOURCE_ORDER = ("espn", "sportscore", "bsd", "thesportsdb", "openligadb")
CACHE_DIR = Path("bsd/cache/free_sources")


@dataclass
class SourceSnapshot:
    provider: str
    rows: List[Dict[str, Any]]
    fetched_at: str
    error: str = ""


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _plain(value)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(fc|cf|sc|afc|club|fk|ac|as|cd|ud|u23|u21|women|w)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _tokens_similarity(a: Any, b: Any) -> float:
    aa, bb = set(_norm(a).split()), set(_norm(b).split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def _moment(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _score(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = int(float(value))
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(value)).strip("-")


def _cache_file(provider: str, key: str) -> Path:
    digest = hashlib.sha256((provider + "|" + key).encode()).hexdigest()
    return CACHE_DIR / (digest + ".json")


def _cached(provider: str, key: str, ttl: int) -> Optional[Any]:
    if ttl <= 0:
        return None
    p = _cache_file(provider, key)
    try:
        saved = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - float(saved["saved_at"]) <= ttl:
            return saved["payload"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return None


def _save(provider: str, key: str, payload: Any) -> None:
    p = _cache_file(provider, key)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"saved_at": time.time(), "payload": payload}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def _json_get(session: requests.Session, provider: str, url: str, *, params: Dict[str, Any], ttl: int) -> Any:
    key = url + "?" + json.dumps(params, sort_keys=True, separators=(",", ":"))
    cached = _cached(provider, key, ttl)
    if cached is not None:
        return cached
    headers = {
        "Accept": "application/json",
        "User-Agent": "MrXPRONOS-MultiSource/1.0",
    }
    if provider == "sportscore":
        params = {**params, "src": "mrxpronos"}
    response = session.get(url, params=params, headers=headers, timeout=(6, 16), allow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, (dict, list)):
        raise ValueError(provider + " non-JSON object/list")
    _save(provider, key, payload)
    return payload


def _state_from_status(raw: Any) -> str:
    text = _plain(raw).lower()
    if any(x in text for x in ("finished", "full time", "final", "ft", "ended")):
        return "post"
    if any(x in text for x in ("live", "in progress", "1st half", "2nd half", "half time", "halftime")):
        return "in"
    if any(x in text for x in ("scheduled", "upcoming", "not started", "notstarted")):
        return "pre"
    if any(x in text for x in ("cancel", "postpon", "abandon", "suspend")):
        return "postponed"
    return text or "pre"


def _base_row(provider: str, provider_id: Any, home: Any, away: Any, when: Any) -> Dict[str, Any]:
    return {
        "source": provider,
        "provider_quality": SOURCE_QUALITY[provider],
        "id": f"{provider}:{provider_id}",
        "provider_event_id": str(provider_id or ""),
        "home_team": _plain(home),
        "away_team": _plain(away),
        "event_date": _moment(when).isoformat() if _moment(when) else _plain(when),
        "raw": {},
    }


def fetch_espn_day(session: requests.Session, day: date, *, ttl: int = 35) -> SourceSnapshot:
    try:
        payload = _json_get(session, "espn", ESPN_SCOREBOARD, params={"dates": day.strftime("%Y%m%d"), "limit": 1000}, ttl=ttl)
        rows = []
        for event in payload.get("events", []) if isinstance(payload, dict) else []:
            comps = event.get("competitions") or []
            comp = comps[0] if comps and isinstance(comps[0], dict) else {}
            competitors = comp.get("competitors") or []
            home = next((x for x in competitors if isinstance(x, dict) and x.get("homeAway") == "home"), None)
            away = next((x for x in competitors if isinstance(x, dict) and x.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            ht = home.get("team") if isinstance(home.get("team"), dict) else {}
            at = away.get("team") if isinstance(away.get("team"), dict) else {}
            status = comp.get("status") or event.get("status") or {}
            typ = status.get("type") if isinstance(status.get("type"), dict) else {}
            row = _base_row("espn", event.get("id") or comp.get("id"), ht.get("displayName") or ht.get("name"), at.get("displayName") or at.get("name"), event.get("date") or comp.get("date"))
            row.update({
                "home_score": _score(home.get("score")), "away_score": _score(away.get("score")),
                "home_logo": ht.get("logo") or "", "away_logo": at.get("logo") or "",
                "state": "post" if typ.get("completed") else _state_from_status(typ.get("state") or typ.get("detail")),
                "status_detail": _plain(typ.get("shortDetail") or typ.get("detail") or typ.get("description") or typ.get("name")),
                "league": _plain((comp.get("league") or {}).get("name") or event.get("league")),
                "minute": _score(status.get("displayClock") or status.get("clock")),
                "raw": event,
            })
            rows.append(row)
        return SourceSnapshot("espn", rows, datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        return SourceSnapshot("espn", [], datetime.now(timezone.utc).isoformat(), type(exc).__name__ + ": " + str(exc)[:140])


def _sportscore_rows(payload: Any) -> List[Dict[str, Any]]:
    values = payload.get("matches") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        values = payload.get("fixtures") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        values = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        values = payload.get("meetings") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        values = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(values, list):
        return []
    rows = []
    for item in values:
        if not isinstance(item, dict):
            continue
        home = item.get("home") if not isinstance(item.get("home"), dict) else (item["home"].get("name") or item["home"].get("display_name"))
        away = item.get("away") if not isinstance(item.get("away"), dict) else (item["away"].get("name") or item["away"].get("display_name"))
        if not _plain(home) or not _plain(away):
            continue
        pid = item.get("id") or item.get("match_id") or item.get("slug")
        row = _base_row("sportscore", pid, home, away, item.get("time") or item.get("date") or item.get("start_time"))
        row.update({
            "home_score": _score(item.get("home_score") if item.get("home_score") is not None else item.get("score_home")),
            "away_score": _score(item.get("away_score") if item.get("away_score") is not None else item.get("score_away")),
            "home_logo": item.get("home_logo") or "", "away_logo": item.get("away_logo") or "",
            "state": _state_from_status(item.get("status") or item.get("status_text")),
            "status_detail": _plain(item.get("status_text") or item.get("status")),
            "league": _plain(item.get("competition") or item.get("league")),
            "minute": _score(item.get("minute")),
            "sportscore_slug": _plain(item.get("slug")),
            "raw": item,
        })
        rows.append(row)
    return rows


def fetch_sportscore_day(session: requests.Session, day: date, *, ttl: int = 55) -> SourceSnapshot:
    try:
        payload = _json_get(session, "sportscore", SPORTSCORE_FIXTURES, params={"sport": "football", "date": day.isoformat(), "limit": 200}, ttl=ttl)
        return SourceSnapshot("sportscore", _sportscore_rows(payload), datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        return SourceSnapshot("sportscore", [], datetime.now(timezone.utc).isoformat(), type(exc).__name__ + ": " + str(exc)[:140])


def fetch_sportscore_match(session: requests.Session, slug: str, *, ttl: int = 25) -> Dict[str, Any]:
    if not _plain(slug):
        return {}
    try:
        payload = _json_get(session, "sportscore", SPORTSCORE_MATCH, params={"sport": "football", "slug": slug}, ttl=ttl)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def resolve_sportscore_slug(session: requests.Session, name: str, *, ttl: int = 3600) -> str:
    name = _plain(name)
    if not name:
        return ""
    try:
        payload = _json_get(
            session, "sportscore", SPORTSCORE_SEARCH,
            params={"q": name, "sport": "football", "limit": 8}, ttl=ttl,
        )
    except Exception:
        return _slug(name)
    teams = payload.get("teams") if isinstance(payload, dict) else None
    if not isinstance(teams, list):
        results = payload.get("results") if isinstance(payload, dict) else None
        teams = results.get("teams") if isinstance(results, dict) else results if isinstance(results, list) else []
    best_slug, best_score = "", 0.0
    for item in teams if isinstance(teams, list) else []:
        if not isinstance(item, dict):
            continue
        candidate = _plain(item.get("name") or item.get("title") or item.get("display_name"))
        score = _tokens_similarity(name, candidate)
        slug = _plain(item.get("slug"))
        if slug and score > best_score:
            best_slug, best_score = slug, score
    return best_slug if best_score >= 0.45 else _slug(name)


def fetch_sportscore_team(session: requests.Session, team_name: str, *, limit: int = 10, ttl: int = 300) -> List[Dict[str, Any]]:
    if not _plain(team_name):
        return []
    try:
        slug = resolve_sportscore_slug(session, team_name, ttl=max(ttl, 1800))
        payload = _json_get(session, "sportscore", SPORTSCORE_TEAM, params={"sport": "football", "slug": slug, "limit": min(30, max(1, limit))}, ttl=ttl)
        return _sportscore_rows(payload)
    except Exception:
        return []


def fetch_sportscore_h2h(session: requests.Session, home: str, away: str, *, limit: int = 20, ttl: int = 1800) -> List[Dict[str, Any]]:
    try:
        home_slug = resolve_sportscore_slug(session, home, ttl=max(ttl, 1800))
        away_slug = resolve_sportscore_slug(session, away, ttl=max(ttl, 1800))
        payload = _json_get(session, "sportscore", SPORTSCORE_H2H, params={"sport": "football", "team1": home_slug, "team2": away_slug, "limit": min(50, max(1, limit))}, ttl=ttl)
        return _sportscore_rows(payload)
    except Exception:
        return []


def fetch_thesportsdb_day(session: requests.Session, day: date, *, ttl: int = 120) -> SourceSnapshot:
    try:
        payload = _json_get(session, "thesportsdb", THESPORTSDB_BASE + "/eventsday.php", params={"d": day.isoformat(), "s": "Soccer"}, ttl=ttl)
        events = payload.get("events") if isinstance(payload, dict) else None
        rows = []
        for item in events if isinstance(events, list) else []:
            if not isinstance(item, dict):
                continue
            row = _base_row("thesportsdb", item.get("idEvent"), item.get("strHomeTeam"), item.get("strAwayTeam"), item.get("strTimestamp") or ((item.get("dateEvent") or "") + "T" + (item.get("strTime") or "00:00:00Z")))
            row.update({
                "home_score": _score(item.get("intHomeScore")), "away_score": _score(item.get("intAwayScore")),
                "home_logo": item.get("strHomeTeamBadge") or "", "away_logo": item.get("strAwayTeamBadge") or "",
                "state": _state_from_status(item.get("strStatus")),
                "status_detail": _plain(item.get("strStatus")),
                "league": _plain(item.get("strLeague")),
                "raw": item,
            })
            if row["home_team"] and row["away_team"]:
                rows.append(row)
        return SourceSnapshot("thesportsdb", rows, datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        return SourceSnapshot("thesportsdb", [], datetime.now(timezone.utc).isoformat(), type(exc).__name__ + ": " + str(exc)[:140])


OPENLIGA_SHORTCUTS = tuple(x.strip() for x in os.getenv("OPENLIGA_SHORTCUTS", "bl1,bl2,dfb,cl").split(",") if x.strip())


def _openliga_season(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def fetch_openligadb_day(session: requests.Session, day: date, *, ttl: int = 300) -> SourceSnapshot:
    rows = []
    errors = []
    season = _openliga_season(day)
    for shortcut in OPENLIGA_SHORTCUTS:
        try:
            payload = _json_get(session, "openligadb", f"{OPENLIGA_BASE}/getmatchdata/{quote(shortcut)}/{season}", params={}, ttl=ttl)
            for item in payload if isinstance(payload, list) else []:
                if not isinstance(item, dict):
                    continue
                when = _moment(item.get("matchDateTimeUTC") or item.get("matchDateTime"))
                if not when or when.date() != day:
                    continue
                t1, t2 = item.get("team1") or {}, item.get("team2") or {}
                row = _base_row("openligadb", item.get("matchID"), t1.get("teamName"), t2.get("teamName"), when.isoformat())
                results = item.get("matchResults") if isinstance(item.get("matchResults"), list) else []
                final = next((x for x in results if isinstance(x, dict) and x.get("resultOrderID") == 2), None)
                if final is None and results:
                    final = sorted([x for x in results if isinstance(x, dict)], key=lambda x: x.get("resultOrderID") or 0)[-1]
                row.update({
                    "home_score": _score((final or {}).get("pointsTeam1")),
                    "away_score": _score((final or {}).get("pointsTeam2")),
                    "home_logo": t1.get("teamIconUrl") or "", "away_logo": t2.get("teamIconUrl") or "",
                    "state": "post" if item.get("matchIsFinished") else "pre",
                    "status_detail": "finished" if item.get("matchIsFinished") else "scheduled",
                    "league": shortcut,
                    "raw": item,
                })
                rows.append(row)
        except Exception as exc:
            errors.append(shortcut + ":" + type(exc).__name__)
    return SourceSnapshot("openligadb", rows, datetime.now(timezone.utc).isoformat(), ",".join(errors)[:200])


def collect_free_day(session: requests.Session, day: date, *, include_espn: bool = True) -> Dict[str, SourceSnapshot]:
    snapshots: Dict[str, SourceSnapshot] = {}
    if include_espn:
        snapshots["espn"] = fetch_espn_day(session, day)
    snapshots["sportscore"] = fetch_sportscore_day(session, day)
    snapshots["thesportsdb"] = fetch_thesportsdb_day(session, day)
    snapshots["openligadb"] = fetch_openligadb_day(session, day)
    return snapshots


def _team_name(row: Dict[str, Any], side: str) -> str:
    value = row.get(side + "_team")
    if isinstance(value, dict):
        return _plain(value.get("name") or value.get("displayName"))
    return _plain(value)


def _match_score(base: Dict[str, Any], other: Dict[str, Any]) -> float:
    home = _tokens_similarity(_team_name(base, "home"), other.get("home_team"))
    away = _tokens_similarity(_team_name(base, "away"), other.get("away_team"))
    score = (home + away) / 2
    bt, ot = _moment(base.get("event_date") or base.get("date") or base.get("start_time")), _moment(other.get("event_date"))
    if bt and ot:
        hours = abs((bt - ot).total_seconds()) / 3600
        if hours > 8:
            return 0.0
        score += max(0.0, 0.18 - 0.02 * hours)
    return score


def best_match(base: Dict[str, Any], rows: Iterable[Dict[str, Any]], threshold: float = 0.58) -> Optional[Dict[str, Any]]:
    best, score = None, 0.0
    for row in rows:
        value = _match_score(base, row)
        if value > score:
            best, score = row, value
    return best if best is not None and score >= threshold else None


def enrich_bsd_events(events: List[Dict[str, Any]], snapshots: Dict[str, SourceSnapshot]) -> List[Dict[str, Any]]:
    """Keep BSD IDs/model fields, add free-source references and higher-quality facts."""
    out = []
    for event in events:
        row = dict(event)
        refs: Dict[str, Any] = dict(row.get("_provider_match_refs") or {})
        evidence = []
        for provider in ("espn", "sportscore", "thesportsdb", "openligadb"):
            hit = best_match(event, snapshots.get(provider, SourceSnapshot(provider, [], "")).rows)
            if not hit:
                continue
            refs[provider] = {
                "id": hit.get("provider_event_id"),
                "slug": hit.get("sportscore_slug") or "",
                "quality": SOURCE_QUALITY[provider]["overall"],
                "event_date": hit.get("event_date"),
            }
            evidence.append(provider)
            # Higher-quality providers may correct display facts, but never BSD model IDs.
            if provider in ("espn", "sportscore"):
                for key in ("home_logo", "away_logo"):
                    if hit.get(key) and not row.get(key):
                        row[key] = hit[key]
                if hit.get("state") in ("in", "post") and hit.get("home_score") is not None and hit.get("away_score") is not None:
                    row["_verified_score"] = {
                        "provider": provider,
                        "home": hit["home_score"],
                        "away": hit["away_score"],
                        "state": hit["state"],
                    }
        row["_provider_match_refs"] = refs
        row["_provider_evidence"] = ["bsd", *evidence]
        row["_provider_consensus_count"] = 1 + len(evidence)
        out.append(row)
    return out


def preferred_day_events(snapshots: Dict[str, SourceSnapshot]) -> List[Dict[str, Any]]:
    """Merge free providers into a display/editorial list without BSD identifiers."""
    merged: List[Dict[str, Any]] = []
    for provider in ("espn", "sportscore", "thesportsdb", "openligadb"):
        for row in snapshots.get(provider, SourceSnapshot(provider, [], "")).rows:
            existing = best_match(row, merged, threshold=0.70)
            if existing is None:
                row = dict(row)
                state = str(row.get("state") or "").lower()
                row["status"] = (
                    "finished" if state == "post"
                    else "live" if state == "in"
                    else "postponed" if state == "postponed"
                    else "notstarted"
                )
                row["_provider_evidence"] = [provider]
                row["_provider_consensus_count"] = 1
                merged.append(row)
                continue
            evidence = list(existing.get("_provider_evidence") or [])
            if provider not in evidence:
                evidence.append(provider)
            existing["_provider_evidence"] = evidence
            existing["_provider_consensus_count"] = len(evidence)
            if SOURCE_QUALITY[provider]["overall"] > SOURCE_QUALITY.get(existing.get("source"), {}).get("overall", 0):
                keep = {k: existing.get(k) for k in ("_provider_evidence", "_provider_consensus_count")}
                existing.update(row)
                existing.update(keep)
            state = str(existing.get("state") or "").lower()
            existing["status"] = (
                "finished" if state == "post"
                else "live" if state == "in"
                else "postponed" if state == "postponed"
                else "notstarted"
            )
    return merged


def summarize_h2h(rows: List[Dict[str, Any]], home_name: str, away_name: str) -> Dict[str, Any]:
    meetings = []
    for row in rows:
        if str(row.get("state") or "") != "post":
            continue
        hs, aws = _score(row.get("home_score")), _score(row.get("away_score"))
        if hs is None or aws is None:
            continue
        home_is_fixture_home = _tokens_similarity(row.get("home_team"), home_name) >= 0.45
        away_is_fixture_away = _tokens_similarity(row.get("away_team"), away_name) >= 0.45
        reverse = (
            _tokens_similarity(row.get("home_team"), away_name) >= 0.45
            and _tokens_similarity(row.get("away_team"), home_name) >= 0.45
        )
        if not (home_is_fixture_home and away_is_fixture_away) and not reverse:
            continue
        fixture_home_goals, fixture_away_goals = (hs, aws) if not reverse else (aws, hs)
        meetings.append({
            "date": row.get("event_date"),
            "fixture_home_goals": fixture_home_goals,
            "fixture_away_goals": fixture_away_goals,
            "provider": row.get("source"),
        })
    total = len(meetings)
    home_wins = sum(x["fixture_home_goals"] > x["fixture_away_goals"] for x in meetings)
    away_wins = sum(x["fixture_home_goals"] < x["fixture_away_goals"] for x in meetings)
    draws = total - home_wins - away_wins
    home_goals = sum(x["fixture_home_goals"] for x in meetings)
    away_goals = sum(x["fixture_away_goals"] for x in meetings)
    return {
        "source": "sportscore",
        "total_matches": total,
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "avg_total_goals": round((home_goals + away_goals) / total, 3) if total else None,
        "recent_matches": meetings[:10],
    }


def _generic_player_name(value: Any) -> str:
    if isinstance(value, str):
        return _plain(value)
    if not isinstance(value, dict):
        return ""
    nested = value.get("player") if isinstance(value.get("player"), dict) else value.get("athlete") if isinstance(value.get("athlete"), dict) else value
    return _plain(nested.get("name") or nested.get("displayName") or nested.get("strPlayer") or nested.get("player_name"))


def sportscore_lineups(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    root = payload.get("match") if isinstance(payload.get("match"), dict) else payload
    lineups = root.get("lineups") if isinstance(root, dict) else None
    result: Dict[str, List[str]] = {"home": [], "away": []}
    if isinstance(lineups, dict):
        for side in ("home", "away"):
            group = lineups.get(side)
            if isinstance(group, dict):
                group = group.get("players") or group.get("starters") or group.get("lineup")
            if isinstance(group, list):
                names = []
                for item in group:
                    if isinstance(item, dict) and item.get("starter") is False:
                        continue
                    name = _generic_player_name(item)
                    if name:
                        names.append(name)
                result[side] = names[:11] if len(names) >= 11 else []
    elif isinstance(lineups, list):
        for entry in lineups:
            if not isinstance(entry, dict):
                continue
            side = _plain(entry.get("side") or entry.get("homeAway")).lower()
            if side not in result:
                team = _plain(entry.get("team")).lower()
                side = "home" if team == "home" else "away" if team == "away" else ""
            if not side:
                continue
            players = entry.get("players") or entry.get("starters") or []
            names = [_generic_player_name(x) for x in players if _generic_player_name(x)] if isinstance(players, list) else []
            result[side] = names[:11] if len(names) >= 11 else []
    return result


def sportscore_timeline(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    root = payload.get("match") if isinstance(payload.get("match"), dict) else payload
    timeline = root.get("timeline") if isinstance(root, dict) else None
    if not isinstance(timeline, list):
        timeline = root.get("events") if isinstance(root, dict) and isinstance(root.get("events"), list) else []
    out: List[Dict[str, Any]] = []
    for item in timeline:
        if not isinstance(item, dict):
            continue
        kind = _plain(item.get("type") or item.get("event_type") or item.get("kind")).lower()
        minute_raw = item.get("minute") or item.get("time") or item.get("clock")
        minute = None
        match = re.search(r"\d+", _plain(minute_raw))
        if match:
            minute = int(match.group())
        player = _generic_player_name(item.get("player") or item.get("athlete") or item.get("scorer"))
        assist = _generic_player_name(item.get("assist") or item.get("assistant"))
        out.append({
            "kind": "goal" if "goal" in kind else "card" if "card" in kind else "substitution" if "sub" in kind else kind,
            "player": player,
            "assists": [assist] if assist else [],
            "minute": minute,
            "minute_total": minute,
            "minute_text": _plain(minute_raw),
            "penalty": bool(item.get("penalty")) or "pen" in kind,
            "own_goal": bool(item.get("own_goal") or item.get("ownGoal")),
            "team": _plain(item.get("team")),
            "raw": item,
        })
    return out


def sportscore_goals(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [x for x in sportscore_timeline(payload) if x.get("kind") == "goal"]


def fetch_thesportsdb_event_detail(session: requests.Session, event_id: str, *, ttl: int = 120) -> Dict[str, Any]:
    event_id = re.sub(r"[^0-9]", "", str(event_id or ""))
    if not event_id:
        return {}
    result: Dict[str, Any] = {}
    endpoints = {
        "event": "lookupevent.php",
        "lineup": "lookuplineup.php",
        "timeline": "lookuptimeline.php",
        "stats": "lookupeventstats.php",
    }
    for key, endpoint in endpoints.items():
        try:
            payload = _json_get(session, "thesportsdb", THESPORTSDB_BASE + "/" + endpoint, params={"id": event_id}, ttl=ttl)
            result[key] = payload
        except Exception:
            result[key] = {}
    return result


def thesportsdb_lineups(detail: Dict[str, Any]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {"home": [], "away": []}
    payload = detail.get("lineup") if isinstance(detail, dict) else {}
    rows = payload.get("lineup") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = payload.get("players") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return result
    for item in rows:
        if not isinstance(item, dict):
            continue
        side_raw = _plain(item.get("strHomeAway") or item.get("homeAway") or item.get("strTeam")).lower()
        side = "home" if "home" in side_raw else "away" if "away" in side_raw else ""
        if not side:
            continue
        starter = item.get("strSubstitute")
        if starter and _plain(starter).lower() in {"yes", "true", "1"}:
            continue
        name = _plain(item.get("strPlayer") or item.get("strPlayerName") or item.get("name"))
        if name:
            result[side].append(name)
    for side in result:
        result[side] = result[side][:11] if len(result[side]) >= 11 else []
    return result


def thesportsdb_timeline(detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = detail.get("timeline") if isinstance(detail, dict) else {}
    rows = payload.get("timeline") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    out = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        kind = _plain(item.get("strTimeline") or item.get("strType") or item.get("type")).lower()
        minute_text = _plain(item.get("intTime") or item.get("strTime") or item.get("minute"))
        m = re.search(r"\d+", minute_text)
        out.append({
            "kind": "goal" if "goal" in kind else "card" if "card" in kind else "substitution" if "sub" in kind else kind,
            "player": _plain(item.get("strPlayer") or item.get("strPlayer1")),
            "assists": [_plain(item.get("strAssist"))] if _plain(item.get("strAssist")) else [],
            "minute": int(m.group()) if m else None,
            "minute_total": int(m.group()) if m else None,
            "minute_text": minute_text,
            "penalty": "pen" in kind,
            "own_goal": "own" in kind,
            "team": _plain(item.get("strTeam")),
            "raw": item,
        })
    return out


def sportscore_detail_enrichment(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    root = payload.get("match") if isinstance(payload.get("match"), dict) else payload
    return {
        "lineups": root.get("lineups") if isinstance(root.get("lineups"), (dict, list)) else {},
        "timeline": root.get("timeline") if isinstance(root.get("timeline"), list) else [],
        "stats": root.get("stats") if isinstance(root.get("stats"), (dict, list)) else root.get("statistics") if isinstance(root.get("statistics"), (dict, list)) else {},
        "h2h": root.get("h2h") if isinstance(root.get("h2h"), (dict, list)) else {},
        "commentary": root.get("commentary") if isinstance(root.get("commentary"), list) else [],
        "odds_probe": extract_sportscore_odds(payload),
    }


def extract_sportscore_odds(payload: Any) -> Dict[str, Any]:
    """Inspect only explicit odds/markets keys.

    SportScore's public docs do not currently contractually document an odds
    endpoint/schema, even though match pages display odds. Therefore these
    values are diagnostic-only unless SPORTSCORE_ALLOW_UNDOCUMENTED_ODDS=1.
    """
    found: List[Any] = []
    def walk(value: Any, depth: int = 0) -> None:
        if depth > 5:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in {"odds", "markets", "betting_markets", "live_odds", "prematch_odds"}:
                    found.append(child)
                else:
                    walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:100]:
                walk(child, depth + 1)
    walk(payload)
    return {
        "available": bool(found),
        "contract_verified": False,
        "automation_allowed": os.getenv("SPORTSCORE_ALLOW_UNDOCUMENTED_ODDS", "0") == "1",
        "raw_sections": found[:8],
        "warning": "SportScore public API docs do not currently document odds schema/endpoints.",
    }
