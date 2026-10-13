"""Agrégateur football gratuit-first pour Mr XPRONOS.

Objectifs:
- réduire les appels BSD en utilisant d'abord ESPN, SportScore, TheSportsDB et OpenLigaDB;
- conserver une hiérarchie d'autorité distincte de l'ordre de requête;
- normaliser tous les calendriers au format historique BSD utilisé par le projet;
- garder BSD comme backfill ciblé lorsque les sources gratuites sont absentes/incomplètes.

Aucune cote SportScore n'est inventée: seuls des champs explicites odds/markets/bookmakers
présents dans le JSON public match-detail sont acceptés. Les probabilités AI ne sont jamais
traitées comme des cotes bookmaker.
"""
from __future__ import annotations

import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "bsd") not in sys.path:
    sys.path.insert(0, str(ROOT / "bsd"))

from bsd_api import BSDClient, BSDAPIError, BSDPage  # noqa: E402

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
SPORTSCORE_FIXTURES = "https://sportscore.com/api/v1/fixtures/"
SPORTSCORE_MATCH = "https://sportscore.com/api/widget/match/"
SPORTSCORE_TEAM = "https://sportscore.com/api/widget/team/"
SPORTSCORE_H2H = "https://sportscore.com/api/v1/h2h/"
THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"
OPENLIGADB_BASE = "https://api.openligadb.de"

# Autorité globale: utilisée quand deux sources renseignent le même champ.
# BSD reste très fiable, mais il est demandé après les gratuites afin d'économiser son quota.
PROVIDER_QUALITY = {
    "espn": 98,
    "bsd": 95,
    "sportscore": 91,
    "thesportsdb": 80,
    "openligadb": 76,
}
FETCH_PRIORITY = ("espn", "sportscore", "thesportsdb", "openligadb", "bsd")

CAPABILITY_PRIORITY = {
    "live_score": ("espn", "sportscore", "bsd", "openligadb", "thesportsdb"),
    "timeline": ("espn", "sportscore", "thesportsdb", "bsd", "openligadb"),
    "lineups": ("espn", "sportscore", "thesportsdb", "bsd"),
    "match_stats": ("espn", "sportscore", "thesportsdb", "bsd"),
    "fixtures": ("sportscore", "espn", "openligadb", "thesportsdb", "bsd"),
    "final_result": ("espn", "sportscore", "openligadb", "thesportsdb", "bsd"),
    "standings": ("sportscore", "openligadb", "thesportsdb", "espn", "bsd"),
    "scorers": ("sportscore", "openligadb", "espn", "thesportsdb", "bsd"),
    # SportScore affiche des marchés sur son site mais l'API publique documentée
    # n'a pas d'endpoint odds. On n'utilise que des champs explicites éventuels.
    "bookmaker_odds": ("sportscore_explicit_json", "bsd"),
}

_CACHE: dict[str, tuple[float, Any]] = {}


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    value = unicodedata.normalize("NFKD", _plain(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _tokens(value: Any) -> set[str]:
    return {x for x in _norm(value).split() if len(x) > 1}


def _similarity(a: Any, b: Any) -> float:
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def _number(value: Any) -> int | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        n = int(float(str(value).replace("%", "").strip()))
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _state(status: Any, completed: bool = False) -> str:
    raw = _plain(status).casefold()
    if completed or any(x in raw for x in ("finished", "full time", "full-time", "final", "ft")):
        return "finished"
    if any(x in raw for x in ("live", "in progress", "in_play", "1st half", "2nd half", "half time", "halftime")):
        return "live"
    if any(x in raw for x in ("postpon", "cancel", "abandon", "suspend")):
        return raw or "postponed"
    return "scheduled"


def _request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    ttl: int = 30,
    timeout: tuple[int, int] = (6, 16),
    cache_key: str = "",
) -> Any:
    key = cache_key or (url + "?" + repr(sorted((params or {}).items())))
    cached = _CACHE.get(key)
    now = time.monotonic()
    if cached and now - cached[0] <= ttl:
        return cached[1]
    last: Exception | None = None
    for attempt in range(2):
        try:
            response = session.get(
                url,
                params=params,
                headers={
                    "User-Agent": "MrXPRONOS-ProviderMesh/1.0",
                    "Accept": "application/json,text/plain,*/*",
                },
                timeout=timeout,
                allow_redirects=True,
            )
            if response.status_code == 429 and attempt == 0:
                time.sleep(0.5)
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, (dict, list)):
                raise ValueError("JSON object/list expected")
            _CACHE[key] = (time.monotonic(), payload)
            return payload
        except (requests.RequestException, ValueError) as exc:
            last = exc
    if cached:
        return cached[1]
    if last:
        raise last
    return {}


def _canonical(
    provider: str,
    provider_id: Any,
    home: str,
    away: str,
    kickoff: Any,
    *,
    home_score: Any = None,
    away_score: Any = None,
    status: Any = "",
    league: str = "",
    home_logo: str = "",
    away_logo: str = "",
    minute: Any = 0,
    raw: Any = None,
    provider_meta: dict[str, Any] | None = None,
) -> dict:
    provider_id = _plain(provider_id)
    return {
        "id": f"{provider}:{provider_id}" if provider_id else f"{provider}:{_norm(home)}:{_norm(away)}:{_plain(kickoff)}",
        "event_date": _plain(kickoff),
        "home_team": _plain(home),
        "away_team": _plain(away),
        "home_score": _number(home_score),
        "away_score": _number(away_score),
        "status": _state(status),
        "period": _plain(status),
        "league_name": _plain(league),
        "home_logo": _plain(home_logo),
        "away_logo": _plain(away_logo),
        "current_minute": _number(minute) or 0,
        "source": provider,
        "source_quality": PROVIDER_QUALITY.get(provider, 0),
        "sources": [provider],
        "provider_ids": {provider: provider_id} if provider_id else {},
        "provider_meta": {provider: provider_meta or {}},
        "raw_data": {"source": provider, "payload": raw},
    }


def normalize_espn_event(event: dict) -> dict | None:
    competitions = event.get("competitions") or []
    competition = competitions[0] if competitions and isinstance(competitions[0], dict) else {}
    competitors = competition.get("competitors") or []
    home = next((x for x in competitors if isinstance(x, dict) and x.get("homeAway") == "home"), None)
    away = next((x for x in competitors if isinstance(x, dict) and x.get("homeAway") == "away"), None)
    if not isinstance(home, dict) or not isinstance(away, dict):
        return None
    ht = home.get("team") if isinstance(home.get("team"), dict) else {}
    at = away.get("team") if isinstance(away.get("team"), dict) else {}
    status_obj = competition.get("status") if isinstance(competition.get("status"), dict) else {}
    typ = status_obj.get("type") if isinstance(status_obj.get("type"), dict) else {}
    status = " ".join(filter(None, [_plain(typ.get(k)) for k in ("state", "shortDetail", "detail", "name")]))
    row = _canonical(
        "espn", event.get("id") or competition.get("id"),
        ht.get("displayName") or ht.get("name"), at.get("displayName") or at.get("name"),
        event.get("date") or competition.get("date"),
        home_score=home.get("score"), away_score=away.get("score"),
        status="finished" if typ.get("completed") else status,
        league=(competition.get("league") or {}).get("name") or event.get("league"),
        home_logo=ht.get("logo"), away_logo=at.get("logo"),
        minute=status_obj.get("displayClock") or status_obj.get("clock"),
        raw=event,
        provider_meta={"espn_url": "https://www.espn.com/soccer/match/_/gameId/" + str(event.get("id") or "")},
    )
    return row if row["home_team"] and row["away_team"] else None


def fetch_espn_day(session: requests.Session, day: date) -> list[dict]:
    key = day.strftime("%Y%m%d")
    payload = _request_json(
        session, ESPN_SCOREBOARD,
        params={"dates": key, "limit": "1000"},
        ttl=25 if day == datetime.now(timezone.utc).date() else 900,
        cache_key="mesh:espn:" + key,
    )
    return [
        parsed for item in (payload.get("events") or [])
        if isinstance(item, dict) and (parsed := normalize_espn_event(item))
    ] if isinstance(payload, dict) else []


def _sportscore_match_rows(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    if any(k in payload for k in ("home", "away", "home_team", "away_team")):
        return [payload]
    for key in ("matches", "fixtures", "results", "data", "past", "recent", "upcoming"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            nested = _sportscore_match_rows(value)
            if nested:
                return nested
    for value in payload.values():
        if isinstance(value, dict):
            nested = _sportscore_match_rows(value)
            if nested:
                return nested
    return []


def normalize_sportscore_match(item: dict) -> dict | None:
    home_obj = item.get("home_team") if isinstance(item.get("home_team"), dict) else {}
    away_obj = item.get("away_team") if isinstance(item.get("away_team"), dict) else {}
    home = item.get("home") or home_obj.get("name") or item.get("home_name")
    away = item.get("away") or away_obj.get("name") or item.get("away_name")
    if not home or not away:
        return None
    slug = _plain(item.get("slug") or item.get("match_slug"))
    status = item.get("status_text") or item.get("status")
    meta = {
        "slug": slug,
        "sportscore_url": "https://sportscore.com/football/match/" + slug + "/" if slug else "",
    }
    return _canonical(
        "sportscore", item.get("id") or slug,
        home, away,
        item.get("time") or item.get("start_time") or item.get("kickoff") or item.get("date"),
        home_score=item.get("home_score") if item.get("home_score") is not None else item.get("score_home"),
        away_score=item.get("away_score") if item.get("away_score") is not None else item.get("score_away"),
        status=status,
        league=item.get("competition") or item.get("league") or item.get("competition_name"),
        home_logo=item.get("home_logo") or home_obj.get("logo"),
        away_logo=item.get("away_logo") or away_obj.get("logo"),
        minute=item.get("minute") or item.get("clock"),
        raw=item,
        provider_meta=meta,
    )


def fetch_sportscore_day(session: requests.Session, day: date, status: str = "") -> list[dict]:
    params: dict[str, Any] = {
        "sport": "football",
        "date": day.isoformat(),
        "limit": 200,
        "src": "mrxpronos",
    }
    if status:
        params["status"] = status
    payload = _request_json(
        session, SPORTSCORE_FIXTURES, params=params,
        ttl=55 if day == datetime.now(timezone.utc).date() else 900,
        cache_key=f"mesh:sportscore:{day.isoformat()}:{status}",
    )
    out = []
    for item in _sportscore_match_rows(payload):
        parsed = normalize_sportscore_match(item)
        if parsed:
            out.append(parsed)
    return out


def normalize_tsdb_event(item: dict) -> dict | None:
    home = item.get("strHomeTeam")
    away = item.get("strAwayTeam")
    if not home or not away:
        return None
    kickoff = ""
    stamp = _plain(item.get("strTimestamp"))
    if stamp:
        kickoff = stamp
    elif item.get("dateEvent"):
        kickoff = str(item.get("dateEvent")) + ("T" + str(item.get("strTime")) if item.get("strTime") else "T00:00:00+00:00")
    status = item.get("strStatus") or item.get("strProgress") or ""
    if item.get("intHomeScore") is not None and item.get("intAwayScore") is not None and not status:
        status = "finished" if _plain(item.get("strPostponed")) != "yes" else "postponed"
    return _canonical(
        "thesportsdb", item.get("idEvent"),
        home, away, kickoff,
        home_score=item.get("intHomeScore"), away_score=item.get("intAwayScore"),
        status=status,
        league=item.get("strLeague"),
        home_logo=item.get("strHomeTeamBadge"), away_logo=item.get("strAwayTeamBadge"),
        minute=item.get("strProgress"),
        raw=item,
    )


def fetch_thesportsdb_day(session: requests.Session, day: date) -> list[dict]:
    payload = _request_json(
        session, THESPORTSDB_BASE + "/eventsday.php",
        params={"d": day.isoformat(), "s": "Soccer"},
        ttl=180,
        cache_key="mesh:tsdb:" + day.isoformat(),
    )
    rows = payload.get("events") if isinstance(payload, dict) else []
    out = []
    for item in rows if isinstance(rows, list) else []:
        parsed = normalize_tsdb_event(item) if isinstance(item, dict) else None
        if parsed:
            out.append(parsed)
    return out


def normalize_openligadb_match(item: dict) -> dict | None:
    home_obj = item.get("team1") if isinstance(item.get("team1"), dict) else {}
    away_obj = item.get("team2") if isinstance(item.get("team2"), dict) else {}
    home = home_obj.get("teamName")
    away = away_obj.get("teamName")
    if not home or not away:
        return None
    results = item.get("matchResults") if isinstance(item.get("matchResults"), list) else []
    final = None
    for result in results:
        if not isinstance(result, dict):
            continue
        name = _norm(result.get("resultName"))
        order = _number(result.get("resultOrderID")) or 0
        if "endergebnis" in name or "full" in name or order >= 2:
            final = result
    goals = item.get("goals") if isinstance(item.get("goals"), list) else []
    meta = {
        "league_shortcut": item.get("leagueShortcut"),
        "league_season": item.get("leagueSeason"),
        "goals": goals,
    }
    return _canonical(
        "openligadb", item.get("matchID") or item.get("matchId"),
        home, away, item.get("matchDateTimeUTC") or item.get("matchDateTime"),
        home_score=(final or {}).get("pointsTeam1"),
        away_score=(final or {}).get("pointsTeam2"),
        status="finished" if item.get("matchIsFinished") else "scheduled",
        league=item.get("leagueName"),
        home_logo=home_obj.get("teamIconUrl"), away_logo=away_obj.get("teamIconUrl"),
        raw=item,
        provider_meta=meta,
    )


def fetch_openligadb_for_team(session: requests.Session, team_name: str) -> list[dict]:
    if not _plain(team_name):
        return []
    safe_team = quote(_plain(team_name), safe="")
    payload = _request_json(
        session,
        f"{OPENLIGADB_BASE}/getmatchesbyteam/{safe_team}/1/1",
        ttl=300,
        cache_key="mesh:oldb:" + _norm(team_name),
    )
    rows = payload if isinstance(payload, list) else []
    out = []
    for item in rows:
        parsed = normalize_openligadb_match(item) if isinstance(item, dict) else None
        if parsed:
            out.append(parsed)
    return out


def _event_key(event: dict) -> str:
    when = _moment(event.get("event_date"))
    day = when.date().isoformat() if when else ""
    return day + "|" + _norm(event.get("home_team")) + "|" + _norm(event.get("away_team"))


def match_score(a: dict, b: dict) -> float:
    hs = _similarity(a.get("home_team"), b.get("home_team"))
    aws = _similarity(a.get("away_team"), b.get("away_team"))
    if min(hs, aws) < 0.35:
        return 0.0
    score = (hs + aws) / 2
    at, bt = _moment(a.get("event_date")), _moment(b.get("event_date"))
    if at and bt:
        hours = abs((at - bt).total_seconds()) / 3600
        if hours > 8:
            return 0.0
        score += max(0, 0.20 - hours * 0.025)
    return score


def merge_events(rows: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for incoming in sorted(rows, key=lambda x: -int(x.get("source_quality") or 0)):
        best_i, best_score = -1, 0.0
        for i, existing in enumerate(merged):
            score = match_score(existing, incoming)
            if score > best_score:
                best_i, best_score = i, score
        if best_i < 0 or best_score < 0.72:
            merged.append(dict(incoming))
            continue
        current = merged[best_i]
        incoming_quality = int(incoming.get("source_quality") or 0)
        current_quality = int(current.get("source_quality") or 0)
        preferred, other = (incoming, current) if incoming_quality > current_quality else (current, incoming)
        result = dict(preferred)
        for key in (
            "event_date", "home_team", "away_team", "home_score", "away_score",
            "league_name", "home_logo", "away_logo", "current_minute",
        ):
            if result.get(key) in (None, "", 0) and other.get(key) not in (None, ""):
                result[key] = other.get(key)
        result["sources"] = list(dict.fromkeys((current.get("sources") or []) + (incoming.get("sources") or [])))
        result["provider_ids"] = {**(current.get("provider_ids") or {}), **(incoming.get("provider_ids") or {})}
        result["provider_meta"] = {**(current.get("provider_meta") or {}), **(incoming.get("provider_meta") or {})}
        result["raw_data"] = {
            "source": result.get("source"),
            "sources": result["sources"],
            "provider_ids": result["provider_ids"],
            "provider_meta": result["provider_meta"],
        }
        merged[best_i] = result
    return sorted(merged, key=lambda x: (_plain(x.get("event_date")), _plain(x.get("home_team"))))


def explicit_sportscore_odds(payload: Any) -> list[dict]:
    """Retourne uniquement de vraies cotes explicitement présentes dans le JSON.

    On ignore predictions/probabilities/confidence afin de ne jamais présenter
    une probabilité de modèle comme une cote de bookmaker.
    """
    found: list[dict] = []
    seen: set[str] = set()

    def walk(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            lowered = {str(k).casefold(): k for k in value}
            forbidden = any(x in "/".join(path).casefold() for x in ("prediction", "probability", "confidence", "ai"))
            odds_context = any(
                token in str(k).casefold()
                for k in value
                for token in ("odds", "bookmaker", "market", "price")
            ) or any(token in "/".join(path).casefold() for token in ("odds", "bookmaker", "market"))
            if odds_context and not forbidden:
                market = value.get(lowered.get("market", "")) or value.get(lowered.get("market_name", ""))
                outcome = value.get(lowered.get("outcome", "")) or value.get(lowered.get("selection", ""))
                bookmaker = value.get(lowered.get("bookmaker", "")) or value.get(lowered.get("bookmaker_name", ""))
                raw_odds = None
                for key in ("decimal_odds", "odds_decimal", "odds", "price"):
                    actual = lowered.get(key)
                    if actual:
                        raw_odds = value.get(actual)
                        break
                try:
                    decimal = float(raw_odds)
                except (TypeError, ValueError):
                    decimal = 0.0
                if decimal > 1.0:
                    sig = repr((market, outcome, bookmaker, round(decimal, 4)))
                    if sig not in seen:
                        seen.add(sig)
                        found.append({
                            "market": _plain(market),
                            "outcome": _plain(outcome),
                            "bookmaker": _plain(bookmaker),
                            "odds": decimal,
                            "source": "sportscore_explicit_json",
                        })
            for key, child in value.items():
                walk(child, path + (str(key),))
        elif isinstance(value, list):
            for child in value:
                walk(child, path)

    walk(payload)
    return found


def fetch_sportscore_match_detail(session: requests.Session, slug: str, *, live: bool = False) -> dict:
    if not _plain(slug):
        return {}
    payload = _request_json(
        session, SPORTSCORE_MATCH,
        params={"sport": "football", "slug": slug, "src": "mrxpronos"},
        ttl=20 if live else 120,
        cache_key=f"mesh:sportscore:detail:{slug}:{int(live)}",
    )
    return payload if isinstance(payload, dict) else {}


def _slug(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", _plain(value)).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


def fetch_sportscore_team(session: requests.Session, team_name: str, limit: int = 30) -> list[dict]:
    slug = _slug(team_name)
    if not slug:
        return []
    payload = _request_json(
        session, SPORTSCORE_TEAM,
        params={"sport": "football", "slug": slug, "limit": max(1, min(30, int(limit))), "src": "mrxpronos"},
        ttl=300,
        cache_key=f"mesh:sportscore:team:{slug}:{limit}",
    )
    rows = _sportscore_match_rows(payload)
    if not rows and isinstance(payload, dict):
        for key in ("past", "recent", "upcoming", "matches", "fixtures"):
            value = payload.get(key)
            if isinstance(value, list):
                rows.extend(x for x in value if isinstance(x, dict))
    out = []
    for item in rows:
        parsed = normalize_sportscore_match(item)
        if parsed:
            out.append(parsed)
    return merge_events(out)


def fetch_sportscore_h2h(session: requests.Session, home: str, away: str, limit: int = 20) -> dict:
    h, a = _slug(home), _slug(away)
    if not h or not a:
        return {}
    payload = _request_json(
        session, SPORTSCORE_H2H,
        params={"sport": "football", "team1": h, "team2": a, "limit": max(1, min(50, int(limit))), "src": "mrxpronos"},
        ttl=1800,
        cache_key=f"mesh:sportscore:h2h:{h}:{a}:{limit}",
    )
    return payload if isinstance(payload, dict) else {}


def _finished(row: dict) -> bool:
    return _plain(row.get("status")).casefold() in {"finished", "ft", "full_time"}


def h2h_summary(rows: list[dict], home: str, away: str, limit: int = 10) -> dict:
    recent = []
    hw = aw = dr = hg = ag = 0
    for row in sorted(rows, key=lambda x: _plain(x.get("event_date")), reverse=True):
        if not _finished(row):
            continue
        hs, aws = _number(row.get("home_score")), _number(row.get("away_score"))
        if hs is None or aws is None:
            continue
        same = _similarity(row.get("home_team"), home) >= 0.45 and _similarity(row.get("away_team"), away) >= 0.45
        reversed_order = _similarity(row.get("home_team"), away) >= 0.45 and _similarity(row.get("away_team"), home) >= 0.45
        if not (same or reversed_order):
            continue
        fh, fa = (hs, aws) if same else (aws, hs)
        if fh > fa:
            hw += 1
        elif fh < fa:
            aw += 1
        else:
            dr += 1
        hg += fh
        ag += fa
        recent.append({
            "date": row.get("event_date"),
            "home_score": hs,
            "away_score": aws,
            "fixture_home_goals": fh,
            "fixture_away_goals": fa,
            "source": row.get("source"),
        })
        if len(recent) >= limit:
            break
    total = len(recent)
    return {
        "source": "provider_mesh",
        "total_matches": total,
        "home_wins": hw,
        "away_wins": aw,
        "draws": dr,
        "home_goals": hg,
        "away_goals": ag,
        "avg_total_goals": round((hg + ag) / total, 3) if total else None,
        "recent_matches": recent,
    }


@dataclass
class MeshPage:
    events: list[dict]
    total_reported: int
    pages_fetched: int
    complete: bool
    source_counts: dict[str, int]
    bsd_used: bool
    bsd_requests: int


class FreeFirstFootballClient:
    """Calendrier multi-source gratuit-first, BSD uniquement en backfill."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        bsd_factory: Callable[[], BSDClient] | None = None,
        min_free_matches: int | None = None,
    ):
        self.session = session or requests.Session()
        self.bsd_factory = bsd_factory or (
            lambda: BSDClient(
                max_requests=int(os.getenv("FOOTBALL_BSD_REQUEST_BUDGET", "18")),
                max_retries=1,
            )
        )
        self.min_free_matches = (
            int(os.getenv("FOOTBALL_FREE_MIN_MATCHES", "3"))
            if min_free_matches is None else int(min_free_matches)
        )
        self._bsd: BSDClient | None = None
        self.requests_by_provider = {name: 0 for name in FETCH_PRIORITY}
        self.bsd_requests_saved = 0

    @property
    def bsd(self) -> BSDClient:
        if self._bsd is None:
            self._bsd = self.bsd_factory()
        return self._bsd

    def _free_day(self, day: date) -> tuple[list[dict], dict[str, int]]:
        all_rows: list[dict] = []
        counts = {"espn": 0, "sportscore": 0, "thesportsdb": 0, "openligadb": 0}
        for name, fn in (
            ("espn", fetch_espn_day),
            ("sportscore", fetch_sportscore_day),
            ("thesportsdb", fetch_thesportsdb_day),
        ):
            try:
                rows = fn(self.session, day)
            except (requests.RequestException, ValueError, TypeError) as exc:
                print("PROVIDER_UNAVAILABLE", name, day.isoformat(), type(exc).__name__)
                rows = []
            counts[name] = len(rows)
            self.requests_by_provider[name] += 1
            all_rows.extend(rows)
        return merge_events(all_rows), counts

    def list_events(
        self,
        date_from: date,
        date_to: date,
        *,
        page_size: int = 200,
        max_pages: int = 7,
        ttl: int = 0,
    ) -> MeshPage:
        if date_from > date_to:
            raise ValueError("date_from doit précéder date_to")
        cursor = date_from
        rows: list[dict] = []
        source_counts = {name: 0 for name in FETCH_PRIORITY}
        free_healthy = True
        while cursor <= date_to:
            day_rows, counts = self._free_day(cursor)
            for key, value in counts.items():
                source_counts[key] += value
            if len(day_rows) < self.min_free_matches:
                free_healthy = False
            rows.extend(day_rows)
            cursor += timedelta(days=1)

        merged = merge_events(rows)
        bsd_used = False
        bsd_before = self._bsd.requests_made if self._bsd else 0
        should_backfill = (
            not merged
            or not free_healthy
            or os.getenv("FOOTBALL_ALWAYS_BSD_BACKFILL", "0") == "1"
        )
        if should_backfill:
            try:
                page = self.bsd.list_events(
                    date_from, date_to,
                    page_size=page_size,
                    max_pages=max_pages,
                    ttl=ttl,
                )
                bsd_used = True
                source_counts["bsd"] = len(page.events)
                bsd_rows = []
                for item in page.events:
                    if not isinstance(item, dict):
                        continue
                    row = dict(item)
                    row["source"] = "bsd"
                    row["source_quality"] = PROVIDER_QUALITY["bsd"]
                    row["sources"] = ["bsd"]
                    row["provider_ids"] = {"bsd": _plain(item.get("id"))}
                    row["provider_meta"] = {"bsd": {}}
                    bsd_rows.append(row)
                merged = merge_events(merged + bsd_rows)
            except (BSDAPIError, ValueError) as exc:
                print("BSD_BACKFILL_UNAVAILABLE", type(exc).__name__, str(exc)[:140])
        else:
            self.bsd_requests_saved += 1

        bsd_after = self._bsd.requests_made if self._bsd else bsd_before
        return MeshPage(
            events=merged,
            total_reported=len(merged),
            pages_fetched=1,
            complete=bool(merged),
            source_counts=source_counts,
            bsd_used=bsd_used,
            bsd_requests=max(0, bsd_after - bsd_before),
        )

    def list_team_recent_events(
        self,
        *,
        team_id: int | None = None,
        team_name: str = "",
        before: date | None = None,
        limit: int = 8,
        ttl: int = 900,
    ) -> list[dict]:
        """SportScore team schedule d'abord, BSD seulement si insuffisant."""
        rows: list[dict] = []
        try:
            rows = fetch_sportscore_team(self.session, team_name, max(limit * 2, 12))
            self.requests_by_provider["sportscore"] += 1
        except (requests.RequestException, ValueError, TypeError):
            rows = []
        cutoff = before or datetime.now(timezone.utc).date()
        finished = [
            row for row in rows
            if _finished(row)
            and (_moment(row.get("event_date")) is None or _moment(row.get("event_date")).date() <= cutoff)
        ]
        finished.sort(key=lambda x: _plain(x.get("event_date")), reverse=True)
        if len(finished) >= min(5, limit):
            self.bsd_requests_saved += 1
            return finished[:limit]
        try:
            bsd_rows = self.bsd.list_team_recent_events(
                team_id=team_id,
                team_name=team_name,
                before=before,
                limit=limit,
                ttl=ttl,
            )
            out = []
            for item in bsd_rows:
                row = dict(item)
                row["source"] = "bsd"
                row["source_quality"] = PROVIDER_QUALITY["bsd"]
                row["sources"] = ["bsd"]
                row["provider_ids"] = {"bsd": _plain(item.get("id"))}
                out.append(row)
            return merge_events(finished + out)[:limit]
        except (BSDAPIError, ValueError, TypeError):
            return finished[:limit]

    def get_h2h(self, fixture: dict, *, limit: int = 20) -> dict:
        home = _plain(fixture.get("home_team"))
        away = _plain(fixture.get("away_team"))
        try:
            payload = fetch_sportscore_h2h(self.session, home, away, limit)
            self.requests_by_provider["sportscore"] += 1
            rows = []
            for item in _sportscore_match_rows(payload):
                parsed = normalize_sportscore_match(item)
                if parsed:
                    rows.append(parsed)
            if not rows and isinstance(payload, dict):
                for key in ("meetings", "matches", "results"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        for item in value:
                            parsed = normalize_sportscore_match(item) if isinstance(item, dict) else None
                            if parsed:
                                rows.append(parsed)
            summary = h2h_summary(rows, home, away, limit=10)
            if summary["total_matches"] > 0:
                self.bsd_requests_saved += 1
                summary["provider"] = "sportscore"
                return summary
        except (requests.RequestException, ValueError, TypeError):
            pass
        bsd_id = (fixture.get("provider_ids") or {}).get("bsd") or fixture.get("id")
        if str(bsd_id).isdigit():
            try:
                remote = self.bsd.get_h2h(int(bsd_id), ttl=86400)
                if isinstance(remote, dict):
                    remote = remote.get("head_to_head") if isinstance(remote.get("head_to_head"), dict) else remote
                    return {**remote, "provider": "bsd", "source": "api"}
            except (BSDAPIError, ValueError):
                pass
        return {"source": "unavailable", "provider": "", "total_matches": 0}

    def find_event(
        self,
        home: str,
        away: str,
        kickoff: datetime | None,
        *,
        allow_bsd: bool = True,
    ) -> dict | None:
        day = (kickoff or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
        page = self.list_events(day, day, ttl=60)
        probe = {
            "home_team": home,
            "away_team": away,
            "event_date": kickoff.isoformat() if kickoff else "",
        }
        best, best_score = None, 0.0
        for row in page.events:
            score = match_score(probe, row)
            if score > best_score:
                best, best_score = row, score
        if best_score >= 0.72:
            return best

        # OpenLigaDB est surtout utile en ciblé: recherche équipe, puis adversaire/date.
        try:
            rows = fetch_openligadb_for_team(self.session, home)
            self.requests_by_provider["openligadb"] += 1
            for row in rows:
                score = match_score(probe, row)
                if score > best_score:
                    best, best_score = row, score
        except (requests.RequestException, ValueError):
            pass
        if best_score >= 0.72:
            return best

        # Recherche ciblée TheSportsDB (un événement gratuit suffit).
        try:
            title = re.sub(r"\s+", "_", f"{home}_vs_{away}")
            payload = _request_json(
                self.session,
                THESPORTSDB_BASE + "/searchevents.php",
                params={"e": title, "d": day.isoformat()},
                ttl=300,
                cache_key=f"mesh:tsdb:search:{_norm(home)}:{_norm(away)}:{day}",
            )
            self.requests_by_provider["thesportsdb"] += 1
            rows = (payload.get("event") or payload.get("events") or []) if isinstance(payload, dict) else []
            for item in rows if isinstance(rows, list) else []:
                row = normalize_tsdb_event(item) if isinstance(item, dict) else None
                if row:
                    score = match_score(probe, row)
                    if score > best_score:
                        best, best_score = row, score
        except (requests.RequestException, ValueError, TypeError):
            pass
        return best if best_score >= 0.72 else None
