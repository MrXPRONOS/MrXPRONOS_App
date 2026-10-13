"""Fournisseurs football gratuits utilisés pour soulager BSD.

Ordre de qualité général (pas l'ordre de facturation):
- ESPN: 96/100 — très riche en live, lineups, événements et boxscore.
- BSD: 94/100 — canonique pour Mr XPRONOS, excellente couverture + cotes,
  mais quota payant/limité donc appelé en dernier quand une source gratuite suffit.
- SportScore: 88/100 — API publique documentée, large couverture, détails/H2H.
- TheSportsDB: 78/100 — API V1 gratuite officielle, limites fortes par endpoint.
- OpenLigaDB: 74/100 — excellent sur les ligues bien entretenues, communautaire.

SportScore affiche des cotes sur son site, mais son API publique documentée ne
publie pas d'endpoint de cotes. Nous ne consommons donc aucune cote SportScore
non documentée pour les décisions du moteur.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

SPORTSCORE_BASE = "https://sportscore.com"
THESPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"
OPENLIGA_BASE = "https://api.openligadb.de"

PROVIDER_QUALITY = {
    "espn": 96,
    "bsd": 94,
    "sportscore": 88,
    "thesportsdb": 78,
    "openligadb": 74,
}

# Pour économiser BSD, on interroge les sources gratuites dans cet ordre.
FREE_FETCH_ORDER = ("sportscore", "thesportsdb", "openligadb")

OPENLIGA_SHORTCUTS = {
    "bundesliga": "bl1",
    "2 bundesliga": "bl2",
    "2. bundesliga": "bl2",
    "3 liga": "bl3",
    "3. liga": "bl3",
    "champions league": "ucl",
    "uefa champions league": "ucl",
    "premier league": "pl",
    "english premier league": "pl",
    "la liga": "la1",
    "laliga": "la1",
    "laliga ea sports": "la1",
    "dfb pokal": "dfb",
    "world cup": "wm26",
    "fifa world cup": "wm26",
}


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _plain(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"\b(fc|cf|sc|afc|club|football|soccer|the|de|da|do)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(value)).strip("-")


def _moment(value: Any) -> Optional[datetime]:
    raw = _plain(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _int(value: Any) -> Optional[int]:
    if value in (None, "", "-"):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _token_similarity(a: Any, b: Any) -> float:
    aa, bb = set(_norm(a).split()), set(_norm(b).split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(len(aa | bb), 1)


def match_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    score = (
        _token_similarity(a.get("home_team"), b.get("home_team"))
        + _token_similarity(a.get("away_team"), b.get("away_team"))
    ) / 2
    at, bt = _moment(a.get("event_date")), _moment(b.get("event_date"))
    if at and bt:
        hours = abs((at - bt).total_seconds()) / 3600
        if hours > 8:
            return 0.0
        score += max(0.0, 0.18 - hours * 0.025)
    return score


def _season_for(day: date) -> int:
    # OpenLigaDB utilise 2026 pour la saison 2026/27.
    return day.year if day.month >= 7 else day.year - 1


@dataclass
class ProviderSnapshot:
    provider: str
    matches: List[Dict[str, Any]]
    error: str = ""
    requests: int = 0


class FreeProviderHub:
    """Client multi-source sans clé avec cache disque et budgets prudents."""

    def __init__(
        self,
        *,
        cache_dir: Path | str = Path("bsd/cache/free"),
        timeout: int = 16,
        session: Optional[requests.Session] = None,
    ):
        self.cache_dir = Path(cache_dir)
        self.timeout = max(5, min(int(timeout), 30))
        self.session = session or requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MrXPRONOS-FreeFootballProviders/1.0",
        })
        self.requests_made: Dict[str, int] = {name: 0 for name in FREE_FETCH_ORDER}
        self.cache_hits = 0

    def _cache_file(self, provider: str, url: str, params: Dict[str, Any]) -> Path:
        raw = json.dumps([provider, url, params], sort_keys=True, ensure_ascii=True)
        return self.cache_dir / provider / (hashlib.sha256(raw.encode()).hexdigest() + ".json")

    def _request_json(
        self,
        provider: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        ttl: int = 60,
    ) -> Any:
        params = dict(params or {})
        path = self._cache_file(provider, url, params)
        if ttl > 0:
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                if time.time() - float(cached["saved_at"]) <= ttl:
                    self.cache_hits += 1
                    return cached["payload"]
            except (OSError, ValueError, KeyError, TypeError):
                pass

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                self.requests_made[provider] = self.requests_made.get(provider, 0) + 1
                response = self.session.get(
                    url,
                    params=params,
                    timeout=(6, self.timeout),
                    allow_redirects=True,
                )
                if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    time.sleep(0.5)
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, (dict, list)):
                    raise ValueError("JSON object/list expected")
                if ttl > 0:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        json.dumps({"saved_at": time.time(), "payload": payload}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
        raise RuntimeError(f"{provider} unavailable: {type(last_error).__name__ if last_error else 'unknown'}")

    @staticmethod
    def _state(status: Any) -> str:
        text = _plain(status).casefold()
        if any(x in text for x in ("finished", "full time", "ft", "ended", "final")):
            return "post"
        if any(x in text for x in ("live", "in play", "in-play", "1st", "2nd", "half", "progress")):
            return "in"
        if any(x in text for x in ("cancel", "postpon", "abandon", "suspend")):
            return "post"
        return "pre"

    def fetch_sportscore_day(self, day: date, *, status: str = "") -> ProviderSnapshot:
        params: Dict[str, Any] = {
            "sport": "football",
            "date": day.isoformat(),
            "limit": 200,
            "src": "mrxpronos",
        }
        if status in {"live", "finished", "upcoming"}:
            params["status"] = status
        try:
            payload = self._request_json(
                "sportscore",
                SPORTSCORE_BASE + "/api/v1/fixtures/",
                params=params,
                ttl=55 if day == datetime.now(timezone.utc).date() else 900,
            )
        except RuntimeError as exc:
            return ProviderSnapshot("sportscore", [], str(exc), self.requests_made["sportscore"])

        rows = []
        raw_rows = []
        if isinstance(payload, dict):
            for key in ("matches", "fixtures", "results", "data"):
                if isinstance(payload.get(key), list):
                    raw_rows = payload[key]
                    break
        elif isinstance(payload, list):
            raw_rows = payload

        for item in raw_rows:
            if not isinstance(item, dict):
                continue
            home_obj = item.get("home") if isinstance(item.get("home"), dict) else {}
            away_obj = item.get("away") if isinstance(item.get("away"), dict) else {}
            home = _plain(
                home_obj.get("name") or item.get("home") or item.get("home_name")
                or item.get("home_team") or item.get("homeTeam")
            )
            away = _plain(
                away_obj.get("name") or item.get("away") or item.get("away_name")
                or item.get("away_team") or item.get("awayTeam")
            )
            when = _moment(item.get("time") or item.get("date") or item.get("start_time") or item.get("kickoff"))
            if not home or not away or not when:
                continue
            status_text = _plain(item.get("status_text") or item.get("status") or item.get("state"))
            league_obj = item.get("competition") if isinstance(item.get("competition"), dict) else {}
            league = _plain(
                league_obj.get("name") or item.get("competition_name") or item.get("league")
                or item.get("league_name")
            )
            rows.append({
                "source": "sportscore",
                "provider_quality": PROVIDER_QUALITY["sportscore"],
                "id": "sportscore:" + _plain(item.get("id") or item.get("slug") or f"{slug(home)}-{slug(away)}"),
                "source_match_id": _plain(item.get("id") or item.get("slug")),
                "slug": _plain(item.get("slug") or f"{slug(home)}-vs-{slug(away)}"),
                "home_team": home,
                "away_team": away,
                "home_score": _int(item.get("home_score") if item.get("home_score") is not None else home_obj.get("score")),
                "away_score": _int(item.get("away_score") if item.get("away_score") is not None else away_obj.get("score")),
                "home_logo": _plain(item.get("home_logo") or home_obj.get("logo")),
                "away_logo": _plain(item.get("away_logo") or away_obj.get("logo")),
                "state": self._state(status_text),
                "status": _plain(item.get("status")),
                "status_detail": status_text,
                "minute": _int(item.get("minute") or item.get("clock")) or 0,
                "event_date": when.isoformat(),
                "league": league,
                "raw": item,
            })
        return ProviderSnapshot("sportscore", rows, requests=self.requests_made["sportscore"])

    def fetch_sportscore_match(self, match_slug: str) -> Dict[str, Any]:
        match_slug = slug(match_slug)
        if not match_slug:
            return {}
        try:
            payload = self._request_json(
                "sportscore",
                SPORTSCORE_BASE + "/api/v1/match/",
                params={"sport": "football", "slug": match_slug, "src": "mrxpronos"},
                ttl=45,
            )
        except RuntimeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def fetch_sportscore_team(self, team_name: str, *, limit: int = 10) -> List[Dict[str, Any]]:
        team_slug = slug(team_name)
        if not team_slug:
            return []
        try:
            payload = self._request_json(
                "sportscore",
                SPORTSCORE_BASE + "/api/v1/team/",
                params={"sport": "football", "slug": team_slug, "limit": max(1, min(limit, 30)), "src": "mrxpronos"},
                ttl=600,
            )
        except RuntimeError:
            return []
        raw_rows: List[Any] = []
        if isinstance(payload, dict):
            for key in ("matches", "fixtures", "events", "schedule", "data"):
                if isinstance(payload.get(key), list):
                    raw_rows = payload[key]
                    break
        result: List[Dict[str, Any]] = []
        for item in raw_rows:
            if not isinstance(item, dict):
                continue
            parsed = self._normalize_loose_event(item, "sportscore")
            if parsed:
                result.append(parsed)
        return result[:limit]

    def fetch_sportscore_h2h(self, home: str, away: str, *, limit: int = 20) -> Dict[str, Any]:
        if not slug(home) or not slug(away):
            return {}
        try:
            payload = self._request_json(
                "sportscore",
                SPORTSCORE_BASE + "/api/v1/h2h/",
                params={
                    "sport": "football",
                    "team1": slug(home),
                    "team2": slug(away),
                    "limit": max(1, min(limit, 50)),
                    "src": "mrxpronos",
                },
                ttl=3600,
            )
        except RuntimeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if summary:
            total = _int(summary.get("total") or summary.get("total_matches"))
            hw = _int(summary.get("team1_wins") or summary.get("home_wins"))
            aw = _int(summary.get("team2_wins") or summary.get("away_wins"))
            dr = _int(summary.get("draws"))
            if total is not None and hw is not None and aw is not None and dr is not None and hw + aw + dr == total:
                return {
                    "provider": "sportscore",
                    "total_matches": total,
                    "home_wins": hw,
                    "away_wins": aw,
                    "draws": dr,
                    "recent_matches": payload.get("matches") or payload.get("meetings") or [],
                }
        rows = payload.get("matches") or payload.get("meetings") or payload.get("results") or []
        if not isinstance(rows, list):
            return {}
        hw = aw = dr = total = 0
        recent = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ev = self._normalize_loose_event(row, "sportscore")
            if not ev or ev.get("home_score") is None or ev.get("away_score") is None:
                continue
            total += 1
            hs, aws = ev["home_score"], ev["away_score"]
            # Re-oriente par rapport aux équipes demandées.
            home_is_team1 = _token_similarity(ev["home_team"], home) >= _token_similarity(ev["away_team"], home)
            team1_goals, team2_goals = (hs, aws) if home_is_team1 else (aws, hs)
            if team1_goals > team2_goals:
                hw += 1
            elif team1_goals < team2_goals:
                aw += 1
            else:
                dr += 1
            recent.append(ev)
        if not total:
            return {}
        return {
            "provider": "sportscore",
            "total_matches": total,
            "home_wins": hw,
            "away_wins": aw,
            "draws": dr,
            "recent_matches": recent[:limit],
        }

    def fetch_thesportsdb_day(self, day: date) -> ProviderSnapshot:
        try:
            payload = self._request_json(
                "thesportsdb",
                THESPORTSDB_BASE + "/eventsday.php",
                params={"d": day.isoformat(), "s": "Soccer"},
                ttl=300 if day == datetime.now(timezone.utc).date() else 3600,
            )
        except RuntimeError as exc:
            return ProviderSnapshot("thesportsdb", [], str(exc), self.requests_made["thesportsdb"])
        raw_rows = payload.get("events") if isinstance(payload, dict) else None
        rows = []
        for item in raw_rows if isinstance(raw_rows, list) else []:
            if not isinstance(item, dict):
                continue
            when = _moment(item.get("strTimestamp"))
            if not when:
                raw_date = _plain(item.get("dateEvent"))
                raw_time = _plain(item.get("strTime")) or "00:00:00"
                when = _moment(f"{raw_date}T{raw_time}+00:00") if raw_date else None
            if not when:
                continue
            status = _plain(item.get("strStatus") or item.get("strProgress"))
            rows.append({
                "source": "thesportsdb",
                "provider_quality": PROVIDER_QUALITY["thesportsdb"],
                "id": "thesportsdb:" + _plain(item.get("idEvent")),
                "source_match_id": _plain(item.get("idEvent")),
                "home_team": _plain(item.get("strHomeTeam")),
                "away_team": _plain(item.get("strAwayTeam")),
                "home_team_id": _plain(item.get("idHomeTeam")),
                "away_team_id": _plain(item.get("idAwayTeam")),
                "home_score": _int(item.get("intHomeScore")),
                "away_score": _int(item.get("intAwayScore")),
                "home_logo": _plain(item.get("strHomeTeamBadge")),
                "away_logo": _plain(item.get("strAwayTeamBadge")),
                "state": self._state(status),
                "status": status,
                "status_detail": status,
                "minute": _int(item.get("intRound")) or 0,
                "event_date": when.isoformat(),
                "league": _plain(item.get("strLeague")),
                "venue": _plain(item.get("strVenue")),
                "raw": item,
            })
        return ProviderSnapshot("thesportsdb", rows, requests=self.requests_made["thesportsdb"])

    def fetch_thesportsdb_detail(self, event_id: str) -> Dict[str, Any]:
        event_id = re.sub(r"\D+", "", _plain(event_id))
        if not event_id:
            return {}
        result: Dict[str, Any] = {"provider": "thesportsdb", "event_id": event_id}
        endpoints = {
            "event": "lookupevent.php",
            "lineup": "lookuplineup.php",
            "timeline": "lookuptimeline.php",
            "stats": "lookupeventstats.php",
        }
        for key, endpoint in endpoints.items():
            try:
                payload = self._request_json(
                    "thesportsdb",
                    THESPORTSDB_BASE + "/" + endpoint,
                    params={"id": event_id},
                    ttl=90,
                )
            except RuntimeError:
                continue
            result[key] = payload
        return result

    def fetch_openligadb_day(self, day: date, leagues: Iterable[str]) -> ProviderSnapshot:
        shortcuts = []
        for league in leagues:
            norm = _norm(league)
            for key, shortcut in OPENLIGA_SHORTCUTS.items():
                if key in norm or norm in key:
                    shortcuts.append(shortcut)
                    break
        shortcuts = list(dict.fromkeys(shortcuts))
        rows: List[Dict[str, Any]] = []
        errors: List[str] = []
        season = _season_for(day)
        for shortcut in shortcuts[:6]:
            try:
                payload = self._request_json(
                    "openligadb",
                    f"{OPENLIGA_BASE}/getmatchdata/{shortcut}/{season}",
                    ttl=1800,
                )
            except RuntimeError as exc:
                errors.append(str(exc))
                continue
            for item in payload if isinstance(payload, list) else []:
                if not isinstance(item, dict):
                    continue
                when = _moment(item.get("matchDateTimeUTC") or item.get("matchDateTime"))
                if not when or when.date() != day:
                    continue
                t1 = item.get("team1") if isinstance(item.get("team1"), dict) else {}
                t2 = item.get("team2") if isinstance(item.get("team2"), dict) else {}
                latest = None
                for rr in item.get("matchResults") or []:
                    if isinstance(rr, dict) and (
                        latest is None or int(rr.get("resultOrderID") or 0) > int(latest.get("resultOrderID") or 0)
                    ):
                        latest = rr
                rows.append({
                    "source": "openligadb",
                    "provider_quality": PROVIDER_QUALITY["openligadb"],
                    "id": "openligadb:" + _plain(item.get("matchID")),
                    "source_match_id": _plain(item.get("matchID")),
                    "home_team": _plain(t1.get("teamName")),
                    "away_team": _plain(t2.get("teamName")),
                    "home_score": _int((latest or {}).get("pointsTeam1")),
                    "away_score": _int((latest or {}).get("pointsTeam2")),
                    "home_logo": _plain(t1.get("teamIconUrl")),
                    "away_logo": _plain(t2.get("teamIconUrl")),
                    "state": "post" if item.get("matchIsFinished") else "pre",
                    "status": "finished" if item.get("matchIsFinished") else "scheduled",
                    "status_detail": "Finished" if item.get("matchIsFinished") else "Scheduled",
                    "minute": 0,
                    "event_date": when.isoformat(),
                    "league": shortcut,
                    "goals": item.get("goals") if isinstance(item.get("goals"), list) else [],
                    "raw": item,
                })
        return ProviderSnapshot(
            "openligadb",
            rows,
            "; ".join(errors[:3]),
            self.requests_made["openligadb"],
        )

    def collect_day(self, day: date, *, leagues: Iterable[str] = ()) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        rows.extend(self.fetch_sportscore_day(day).matches)
        rows.extend(self.fetch_thesportsdb_day(day).matches)
        rows.extend(self.fetch_openligadb_day(day, leagues).matches)
        return rows

    def best_match(self, base: Dict[str, Any], rows: Iterable[Dict[str, Any]], *, threshold: float = 0.60) -> Optional[Dict[str, Any]]:
        best = None
        best_score = threshold
        for row in rows:
            if not isinstance(row, dict):
                continue
            score = match_similarity(base, row)
            if score > best_score:
                best, best_score = row, score
        return best

    def enrich_bsd_events(self, events: List[Dict[str, Any]], day: date) -> List[Dict[str, Any]]:
        leagues = [_plain(e.get("league_name") or (e.get("league") or {}).get("name") if isinstance(e.get("league"), dict) else e.get("league")) for e in events]
        free_rows = self.collect_day(day, leagues=leagues)
        for event in events:
            matched = self.best_match({
                "home_team": self._team_name(event, "home"),
                "away_team": self._team_name(event, "away"),
                "event_date": event.get("event_date"),
            }, free_rows, threshold=0.68)
            if not matched:
                continue
            meta = event.setdefault("_free_provider_meta", {})
            sources = meta.setdefault("sources", [])
            if matched.get("source") not in sources:
                sources.append(matched.get("source"))
            meta["quality"] = max(int(meta.get("quality") or 0), int(matched.get("provider_quality") or 0))
            meta["matched_id"] = matched.get("source_match_id")
            meta["matched_slug"] = matched.get("slug")
            for key in ("home_logo", "away_logo"):
                if not event.get(key) and matched.get(key):
                    event[key] = matched[key]
            # Ne remplace jamais un score BSD renseigné; complète seulement l'absence.
            for key in ("home_score", "away_score"):
                if event.get(key) is None and matched.get(key) is not None:
                    event[key] = matched[key]
            if not event.get("status") and matched.get("status"):
                event["status"] = matched["status"]
        return events

    @staticmethod
    def _team_name(event: Dict[str, Any], side: str) -> str:
        value = event.get(side + "_team")
        if isinstance(value, dict):
            return _plain(value.get("name") or value.get("display_name") or value.get("teamName"))
        return _plain(event.get(side + "_team_name") or value)

    def _normalize_loose_event(self, item: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
        home_obj = item.get("home") if isinstance(item.get("home"), dict) else {}
        away_obj = item.get("away") if isinstance(item.get("away"), dict) else {}
        home = _plain(home_obj.get("name") or item.get("home") or item.get("home_team") or item.get("home_name"))
        away = _plain(away_obj.get("name") or item.get("away") or item.get("away_team") or item.get("away_name"))
        when = _moment(item.get("time") or item.get("date") or item.get("event_date") or item.get("kickoff"))
        if not home or not away or not when:
            return None
        status = _plain(item.get("status_text") or item.get("status") or item.get("state"))
        return {
            "source": source,
            "home_team": home,
            "away_team": away,
            "home_score": _int(item.get("home_score")),
            "away_score": _int(item.get("away_score")),
            "state": self._state(status),
            "status": status,
            "status_detail": status,
            "event_date": when.isoformat(),
            "league": _plain(item.get("league") or item.get("competition")),
            "raw": item,
        }

    def sportscore_odds_probe(self, detail: Dict[str, Any]) -> Dict[str, Any]:
        """Détecte seulement la présence d'un bloc de cotes dans le JSON documenté.

        Aucune cote n'est injectée dans le moteur tant que SportScore ne documente
        pas officiellement le schéma/API des marchés.
        """
        found: List[Dict[str, Any]] = []

        def walk(value: Any, path: str = "") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{path}.{key}" if path else str(key)
                    if str(key).casefold() in {"odds", "markets", "bookmakers", "betting"}:
                        found.append({"path": child_path, "type": type(child).__name__})
                    if len(found) < 20:
                        walk(child, child_path)
            elif isinstance(value, list) and len(found) < 20:
                for idx, child in enumerate(value[:20]):
                    walk(child, f"{path}[{idx}]")

        walk(detail)
        return {
            "provider": "sportscore",
            "documented_odds_endpoint": False,
            "detected_blocks": found,
            "usable_for_engine": False,
        }
