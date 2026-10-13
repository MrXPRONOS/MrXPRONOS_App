"""Fournisseurs football gratuits complémentaires à ESPN/BSD.

Objectif:
- SportScore: couverture courante/live + détails (officiel API publique, attribution requise).
- OpenLigaDB: résultats/buts/classements sur ligues disponibles, sans clé.
- TheSportsDB v1: calendrier/détails/timeline/compositions/stats en complément.

Ces sources ne remplacent jamais silencieusement une donnée de meilleure qualité.
Elles servent d'abord à économiser les appels BSD de détail/H2H et à corroborer
les scores. Les cotes restent BSD: aucun endpoint odds n'est documenté dans
l'API publique SportScore au 13/10/2026.
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
from typing import Any, Iterable

import requests

SPORTSCORE_BASE = "https://sportscore.com"
TSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"
OPENLIGA_BASE = "https://api.openligadb.de"
SPORTSCORE_ATTRIBUTION = '<a href="https://sportscore.com/" rel="dofollow" title="Sports data by SportScore">Powered by SportScore</a>'

# Qualité intrinsèque: utilisée pour arbitrer une contradiction.
PROVIDER_QUALITY = {
    # Internal routing weights, not vendor quality claims.
    "espn": 98,
    "bsd": 96,
    "football-data.org": 94,
    "sportscore": 91,
    "api-football": 90,
    "sportsapipro": 88,
    "openligadb": 84,
    "thesportsdb": 80,
}
# Ordre d'appel: les gratuites passent avant BSD afin d'économiser son quota.
FETCH_PRIORITY = ("espn", "sportscore", "openligadb", "thesportsdb", "bsd")
ODDS_PRIORITY = ("bsd",)  # SportScore affiche des odds sur le site, pas dans son API publique documentée.


def provider_policy() -> dict[str, Any]:
    return {
        "quality": dict(PROVIDER_QUALITY),
        "fetch_priority": list(FETCH_PRIORITY),
        "odds_priority": list(ODDS_PRIORITY),
        "sportscore_odds_api_supported": False,
        "sportscore_attribution_required": True,
    }


def _plain(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _norm(v: Any) -> str:
    text = unicodedata.normalize("NFKD", _plain(v)).encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _slug(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(v)).strip("-")


def _num(v: Any) -> int | float | None:
    if v in (None, "", "-"):
        return None
    try:
        n = float(v)
        return int(n) if n.is_integer() else n
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str | None:
    raw = _plain(value)
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def stable_team_id(name: str) -> int:
    digest = hashlib.sha1(_norm(name).encode("utf-8")).hexdigest()[:12]
    return int(digest, 16) % 2_000_000_000 + 1


def _event_id(provider: str, raw_id: Any, home: str, away: str, when: Any) -> str:
    if raw_id not in (None, ""):
        return f"{provider}:{raw_id}"
    key = f"{provider}|{_norm(home)}|{_norm(away)}|{_plain(when)}"
    return f"{provider}:{hashlib.sha1(key.encode()).hexdigest()[:16]}"


def team_similarity(a: str, b: str) -> float:
    aa, bb = set(_norm(a).split()), set(_norm(b).split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def fixture_similarity(a: dict, b: dict) -> float:
    hs = team_similarity(a.get("home_team", ""), b.get("home_team", ""))
    as_ = team_similarity(a.get("away_team", ""), b.get("away_team", ""))
    if min(hs, as_) < 0.35:
        return 0.0
    score = (hs + as_) / 2
    ta, tb = _iso(a.get("event_date")), _iso(b.get("event_date"))
    if ta and tb:
        da, db = datetime.fromisoformat(ta), datetime.fromisoformat(tb)
        hours = abs((da - db).total_seconds()) / 3600
        if hours > 8:
            return 0.0
        score += max(0.0, 0.15 - hours * 0.02)
    return min(score, 1.0)


def _status(value: Any) -> tuple[str, str]:
    raw = _plain(value).casefold()
    if any(x in raw for x in ("finished", "full time", "ft", "ended")):
        return "post", "finished"
    if any(x in raw for x in ("live", "in progress", "1st", "2nd", "half", "extra")):
        return "in", raw or "live"
    if any(x in raw for x in ("postpon", "cancel", "suspend", "abandon")):
        return "post", raw
    return "pre", raw or "scheduled"


def normalize_sportscore(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    home = _plain(row.get("home") or row.get("home_team") or (row.get("homeTeam") or {}).get("name"))
    away = _plain(row.get("away") or row.get("away_team") or (row.get("awayTeam") or {}).get("name"))
    if not home or not away:
        return None
    when = row.get("time") or row.get("start_time") or row.get("date") or row.get("start")
    state, detail = _status(row.get("status_text") or row.get("status"))
    slug = _plain(row.get("slug"))
    raw_id = row.get("id") or row.get("match_id") or slug
    return {
        "source": "sportscore",
        "source_quality": PROVIDER_QUALITY["sportscore"],
        "id": _event_id("sportscore", raw_id, home, away, when),
        "source_match_id": _plain(raw_id),
        "slug": slug,
        "home_team": home,
        "away_team": away,
        "home_team_id": stable_team_id(home),
        "away_team_id": stable_team_id(away),
        "home_logo": _plain(row.get("home_logo")),
        "away_logo": _plain(row.get("away_logo")),
        "home_score": _num(row.get("home_score")),
        "away_score": _num(row.get("away_score")),
        "state": state,
        "status": "finished" if state == "post" else "live" if state == "in" else "scheduled",
        "status_detail": detail,
        "event_date": _iso(when) or _plain(when),
        "league": _plain(row.get("competition") or row.get("league")),
        "raw": row,
    }


def normalize_tsdb(row: dict) -> dict | None:
    if not isinstance(row, dict) or _plain(row.get("strSport")).casefold() not in ("soccer", "football"):
        return None
    home, away = _plain(row.get("strHomeTeam")), _plain(row.get("strAwayTeam"))
    if not home or not away:
        return None
    when = row.get("strTimestamp")
    if not when and row.get("dateEvent"):
        when = f"{row.get('dateEvent')}T{row.get('strTime') or '00:00:00'}+00:00"
    state, detail = _status(row.get("strStatus") or row.get("strProgress"))
    return {
        "source": "thesportsdb",
        "source_quality": PROVIDER_QUALITY["thesportsdb"],
        "id": _event_id("thesportsdb", row.get("idEvent"), home, away, when),
        "source_match_id": _plain(row.get("idEvent")),
        "home_team": home,
        "away_team": away,
        "home_team_id": _num(row.get("idHomeTeam")) or stable_team_id(home),
        "away_team_id": _num(row.get("idAwayTeam")) or stable_team_id(away),
        "home_logo": _plain(row.get("strHomeTeamBadge")),
        "away_logo": _plain(row.get("strAwayTeamBadge")),
        "home_score": _num(row.get("intHomeScore")),
        "away_score": _num(row.get("intAwayScore")),
        "state": state,
        "status": "finished" if state == "post" else "live" if state == "in" else "scheduled",
        "status_detail": detail,
        "event_date": _iso(when) or _plain(when),
        "league": _plain(row.get("strLeague")),
        "venue": _plain(row.get("strVenue")),
        "raw": row,
    }


def normalize_openliga(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    t1 = row.get("team1") if isinstance(row.get("team1"), dict) else {}
    t2 = row.get("team2") if isinstance(row.get("team2"), dict) else {}
    home, away = _plain(t1.get("teamName")), _plain(t2.get("teamName"))
    if not home or not away:
        return None
    results = row.get("matchResults") if isinstance(row.get("matchResults"), list) else []
    finals = sorted(
        (x for x in results if isinstance(x, dict) and _num(x.get("resultOrderID")) is not None),
        key=lambda x: _num(x.get("resultOrderID")) or 0,
    )
    final = finals[-1] if finals else {}
    finished = bool(row.get("matchIsFinished"))
    return {
        "source": "openligadb",
        "source_quality": PROVIDER_QUALITY["openligadb"],
        "id": _event_id("openligadb", row.get("matchID"), home, away, row.get("matchDateTimeUTC")),
        "source_match_id": _plain(row.get("matchID")),
        "home_team": home,
        "away_team": away,
        "home_team_id": _num(t1.get("teamId")) or stable_team_id(home),
        "away_team_id": _num(t2.get("teamId")) or stable_team_id(away),
        "home_logo": _plain(t1.get("teamIconUrl")),
        "away_logo": _plain(t2.get("teamIconUrl")),
        "home_score": _num(final.get("pointsTeam1")),
        "away_score": _num(final.get("pointsTeam2")),
        "state": "post" if finished else "pre",
        "status": "finished" if finished else "scheduled",
        "status_detail": "finished" if finished else "scheduled",
        "event_date": _iso(row.get("matchDateTimeUTC") or row.get("matchDateTime")) or _plain(row.get("matchDateTimeUTC")),
        "league": _plain((row.get("league") or {}).get("leagueName") if isinstance(row.get("league"), dict) else ""),
        "goals": row.get("goals") if isinstance(row.get("goals"), list) else [],
        "raw": row,
    }


@dataclass
class ProviderResult:
    provider: str
    events: list[dict]
    calls: int = 0
    error: str = ""


class FreeFootballProviders:
    def __init__(self, session: Any | None = None, *, timeout: int = 14, cache_dir: Path | str = "bsd/free_cache"):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.cache_dir = Path(cache_dir)
        self.calls: dict[str, int] = {"sportscore": 0, "thesportsdb": 0, "openligadb": 0}

    def _cache_path(self, provider: str, key: str) -> Path:
        digest = hashlib.sha1(key.encode()).hexdigest()
        return self.cache_dir / provider / f"{digest}.json"

    def _get(self, provider: str, url: str, *, params: dict | None = None, ttl: int = 60) -> Any:
        params = dict(params or {})
        key = url + "?" + json.dumps(params, sort_keys=True)
        p = self._cache_path(provider, key)
        if ttl > 0:
            try:
                saved = json.loads(p.read_text(encoding="utf-8"))
                if time.time() - float(saved["saved_at"]) <= ttl:
                    return saved["payload"]
            except (OSError, ValueError, KeyError, TypeError):
                pass
        self.calls[provider] = self.calls.get(provider, 0) + 1
        headers = {
            "Accept": "application/json",
            "User-Agent": "MrXPRONOS-FreeFootballProviders/1.0",
        }
        if provider == "sportscore":
            params.setdefault("src", "mrxpronos")
        response = self.session.get(url, params=params, headers=headers, timeout=(6, self.timeout), allow_redirects=True)
        if response.status_code == 429:
            raise RuntimeError(f"{provider} rate limited")
        response.raise_for_status()
        payload = response.json()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(json.dumps({"saved_at": time.time(), "payload": payload}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return payload

    @staticmethod
    def _rows(payload: Any, *keys: str) -> list[dict]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
        return []

    def sportscore_day(self, day: date, *, status: str | None = None) -> ProviderResult:
        params = {"sport": "football", "date": day.isoformat(), "limit": 200}
        if status:
            params["status"] = status
        try:
            payload = self._get("sportscore", SPORTSCORE_BASE + "/api/v1/fixtures/", params=params, ttl=50)
            rows = self._rows(payload, "matches", "fixtures", "results", "data")
            events = [e for e in (normalize_sportscore(x) for x in rows) if e]
            return ProviderResult("sportscore", events, self.calls["sportscore"])
        except Exception as exc:
            return ProviderResult("sportscore", [], self.calls["sportscore"], f"{type(exc).__name__}: {exc}")

    def sportscore_detail(self, slug: str) -> dict:
        if not _plain(slug):
            return {}
        try:
            payload = self._get(
                "sportscore", SPORTSCORE_BASE + "/api/v1/match/",
                params={"sport": "football", "slug": slug}, ttl=45,
            )
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def sportscore_team_schedule(self, team_name: str, *, limit: int = 12) -> list[dict]:
        slug = _slug(team_name)
        if not slug:
            return []
        try:
            payload = self._get(
                "sportscore", SPORTSCORE_BASE + "/api/v1/team/",
                params={"sport": "football", "slug": slug, "limit": min(30, max(1, limit))}, ttl=600,
            )
            rows = self._rows(payload, "matches", "fixtures", "events", "results", "data")
            return [e for e in (normalize_sportscore(x) for x in rows) if e]
        except Exception:
            return []

    def sportscore_h2h(self, home: str, away: str, *, limit: int = 20) -> dict:
        if not home or not away:
            return {}
        try:
            payload = self._get(
                "sportscore", SPORTSCORE_BASE + "/api/v1/h2h/",
                params={"sport": "football", "team1": _slug(home), "team2": _slug(away), "limit": min(50, max(1, limit))},
                ttl=21600,
            )
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def sportscore_h2h_events(self, home: str, away: str, *, limit: int = 20) -> list[dict]:
        payload = self.sportscore_h2h(home, away, limit=limit)
        rows = self._rows(payload, "matches", "meetings", "results", "events", "data")
        return [e for e in (normalize_sportscore(x) for x in rows) if e]

    def tsdb_day(self, day: date) -> ProviderResult:
        try:
            payload = self._get(
                "thesportsdb", TSDB_BASE + "/eventsday.php",
                params={"d": day.isoformat(), "s": "Soccer"}, ttl=300,
            )
            rows = self._rows(payload, "events")
            events = [e for e in (normalize_tsdb(x) for x in rows) if e]
            return ProviderResult("thesportsdb", events, self.calls["thesportsdb"])
        except Exception as exc:
            return ProviderResult("thesportsdb", [], self.calls["thesportsdb"], f"{type(exc).__name__}: {exc}")

    def tsdb_search_event(self, home: str, away: str, day: date) -> dict:
        name = re.sub(r"\s+", "_", f"{home}_vs_{away}")
        try:
            payload = self._get(
                "thesportsdb", TSDB_BASE + "/searchevents.php",
                params={"e": name, "d": day.isoformat()}, ttl=900,
            )
            rows = self._rows(payload, "event", "events")
            return rows[0] if rows else {}
        except Exception:
            return {}

    def tsdb_detail_bundle(self, event_id: str) -> dict:
        if not re.fullmatch(r"\d+", _plain(event_id)):
            return {}
        bundle: dict[str, Any] = {"event_id": event_id}
        for key, endpoint, response_keys in (
            ("lineups", "lookuplineup.php", ("lineup", "lineups")),
            ("timeline", "lookuptimeline.php", ("timeline",)),
            ("stats", "lookupeventstats.php", ("eventstats", "stats")),
        ):
            try:
                payload = self._get("thesportsdb", TSDB_BASE + "/" + endpoint, params={"id": event_id}, ttl=180)
                bundle[key] = self._rows(payload, *response_keys)
            except Exception:
                bundle[key] = []
        return bundle

    def openliga_available(self) -> list[dict]:
        try:
            payload = self._get("openligadb", OPENLIGA_BASE + "/getavailableleagues", ttl=21600)
            return self._rows(payload)
        except Exception:
            return []

    def openliga_day(self, day: date, league_hint: str = "") -> ProviderResult:
        """OpenLigaDB n'a pas de calendrier global par date.

        On sélectionne les ligues disponibles dont le nom ressemble au championnat,
        télécharge leur saison (cache 6h), puis filtre localement la date.
        """
        hint = _norm(league_hint)
        if not hint:
            return ProviderResult("openligadb", [], self.calls["openligadb"])
        available = self.openliga_available()
        candidates = []
        for row in available:
            name = _plain(row.get("leagueName"))
            shortcut = _plain(row.get("leagueShortcut"))
            season = _plain(row.get("leagueSeason"))
            score = max(team_similarity(hint, name), team_similarity(hint, shortcut))
            if shortcut and season and score >= 0.35:
                candidates.append((score, shortcut, season))
        candidates.sort(reverse=True)
        events: list[dict] = []
        for _, shortcut, season in candidates[:2]:
            try:
                payload = self._get(
                    "openligadb",
                    f"{OPENLIGA_BASE}/getmatchdata/{shortcut}/{season}",
                    ttl=21600,
                )
                for raw in self._rows(payload):
                    event = normalize_openliga(raw)
                    if not event:
                        continue
                    when = _iso(event.get("event_date"))
                    if when and datetime.fromisoformat(when).date() == day:
                        events.append(event)
            except Exception:
                continue
        return ProviderResult("openligadb", events, self.calls["openligadb"])

    def day(self, day: date, *, league_hints: Iterable[str] = ()) -> list[ProviderResult]:
        results = [self.sportscore_day(day), self.tsdb_day(day)]
        seen_hints = []
        for hint in league_hints:
            n = _norm(hint)
            if n and n not in seen_hints:
                seen_hints.append(n)
        for hint in seen_hints[:3]:
            result = self.openliga_day(day, hint)
            if result.events:
                results.append(result)
        return results

    def best_match(self, base: dict, rows: Iterable[dict], *, threshold: float = 0.60) -> dict | None:
        best, score = None, 0.0
        for row in rows:
            s = fixture_similarity(base, row)
            if s > score:
                best, score = row, s
        return best if score >= threshold else None

    def merge_facts(self, rows: Iterable[dict]) -> dict:
        rows = [x for x in rows if isinstance(x, dict)]
        if not rows:
            return {}
        ranked = sorted(rows, key=lambda x: int(x.get("source_quality") or PROVIDER_QUALITY.get(str(x.get("source")), 0)), reverse=True)
        merged = dict(ranked[0])
        sources = []
        for row in ranked:
            source = str(row.get("source") or "")
            if source and source not in sources:
                sources.append(source)
            for key in ("home_score", "away_score", "state", "status_detail", "event_date", "league", "home_logo", "away_logo"):
                # Un score de 0 est une vraie donnée, jamais une valeur manquante.
                if merged.get(key) in (None, "") and row.get(key) not in (None, ""):
                    merged[key] = row[key]
        merged["provider_sources"] = sources
        merged["provider_quality"] = max(PROVIDER_QUALITY.get(x, 0) for x in sources) if sources else 0
        return merged
