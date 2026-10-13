"""Free football providers used to reduce BSD API load.

Priority for conflict resolution (quality/reliability):
1. ESPN      95/95  (handled elsewhere in the project)
2. BSD       92/92
3. SportScore 88/86
4. TheSportsDB 78/82
5. OpenLigaDB 72/78

The call strategy is intentionally different: free providers are queried before
BSD for replaceable secondary work (team recent form, H2H, metadata), while BSD
remains the authoritative fallback for unsupported data such as bookmaker odds.
"""
from __future__ import annotations

import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests

SPORTSCORE_BASE = "https://sportscore.com/api/v1"
THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"
OPENLIGA_BASE = "https://api.openligadb.de"

SOURCE_RANKINGS = {
    "espn": {"quality": 95, "reliability": 95, "rank": 1},
    "bsd": {"quality": 92, "reliability": 92, "rank": 2},
    "sportscore": {"quality": 88, "reliability": 86, "rank": 3},
    "thesportsdb": {"quality": 78, "reliability": 82, "rank": 4},
    "openligadb": {"quality": 72, "reliability": 78, "rank": 5},
}


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _plain(value).casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _slug(value: Any) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", _norm(value))).strip("-")


def _dt(value: Any) -> Optional[datetime]:
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
        n = int(value)
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def _stable_team_id(name: str) -> int:
    # Positive deterministic ID for free-provider-only opponents. Real BSD IDs
    # are always preferred whenever known.
    import hashlib
    raw = hashlib.sha1(_norm(name).encode("utf-8")).hexdigest()[:8]
    return 900_000_000 + (int(raw, 16) % 90_000_000)


def _status(value: Any, *, finished: Any = None) -> str:
    text = _norm(value)
    if finished is True or any(x in text for x in ("finished", "final", "ft", "ended")):
        return "finished"
    if any(x in text for x in ("live", "in progress", "playing", "halftime", "half time")):
        return "live"
    if any(x in text for x in ("cancel", "postpon", "abandon", "suspend")):
        return "cancelled"
    return "notstarted"


def _match_similarity(a: dict, b: dict) -> float:
    ah, aa = _norm(a.get("home_team")), _norm(a.get("away_team"))
    bh, ba = _norm(b.get("home_team")), _norm(b.get("away_team"))
    if not ah or not aa or not bh or not ba:
        return 0.0
    def token_score(x: str, y: str) -> float:
        xs, ys = set(x.split()), set(y.split())
        return len(xs & ys) / max(len(xs | ys), 1)
    team_score = (token_score(ah, bh) + token_score(aa, ba)) / 2
    ad, bd = _dt(a.get("event_date")), _dt(b.get("event_date"))
    if ad and bd:
        hours = abs((ad - bd).total_seconds()) / 3600
        if hours > 6:
            return 0.0
        time_score = max(0.0, 1.0 - hours / 6)
    else:
        time_score = 0.5
    return 0.82 * team_score + 0.18 * time_score


@dataclass
class ProviderDiagnostics:
    calls: int = 0
    errors: int = 0
    cache_hits: int = 0


class FreeFootballHub:
    """Small cached clients for SportScore, TheSportsDB and OpenLigaDB."""

    def __init__(self, *, session: Any = None, timeout: int = 15, enabled: Optional[bool] = None):
        if enabled is None:
            enabled = str(os.getenv("BSD_FREE_SOURCES", "1")).strip().lower() not in {"0", "false", "no"}
        self.enabled = bool(enabled)
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MrXPRONOS-MultiSource/1.0",
        })
        self.cache: Dict[str, tuple[float, Any]] = {}
        self.diag: Dict[str, ProviderDiagnostics] = {
            "sportscore": ProviderDiagnostics(),
            "thesportsdb": ProviderDiagnostics(),
            "openligadb": ProviderDiagnostics(),
        }

    def _get(self, provider: str, url: str, *, params: Optional[dict] = None, ttl: int = 60) -> Any:
        key = provider + "|" + url + "|" + repr(sorted((params or {}).items()))
        now = time.time()
        cached = self.cache.get(key)
        if cached and now - cached[0] <= ttl:
            self.diag[provider].cache_hits += 1
            return cached[1]
        self.diag[provider].calls += 1
        try:
            response = self.session.get(url, params=params, timeout=(6, self.timeout), allow_redirects=True)
            response.raise_for_status()
            payload = response.json()
            self.cache[key] = (now, payload)
            return payload
        except (requests.RequestException, ValueError, TypeError):
            self.diag[provider].errors += 1
            return cached[1] if cached else None

    def sportscore_day(self, day: date, *, status: str = "") -> List[dict]:
        if not self.enabled:
            return []
        params: Dict[str, Any] = {"sport": "football", "date": day.isoformat(), "limit": 200}
        if status in {"live", "finished", "upcoming"}:
            params["status"] = status
        payload = self._get("sportscore", SPORTSCORE_BASE + "/fixtures/", params=params, ttl=25 if status == "live" else 120)
        rows = payload.get("matches") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            rows = payload.get("fixtures") if isinstance(payload, dict) else []
        out = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            home = _plain(row.get("home") or row.get("home_team") or row.get("home_name"))
            away = _plain(row.get("away") or row.get("away_team") or row.get("away_name"))
            when = row.get("time") or row.get("start_time") or row.get("date")
            if not home or not away or not when:
                continue
            out.append({
                "id": "sportscore:" + _plain(row.get("id") or row.get("slug") or f"{_slug(home)}-{_slug(away)}-{day}"),
                "source": "sportscore",
                "source_match_id": _plain(row.get("id") or row.get("slug")),
                "source_slug": _plain(row.get("slug")),
                "home_team": home,
                "away_team": away,
                "home_team_id": _stable_team_id(home),
                "away_team_id": _stable_team_id(away),
                "home_score": _score(row.get("home_score")),
                "away_score": _score(row.get("away_score")),
                "status": _status(row.get("status") or row.get("status_text")),
                "event_date": str(when),
                "league_name": _plain(row.get("competition") or row.get("league") or row.get("competition_name")),
                "home_logo": row.get("home_logo") or "",
                "away_logo": row.get("away_logo") or "",
                "raw_data": row,
            })
        return out

    def thesportsdb_day(self, day: date) -> List[dict]:
        if not self.enabled:
            return []
        payload = self._get(
            "thesportsdb",
            THESPORTSDB_BASE + "/eventsday.php",
            params={"d": day.isoformat(), "s": "Soccer"},
            ttl=300,
        )
        rows = payload.get("events") if isinstance(payload, dict) else []
        out = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            home = _plain(row.get("strHomeTeam"))
            away = _plain(row.get("strAwayTeam"))
            if not home or not away:
                continue
            event_date = _plain(row.get("strTimestamp"))
            if not event_date:
                event_date = day.isoformat() + "T" + (_plain(row.get("strTime")) or "00:00:00") + "+00:00"
            out.append({
                "id": "thesportsdb:" + _plain(row.get("idEvent") or f"{_slug(home)}-{_slug(away)}-{day}"),
                "source": "thesportsdb",
                "source_match_id": _plain(row.get("idEvent")),
                "home_team": home,
                "away_team": away,
                "home_team_id": _stable_team_id(home),
                "away_team_id": _stable_team_id(away),
                "home_score": _score(row.get("intHomeScore")),
                "away_score": _score(row.get("intAwayScore")),
                "status": _status(row.get("strStatus") or row.get("strProgress")),
                "event_date": event_date,
                "league_name": _plain(row.get("strLeague")),
                "home_logo": row.get("strHomeTeamBadge") or "",
                "away_logo": row.get("strAwayTeamBadge") or "",
                "raw_data": row,
            })
        return out

    def openligadb_current(self, *, shortcuts: Optional[Iterable[str]] = None) -> List[dict]:
        if not self.enabled:
            return []
        shortcuts = list(shortcuts or [x.strip() for x in os.getenv("OPENLIGADB_LEAGUES", "bl1,bl2,bl3,cl").split(",") if x.strip()])
        out = []
        for shortcut in shortcuts[:12]:
            payload = self._get("openligadb", OPENLIGA_BASE + "/getmatchdata/" + shortcut, ttl=300)
            if not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, dict):
                    continue
                t1 = row.get("team1") if isinstance(row.get("team1"), dict) else {}
                t2 = row.get("team2") if isinstance(row.get("team2"), dict) else {}
                home, away = _plain(t1.get("teamName")), _plain(t2.get("teamName"))
                when = row.get("matchDateTimeUTC") or row.get("matchDateTime")
                if not home or not away or not when:
                    continue
                final_h = final_a = None
                for result in row.get("matchResults") or []:
                    if not isinstance(result, dict):
                        continue
                    kind = _plain(result.get("resultTypeKind")).casefold()
                    if "after90" in kind or "end" in _plain(result.get("resultName")).casefold():
                        final_h, final_a = _score(result.get("pointsTeam1")), _score(result.get("pointsTeam2"))
                out.append({
                    "id": "openligadb:" + _plain(row.get("matchID")),
                    "source": "openligadb",
                    "source_match_id": _plain(row.get("matchID")),
                    "home_team": home,
                    "away_team": away,
                    "home_team_id": _stable_team_id(home),
                    "away_team_id": _stable_team_id(away),
                    "home_score": final_h,
                    "away_score": final_a,
                    "status": _status("", finished=row.get("matchIsFinished")),
                    "event_date": str(when),
                    "league_name": _plain((row.get("league") or {}).get("leagueName") if isinstance(row.get("league"), dict) else shortcut),
                    "home_logo": t1.get("teamIconUrl") or "",
                    "away_logo": t2.get("teamIconUrl") or "",
                    "goals": row.get("goals") or [],
                    "raw_data": row,
                })
        return out

    def day(self, day: date) -> Dict[str, List[dict]]:
        return {
            "sportscore": self.sportscore_day(day),
            "thesportsdb": self.thesportsdb_day(day),
            "openligadb": [x for x in self.openligadb_current() if (_dt(x.get("event_date")) or datetime.min.replace(tzinfo=timezone.utc)).date() == day],
        }

    def enrich_bsd_events(self, events: List[dict], day: date) -> Dict[str, int]:
        """Fill BSD gaps and attach independent-source agreement without changing BSD IDs."""
        sources = self.day(day)
        matched = 0
        confirmed = 0
        filled = 0
        for event in events:
            votes = []
            for provider, rows in sources.items():
                best = None
                best_score = 0.0
                for row in rows:
                    score = _match_similarity(event, row)
                    if score > best_score:
                        best, best_score = row, score
                if best is None or best_score < 0.68:
                    continue
                matched += 1
                votes.append(provider)
                for field in ("league_name", "home_logo", "away_logo"):
                    if not event.get(field) and best.get(field):
                        event[field] = best[field]
                        filled += 1
                if event.get("home_score") is None and best.get("home_score") is not None:
                    event["home_score"] = best["home_score"]; filled += 1
                if event.get("away_score") is None and best.get("away_score") is not None:
                    event["away_score"] = best["away_score"]; filled += 1
                event.setdefault("provider_matches", {})[provider] = {
                    "id": best.get("source_match_id"),
                    "slug": best.get("source_slug"),
                    "similarity": round(best_score, 3),
                }
            event["provider_sources"] = ["bsd", *votes]
            if len(votes) >= 2:
                event["provider_verified"] = True
                confirmed += 1
        return {
            "free_source_matches": matched,
            "multi_source_confirmed": confirmed,
            "fields_filled": filled,
            "sportscore_calls": self.diag["sportscore"].calls,
            "thesportsdb_calls": self.diag["thesportsdb"].calls,
            "openligadb_calls": self.diag["openligadb"].calls,
        }

    def sportscore_team_search(self, name: str) -> Optional[dict]:
        payload = self._get("sportscore", SPORTSCORE_BASE + "/search/", params={"q": name, "sport": "football", "limit": 8}, ttl=3600)
        candidates = []
        if isinstance(payload, dict):
            for key in ("teams", "results", "data"):
                if isinstance(payload.get(key), list):
                    candidates.extend(payload[key])
        target = _norm(name)
        best = None
        best_score = 0.0
        for row in candidates:
            if not isinstance(row, dict):
                continue
            label = _plain(row.get("name") or row.get("title"))
            if not label:
                continue
            score = len(set(target.split()) & set(_norm(label).split())) / max(len(set(target.split()) | set(_norm(label).split())), 1)
            if score > best_score:
                best, best_score = row, score
        return best if best_score >= 0.5 else None

    def sportscore_h2h(self, home: str, away: str, *, limit: int = 20) -> List[dict]:
        h = self.sportscore_team_search(home)
        a = self.sportscore_team_search(away)
        if not h or not a:
            return []
        hs = _plain(h.get("slug") or h.get("id"))
        ads = _plain(a.get("slug") or a.get("id"))
        if not hs or not ads:
            return []
        payload = self._get("sportscore", SPORTSCORE_BASE + "/h2h/", params={"sport": "football", "team1": hs, "team2": ads, "limit": min(limit, 50)}, ttl=1800)
        rows = []
        if isinstance(payload, dict):
            for key in ("matches", "meetings", "results"):
                if isinstance(payload.get(key), list):
                    rows = payload[key]
                    break
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            rh, ra = _plain(row.get("home") or row.get("home_team")), _plain(row.get("away") or row.get("away_team"))
            if not rh or not ra:
                continue
            out.append({
                "id": "sportscore:" + _plain(row.get("id") or row.get("slug")),
                "source": "sportscore",
                "home_team": rh,
                "away_team": ra,
                "home_team_id": _stable_team_id(rh),
                "away_team_id": _stable_team_id(ra),
                "home_score": _score(row.get("home_score")),
                "away_score": _score(row.get("away_score")),
                "status": _status(row.get("status"), finished=True),
                "event_date": row.get("time") or row.get("date"),
                "league_name": _plain(row.get("competition") or row.get("league")),
            })
        return out

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "ranking": SOURCE_RANKINGS,
            "providers": {name: vars(diag) for name, diag in self.diag.items()},
            "sportscore_odds_api": {
                "supported": False,
                "reason": "SportScore website shows pre-match/live odds, but public REST API documentation currently exposes no odds endpoint.",
            },
        }
