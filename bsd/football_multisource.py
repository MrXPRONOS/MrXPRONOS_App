"""Agrégateur gratuit multi-sources football pour réduire les appels BSD.

Ordre de QUALITÉ des données:
1. ESPN       : 100 — référence live/détails quand couvert.
2. BSD        : 96  — référence interne historique/IDs, utilisée en fallback.
3. SportScore : 92  — bonne couverture live, détails, compos, timeline/stats.
4. OpenLigaDB : 86  — très fiable sur les compétitions couvertes, couverture globale limitée.
5. TheSportsDB: 80  — utile en corroboration; limitations plus fortes sur le gratuit.

Ordre de COLLECTE (coût): ESPN -> SportScore -> OpenLigaDB -> TheSportsDB -> BSD.
On sépare volontairement qualité et ordre d'appel: BSD garde une forte autorité
lorsqu'il est présent, mais n'est appelé que si les sources gratuites sont
insuffisantes pour le besoin courant.
"""
from __future__ import annotations

import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import quote

import requests

from bsd_api import BSDAPIError, BSDClient, BSDPage

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
SPORTSCORE_FIXTURES = "https://sportscore.com/api/v1/fixtures/"
SPORTSCORE_MATCH = "https://sportscore.com/api/v1/match/"
SPORTSCORE_TEAM = "https://sportscore.com/api/v1/team/"
SPORTSCORE_H2H = "https://sportscore.com/api/v1/h2h/"
THESPORTSDB = "https://www.thesportsdb.com/api/v1/json/123"
OPENLIGA = "https://api.openligadb.de"

# Compétitions OpenLigaDB à forte qualité. Les six premiers shortcuts sont
# stables d'une saison à l'autre; les quatre derniers sont spécifiques à 2026.
OPENLIGA_CORE_COMPETITIONS = (
    ("bl1", "1. Bundesliga"),
    ("bl2", "2. Bundesliga"),
    ("bl3", "3. Liga"),
    ("ucl", "UEFA Champions League"),
    ("dfb", "DFB-Pokal"),
    ("ffb1", "Frauen-Bundesliga"),
)
OPENLIGA_2026_COMPETITIONS = (
    ("uel2026", "UEFA Europa League"),
    ("uecl2026", "UEFA Conference League"),
    ("nla", "UEFA Nations League A"),
    ("wm26", "FIFA World Cup 2026"),
)

PROVIDER_QUALITY = {
    "espn": 100,
    "bsd": 96,
    "sportscore": 92,
    "openligadb": 86,
    "thesportsdb": 80,
}
FETCH_PRIORITY = ("espn", "sportscore", "openligadb", "thesportsdb", "bsd")

# SportScore impose une attribution visible sur les pages utilisant ses données.
SPORTSCORE_ATTRIBUTION_URL = "https://sportscore.com/"


@dataclass
class SourceHealth:
    provider: str
    requests: int = 0
    failures: int = 0
    rows: int = 0
    last_error: str = ""


def _plain(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _plain(value)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(fc|cf|sc|afc|club|the|de|da|do|calcio|football|fk|sk)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", _norm(value))).strip("-")


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _score(value: Any) -> int | None:
    if value in (None, "", "-", "None"):
        return None
    try:
        n = int(float(str(value).strip()))
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def _team_name(row: dict, side: str) -> str:
    value = row.get(side + "_team")
    if isinstance(value, dict):
        return _plain(value.get("name") or value.get("displayName"))
    return _plain(value)


def _similarity(a: str, b: str) -> float:
    aa, bb = set(_norm(a).split()), set(_norm(b).split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(len(aa | bb), 1)


def _same_fixture(a: dict, b: dict) -> bool:
    ah, aa = _team_name(a, "home"), _team_name(a, "away")
    bh, ba = _team_name(b, "home"), _team_name(b, "away")
    if min(_similarity(ah, bh), _similarity(aa, ba)) < 0.48:
        return False
    at = _moment(a.get("event_date") or a.get("date"))
    bt = _moment(b.get("event_date") or b.get("date"))
    return not (at and bt) or abs((at - bt).total_seconds()) <= 4 * 3600


def _status(value: Any, *, finished: bool = False) -> str:
    text = _plain(value).lower()
    if finished or any(x in text for x in ("finished", "full time", "ft", "ended")):
        return "finished"
    if any(x in text for x in ("live", "in progress", "1st half", "2nd half", "half time", "halftime")):
        return "live"
    if any(x in text for x in ("cancel", "postpon", "suspend", "abandon")):
        return text or "cancelled"
    return "notstarted"


def _bsd_compatible(
    *,
    provider: str,
    provider_id: Any,
    home: str,
    away: str,
    kickoff: Any,
    home_score: Any = None,
    away_score: Any = None,
    status: str = "",
    league: str = "",
    home_logo: str = "",
    away_logo: str = "",
    raw: Any = None,
    extra: dict | None = None,
) -> dict:
    dt = _moment(kickoff)
    pid = _plain(provider_id) or (_slug(home) + "-" + _slug(away) + "-" + (dt.date().isoformat() if dt else "unknown"))
    normalized_status = _status(status)
    row = {
        "id": provider + ":" + pid,
        "source": provider,
        "provider": provider,
        "source_event_id": pid,
        "event_date": dt.isoformat() if dt else _plain(kickoff),
        "status": normalized_status,
        "state": "post" if normalized_status == "finished" else "in" if normalized_status == "live" else "pre",
        "status_detail": _plain(status) or normalized_status,
        "minute": 0,
        "home_team": {"name": _plain(home), "logo": _plain(home_logo)},
        "away_team": {"name": _plain(away), "logo": _plain(away_logo)},
        "home_score": _score(home_score),
        "away_score": _score(away_score),
        "league_name": _plain(league),
        "provider_sources": [provider],
        "provider_quality": PROVIDER_QUALITY[provider],
        "provider_ids": {provider: pid},
        "raw_data": {"source": provider, "provider_payload": raw},
    }
    if extra:
        row.update(extra)
    row["minute"] = _score(row.get("current_minute") or row.get("minute")) or 0
    return row


def _season_for(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def _openliga_competitions(day: date) -> list[tuple[str, int, str]]:
    """Shortcuts OpenLigaDB à qualité élevée, avec saison appropriée."""
    season = _season_for(day)
    rows = [(shortcut, season, label) for shortcut, label in OPENLIGA_CORE_COMPETITIONS]
    # Les compétitions internationales ci-dessous sont explicitement publiées
    # sous la saison 2026 dans OpenLigaDB, y compris la Coupe du monde.
    if day.year == 2026:
        rows.extend((shortcut, 2026, label) for shortcut, label in OPENLIGA_2026_COMPETITIONS)
    return rows


def map_events_to_reference_ids(
    references: Iterable[dict],
    candidates: Iterable[dict],
    *,
    max_hours: float = 4.0,
) -> tuple[list[dict], list[dict]]:
    """Remappe des résultats gratuits sur des IDs déjà connus (ex: IDs BSD publiés).

    Aucun nouvel ID BSD n'est inventé. On exige les équipes dans le même ordre et
    un horaire proche; les références non confirmées sont renvoyées dans missing.
    """
    pool = [row for row in candidates if isinstance(row, dict)]
    mapped: list[dict] = []
    missing: list[dict] = []
    used: set[int] = set()

    for ref in references:
        if not isinstance(ref, dict):
            continue
        ref_id = ref.get("source_event_id", ref.get("id"))
        rh, ra = _team_name(ref, "home"), _team_name(ref, "away")
        rt = _moment(ref.get("event_date") or ref.get("date"))
        best_index = -1
        best_score = 0.0
        for index, row in enumerate(pool):
            if index in used:
                continue
            home_score = _similarity(rh, _team_name(row, "home"))
            away_score = _similarity(ra, _team_name(row, "away"))
            if min(home_score, away_score) < 0.52:
                continue
            score = (home_score + away_score) / 2
            ct = _moment(row.get("event_date") or row.get("date"))
            if rt and ct:
                hours = abs((rt - ct).total_seconds()) / 3600
                if hours > max_hours:
                    continue
                score += max(0.0, 0.16 - hours * 0.03)
            if score > best_score:
                best_index, best_score = index, score

        if best_index < 0:
            missing.append(ref)
            continue

        used.add(best_index)
        row = dict(pool[best_index])
        original_id = row.get("id")
        row["provider_event_id"] = original_id
        row["id"] = ref_id
        row["source_event_id"] = ref_id
        # IDs d'équipes/ligues déjà connus restent préférables pour les modèles BSD.
        for key in ("home_team_id", "away_team_id", "league_id"):
            if ref.get(key) is not None:
                row[key] = ref.get(key)
        mapped.append(row)

    return mapped, missing


def _merge_stat_blocks(primary: Any, secondary: Any) -> dict:
    out = {
        "home": dict((primary or {}).get("home") or {}),
        "away": dict((primary or {}).get("away") or {}),
    }
    extra = secondary if isinstance(secondary, dict) else {}
    for side in ("home", "away"):
        for key, value in ((extra.get(side) or {}).items() if isinstance(extra.get(side), dict) else []):
            if out[side].get(key) in (None, "") and value not in (None, ""):
                out[side][key] = value
    return out


def _logo_from(row: dict, side: str) -> str:
    direct = _plain(row.get(side + "_logo"))
    if direct:
        return direct
    team = row.get(side + "_team")
    if isinstance(team, dict):
        return _plain(team.get("logo") or team.get("image") or team.get("badge"))
    return ""


class MultiSourceFootballClient:
    """Client compatible avec les besoins éditoriaux de BSDClient.

    Le moteur historique/prédictif BSD garde BSDClient pur afin de ne pas mélanger
    des identifiants fournisseurs dans les jeux d'entraînement.
    """

    def __init__(
        self,
        bsd: BSDClient | None = None,
        *,
        session: requests.Session | None = None,
        max_free_requests: int | None = None,
        timeout: int = 14,
    ):
        self.bsd = bsd
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_free_requests = max_free_requests or int(os.getenv("FOOTBALL_FREE_SOURCE_BUDGET", "45"))
        self.free_requests = 0
        self.requests_made = 0
        self.cache_hits = 0
        self.health = {name: SourceHealth(name) for name in PROVIDER_QUALITY}
        self._cache: dict[str, tuple[float, Any]] = {}

    def _json(self, provider: str, url: str, params: dict | None = None, *, ttl: int = 45) -> Any:
        key = provider + "|" + url + "|" + repr(sorted((params or {}).items()))
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and now - cached[0] <= ttl:
            self.cache_hits += 1
            return cached[1]
        if self.free_requests >= self.max_free_requests:
            return None
        self.free_requests += 1
        self.requests_made += 1
        self.health[provider].requests += 1
        last: Exception | None = None
        for attempt in range(2):
            try:
                response = self.session.get(
                    url, params=params, timeout=(6, self.timeout), allow_redirects=True,
                    headers={
                        "Accept": "application/json,text/plain,*/*",
                        "User-Agent": "MrXPRONOS-MultiSource/1.0",
                    },
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 0:
                        time.sleep(0.35)
                        continue
                response.raise_for_status()
                data = response.json()
                self._cache[key] = (time.monotonic(), data)
                return data
            except (requests.RequestException, ValueError) as exc:
                last = exc
        self.health[provider].failures += 1
        self.health[provider].last_error = type(last).__name__ if last else "unavailable"
        return None

    def _espn_day(self, day: date) -> list[dict]:
        payload = self._json(
            "espn", ESPN_SCOREBOARD,
            {"dates": day.strftime("%Y%m%d"), "limit": "1000"}, ttl=30,
        )
        rows: list[dict] = []
        for event in payload.get("events", []) if isinstance(payload, dict) else []:
            comps = event.get("competitions") or []
            comp = comps[0] if comps and isinstance(comps[0], dict) else {}
            competitors = comp.get("competitors") or []
            home = next((x for x in competitors if isinstance(x, dict) and x.get("homeAway") == "home"), {})
            away = next((x for x in competitors if isinstance(x, dict) and x.get("homeAway") == "away"), {})
            ht = home.get("team") if isinstance(home.get("team"), dict) else {}
            at = away.get("team") if isinstance(away.get("team"), dict) else {}
            if not ht or not at:
                continue
            st = comp.get("status") if isinstance(comp.get("status"), dict) else event.get("status") or {}
            typ = st.get("type") if isinstance(st.get("type"), dict) else {}
            finished = bool(typ.get("completed"))
            row = _bsd_compatible(
                provider="espn", provider_id=event.get("id") or comp.get("id"),
                home=ht.get("displayName") or ht.get("name"),
                away=at.get("displayName") or at.get("name"),
                kickoff=event.get("date") or comp.get("date"),
                home_score=home.get("score"), away_score=away.get("score"),
                status=("finished" if finished else typ.get("state") or typ.get("detail") or ""),
                league=((comp.get("league") or {}).get("name") if isinstance(comp.get("league"), dict) else ""),
                home_logo=ht.get("logo") or "", away_logo=at.get("logo") or "", raw=event,
                extra={
                    "current_minute": _score(st.get("displayClock") or st.get("clock")) or 0,
                    "home_team_id": None, "away_team_id": None,
                },
            )
            rows.append(row)
        self.health["espn"].rows += len(rows)
        return rows

    def _sportscore_day(self, day: date) -> list[dict]:
        payload = self._json(
            "sportscore", SPORTSCORE_FIXTURES,
            {"sport": "football", "date": day.isoformat(), "limit": "200", "src": "mrxpronos"},
            ttl=60,
        )
        candidates = []
        if isinstance(payload, dict):
            for key in ("matches", "fixtures", "results", "data"):
                if isinstance(payload.get(key), list):
                    candidates = payload[key]
                    break
        elif isinstance(payload, list):
            candidates = payload
        rows = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            home_obj = item.get("home_team") if isinstance(item.get("home_team"), dict) else item.get("homeTeam") if isinstance(item.get("homeTeam"), dict) else {}
            away_obj = item.get("away_team") if isinstance(item.get("away_team"), dict) else item.get("awayTeam") if isinstance(item.get("awayTeam"), dict) else {}
            home = item.get("home") or home_obj.get("name") or home_obj.get("display_name")
            away = item.get("away") or away_obj.get("name") or away_obj.get("display_name")
            if not home or not away:
                continue
            league_obj = item.get("competition") if isinstance(item.get("competition"), dict) else item.get("league") if isinstance(item.get("league"), dict) else {}
            status = item.get("status_text") or item.get("status") or ""
            row = _bsd_compatible(
                provider="sportscore",
                provider_id=item.get("id") or item.get("match_id") or item.get("slug"),
                home=home, away=away,
                kickoff=item.get("time") or item.get("start_time") or item.get("date"),
                home_score=item.get("home_score"), away_score=item.get("away_score"),
                status=status, league=league_obj.get("name") or item.get("competition_name") or item.get("league_name"),
                home_logo=item.get("home_logo") or home_obj.get("logo") or "",
                away_logo=item.get("away_logo") or away_obj.get("logo") or "",
                raw=item,
                extra={
                    "sportscore_slug": _plain(item.get("slug")),
                    "current_minute": _score(item.get("minute") or item.get("current_minute")) or 0,
                    "home_team_id": None, "away_team_id": None,
                },
            )
            rows.append(row)
        self.health["sportscore"].rows += len(rows)
        return rows

    def _thesportsdb_day(self, day: date) -> list[dict]:
        payload = self._json(
            "thesportsdb", THESPORTSDB + "/eventsday.php",
            {"d": day.isoformat(), "s": "Soccer"}, ttl=300,
        )
        events = payload.get("events") if isinstance(payload, dict) else None
        rows = []
        for item in events if isinstance(events, list) else []:
            if not isinstance(item, dict) or not item.get("strHomeTeam") or not item.get("strAwayTeam"):
                continue
            timestamp = item.get("strTimestamp") or (
                str(item.get("dateEvent") or "") + "T" + str(item.get("strTime") or "00:00:00") + "Z"
            )
            rows.append(_bsd_compatible(
                provider="thesportsdb", provider_id=item.get("idEvent"),
                home=item.get("strHomeTeam"), away=item.get("strAwayTeam"), kickoff=timestamp,
                home_score=item.get("intHomeScore"), away_score=item.get("intAwayScore"),
                status=item.get("strStatus") or item.get("strProgress") or "",
                league=item.get("strLeague"),
                home_logo=item.get("strHomeTeamBadge") or "", away_logo=item.get("strAwayTeamBadge") or "",
                raw=item, extra={"home_team_id": None, "away_team_id": None},
            ))
        self.health["thesportsdb"].rows += len(rows)
        return rows

    def _openliga_day(self, day: date) -> list[dict]:
        """OpenLigaDB multi-ligues : uniquement les compétitions à qualité élevée."""
        rows: list[dict] = []
        seen: set[str] = set()
        for shortcut, season, league_label in _openliga_competitions(day):
            payload = self._json(
                "openligadb",
                f"{OPENLIGA}/getmatchdata/{quote(shortcut, safe='')}/{season}",
                None,
                ttl=900,
            )
            for item in payload if isinstance(payload, list) else []:
                when = _moment(item.get("matchDateTimeUTC") or item.get("matchDateTime"))
                if not when or when.date() != day:
                    continue
                match_id = str(item.get("matchID") or "")
                identity = shortcut + ":" + match_id
                if identity in seen:
                    continue
                seen.add(identity)
                t1 = item.get("team1") if isinstance(item.get("team1"), dict) else {}
                t2 = item.get("team2") if isinstance(item.get("team2"), dict) else {}
                results = item.get("matchResults") if isinstance(item.get("matchResults"), list) else []
                latest = max(
                    (x for x in results if isinstance(x, dict)),
                    key=lambda x: int(x.get("resultOrderID") or 0),
                    default={},
                )
                rows.append(_bsd_compatible(
                    provider="openligadb",
                    provider_id=item.get("matchID"),
                    home=t1.get("teamName"),
                    away=t2.get("teamName"),
                    kickoff=when,
                    home_score=latest.get("pointsTeam1"),
                    away_score=latest.get("pointsTeam2"),
                    status="finished" if item.get("matchIsFinished") else "notstarted",
                    league=league_label,
                    home_logo=t1.get("teamIconUrl") or "",
                    away_logo=t2.get("teamIconUrl") or "",
                    raw={**item, "_openliga_shortcut": shortcut, "_openliga_season": season},
                    extra={
                        "home_team_id": t1.get("teamId"),
                        "away_team_id": t2.get("teamId"),
                        "openliga_shortcut": shortcut,
                    },
                ))
        self.health["openligadb"].rows += len(rows)
        return rows

    def _merge(self, rows: Iterable[dict]) -> list[dict]:
        groups: list[list[dict]] = []
        for row in rows:
            match = next((g for g in groups if _same_fixture(g[0], row)), None)
            if match is None:
                groups.append([row])
            else:
                match.append(row)

        merged: list[dict] = []
        for group in groups:
            ordered = sorted(group, key=lambda r: PROVIDER_QUALITY.get(str(r.get("source")), 0), reverse=True)
            best = dict(ordered[0])
            bsd = next((r for r in group if r.get("source") == "bsd"), None)
            # Compatibilité interne: conserver les IDs BSD si BSD a dû être interrogé.
            if bsd:
                best["id"] = bsd.get("id")
                best["home_team_id"] = bsd.get("home_team_id") or ((bsd.get("home_team") or {}).get("id") if isinstance(bsd.get("home_team"), dict) else None)
                best["away_team_id"] = bsd.get("away_team_id") or ((bsd.get("away_team") or {}).get("id") if isinstance(bsd.get("away_team"), dict) else None)
                # Logos BSD remplissent les trous sans écraser une meilleure source.
                for side in ("home", "away"):
                    current = best.get(side + "_team")
                    source_team = bsd.get(side + "_team")
                    if isinstance(current, dict) and isinstance(source_team, dict) and not current.get("logo"):
                        current["logo"] = source_team.get("logo")
            for row in ordered[1:]:
                # 0 est un score valide : seules None / chaîne vide sont absentes.
                for key in ("home_score", "away_score", "league_name"):
                    if best.get(key) in (None, "") and row.get(key) not in (None, ""):
                        best[key] = row.get(key)
                if best.get("current_minute") in (None, "", 0) and row.get("current_minute") not in (None, "", 0):
                    best["current_minute"] = row.get("current_minute")
                    best["minute"] = row.get("minute") or row.get("current_minute")

                for side in ("home", "away"):
                    if not _logo_from(best, side):
                        logo = _logo_from(row, side)
                        if logo:
                            best[side + "_logo"] = logo
                            team = best.get(side + "_team")
                            if isinstance(team, dict) and not team.get("logo"):
                                team["logo"] = logo

                best["live_stats"] = _merge_stat_blocks(
                    best.get("live_stats") or (best.get("raw_data") or {}).get("live_stats"),
                    row.get("live_stats") or (row.get("raw_data") or {}).get("live_stats"),
                )
            sources = [str(r.get("source")) for r in ordered]
            best["source"] = "multisource" if len(sources) > 1 else sources[0]
            best["provider_sources"] = sources
            best["provider_quality"] = max(PROVIDER_QUALITY.get(x, 0) for x in sources)
            best["provider_ids"] = {
                str(r.get("source")): str(r.get("source_event_id") or r.get("id") or "")
                for r in ordered
            }
            best["raw_sources"] = {
                str(r.get("source")): (r.get("raw_data") or {}).get("provider_payload")
                for r in ordered
            }
            raw = dict(best.get("raw_data") or {})
            raw["live_stats"] = best.get("live_stats") or {}
            raw["provider_sources"] = sources
            raw["provider_quality"] = best["provider_quality"]
            best["raw_data"] = raw
            merged.append(best)
        return sorted(merged, key=lambda x: str(x.get("event_date") or ""))

    def _bsd_events(self, date_from: date, date_to: date, page_size: int, max_pages: int, ttl: int) -> list[dict]:
        if self.bsd is None:
            return []
        try:
            page = self.bsd.list_events(
                date_from, date_to, page_size=page_size, max_pages=max_pages, ttl=ttl,
            )
        except (BSDAPIError, ValueError, requests.RequestException):
            return []
        rows = []
        for item in page.events:
            row = dict(item)
            row["source"] = "bsd"
            row["provider"] = "bsd"
            row["provider_quality"] = PROVIDER_QUALITY["bsd"]
            row["source_event_id"] = str(item.get("id") or "")
            row["provider_sources"] = ["bsd"]
            row["provider_ids"] = {"bsd": str(item.get("id") or "")}
            rows.append(row)
        self.health["bsd"].requests = self.bsd.requests_made
        self.health["bsd"].rows += len(rows)
        return rows

    def list_events(
        self,
        date_from: date,
        date_to: date,
        *,
        page_size: int = 200,
        max_pages: int = 2,
        ttl: int = 180,
    ) -> BSDPage:
        if date_from > date_to:
            raise ValueError("date_from doit précéder date_to")
        days = (date_to - date_from).days + 1
        if days > 7:
            # Les gros backfills restent sur BSD pur: les sources gratuites ne
            # garantissent pas une couverture historique homogène.
            if self.bsd is None:
                return BSDPage([], 0, 0, True)
            return self.bsd.list_events(date_from, date_to, page_size=page_size, max_pages=max_pages, ttl=ttl)

        rows: list[dict] = []
        for offset in range(days):
            day = date_from + timedelta(days=offset)
            rows.extend(self._espn_day(day))
            rows.extend(self._sportscore_day(day))
            rows.extend(self._openliga_day(day))
            rows.extend(self._thesportsdb_day(day))

        free = self._merge(rows)
        # BSD devient le filet de sécurité, pas le premier appel.
        min_matches = max(1, int(os.getenv("FOOTBALL_FREE_MIN_MATCHES_PER_DAY", "8"))) * days
        use_bsd = os.getenv("FOOTBALL_BSD_FALLBACK", "1") != "0" and len(free) < min_matches
        if use_bsd:
            rows.extend(self._bsd_events(date_from, date_to, page_size, max_pages, ttl))
        merged = self._merge(rows)
        return BSDPage(
            events=merged,
            total_reported=len(merged),
            pages_fetched=1,
            complete=True,
        )

    def list_team_recent_events(
        self,
        *,
        team_id: int | None = None,
        team_name: str = "",
        before: date | None = None,
        limit: int = 6,
        ttl: int = 900,
    ) -> list[dict]:
        name = _plain(team_name)
        rows: list[dict] = []
        if name:
            slug = _slug(name)
            payload = self._json(
                "sportscore", SPORTSCORE_TEAM,
                {"sport": "football", "slug": slug, "limit": str(min(50, max(10, limit * 2))), "src": "mrxpronos"},
                ttl=ttl,
            )
            candidates: list = []
            if isinstance(payload, dict):
                for key in ("matches", "fixtures", "events", "results", "past"):
                    if isinstance(payload.get(key), list):
                        candidates.extend(payload[key])
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                home = item.get("home") or ((item.get("home_team") or {}).get("name") if isinstance(item.get("home_team"), dict) else "")
                away = item.get("away") or ((item.get("away_team") or {}).get("name") if isinstance(item.get("away_team"), dict) else "")
                if not home or not away:
                    continue
                dt = _moment(item.get("time") or item.get("start_time") or item.get("date"))
                if before and dt and dt.date() >= before:
                    continue
                rows.append(_bsd_compatible(
                    provider="sportscore", provider_id=item.get("id") or item.get("slug"),
                    home=home, away=away, kickoff=dt,
                    home_score=item.get("home_score"), away_score=item.get("away_score"),
                    status=item.get("status_text") or item.get("status"), league=item.get("league_name"),
                    raw=item,
                ))
            # OpenLigaDB peut compléter gratuitement les formes pour les équipes couvertes.
            payload = self._json(
                "openligadb",
                f"{OPENLIGA}/getmatchesbyteam/{quote(name, safe='')}/12/0",
                None, ttl=ttl,
            )
            for item in payload if isinstance(payload, list) else []:
                dt = _moment(item.get("matchDateTimeUTC") or item.get("matchDateTime"))
                if before and dt and dt.date() >= before:
                    continue
                t1 = item.get("team1") if isinstance(item.get("team1"), dict) else {}
                t2 = item.get("team2") if isinstance(item.get("team2"), dict) else {}
                results = item.get("matchResults") if isinstance(item.get("matchResults"), list) else []
                latest = max((x for x in results if isinstance(x, dict)), key=lambda x:int(x.get("resultOrderID") or 0), default={})
                rows.append(_bsd_compatible(
                    provider="openligadb", provider_id=item.get("matchID"),
                    home=t1.get("teamName"), away=t2.get("teamName"), kickoff=dt,
                    home_score=latest.get("pointsTeam1"), away_score=latest.get("pointsTeam2"),
                    status="finished" if item.get("matchIsFinished") else "notstarted",
                    league="", raw=item,
                ))
        merged = [
            x for x in self._merge(rows)
            if x.get("home_score") is not None and x.get("away_score") is not None
        ]
        if len(merged) >= min(4, limit):
            return merged[-limit:]
        if self.bsd is not None:
            try:
                # N'utiliser un ID que si l'appelant sait qu'il s'agit d'un ID BSD.
                return self.bsd.list_team_recent_events(
                    team_id=team_id if team_id and str(team_id).isdigit() else None,
                    team_name=name,
                    before=before, limit=limit, ttl=ttl,
                )
            except (BSDAPIError, ValueError, requests.RequestException):
                pass
        return merged[-limit:]

    @staticmethod
    def _players(value: Any) -> list[str]:
        rows = value if isinstance(value, list) else []
        names: list[str] = []
        for row in rows:
            if isinstance(row, str):
                name = _plain(row)
            elif isinstance(row, dict):
                athlete = row.get("athlete") if isinstance(row.get("athlete"), dict) else row
                name = _plain(
                    athlete.get("displayName") or athlete.get("name")
                    or athlete.get("strPlayer") or athlete.get("player_name")
                    or athlete.get("player")
                )
            else:
                name = ""
            if name and name not in names:
                names.append(name)
        return names[:18]

    @staticmethod
    def _minute_text(value: Any) -> str:
        text = _plain(value)
        if not text:
            return ""
        m = re.search(r"(\d+)(?:\D*\+\D*(\d+))?", text)
        if not m:
            return text[:18]
        return m.group(1) + (("+" + m.group(2)) if m.group(2) else "") + "'"

    def _sportscore_detail(self, event: dict) -> dict:
        ids = event.get("provider_ids") if isinstance(event.get("provider_ids"), dict) else {}
        raw_sources = event.get("raw_sources") if isinstance(event.get("raw_sources"), dict) else {}
        raw = raw_sources.get("sportscore") if isinstance(raw_sources.get("sportscore"), dict) else {}
        slug = _plain(
            event.get("sportscore_slug") or raw.get("slug")
            or ids.get("sportscore")
            or (_slug(_team_name(event, "home")) + "-vs-" + _slug(_team_name(event, "away")))
        )
        if not slug:
            return {}
        payload = self._json(
            "sportscore", SPORTSCORE_MATCH,
            {"sport": "football", "slug": slug, "src": "mrxpronos"},
            ttl=30,
        )
        root = payload.get("match") if isinstance(payload, dict) and isinstance(payload.get("match"), dict) else (
            payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        )
        if not isinstance(root, dict):
            return {}

        lineups = {"home": [], "away": []}
        lineup_root = root.get("lineups") or root.get("lineup")
        if isinstance(lineup_root, dict):
            for side in ("home", "away"):
                side_value = lineup_root.get(side)
                if isinstance(side_value, dict):
                    side_value = side_value.get("starters") or side_value.get("players") or side_value.get("lineup")
                lineups[side] = self._players(side_value)

        timeline = root.get("timeline") or root.get("events") or root.get("incidents") or []
        goals, cards, substitutions = [], [], []
        for item in timeline if isinstance(timeline, list) else []:
            if not isinstance(item, dict):
                continue
            label = _plain(item.get("type") or item.get("event") or item.get("name") or item.get("text")).lower()
            minute_text = self._minute_text(
                item.get("minute") or item.get("time") or item.get("clock") or item.get("minute_text")
            )
            minute_match = re.search(r"\d+", minute_text)
            minute = int(minute_match.group()) if minute_match else None
            player_obj = item.get("player") if isinstance(item.get("player"), dict) else {}
            player = _plain(
                player_obj.get("name") or player_obj.get("displayName")
                or item.get("player_name") or item.get("player")
            )
            team = _plain(item.get("team") or item.get("team_name") or item.get("side"))
            if "goal" in label or item.get("scoring") is True:
                assists = self._players(item.get("assists") or ([item.get("assist")] if item.get("assist") else []))
                goals.append({
                    "player": player,
                    "minute": minute,
                    "minute_total": minute,
                    "minute_text": minute_text,
                    "team": team,
                    "assists": assists,
                    "penalty": "pen" in label or bool(item.get("penalty")),
                    "own_goal": "own" in label or bool(item.get("own_goal")),
                })
            elif "yellow" in label or "red" in label or "card" in label:
                cards.append({
                    "player": player, "minute": minute, "minute_text": minute_text,
                    "team": team, "type": "red" if "red" in label else "yellow",
                })
            elif "sub" in label:
                substitutions.append({
                    "players": self._players(item.get("players") or []),
                    "minute": minute, "minute_text": minute_text, "team": team,
                })

        stats_out = {"home": {}, "away": {}}
        stats = root.get("stats") or root.get("statistics")
        aliases = {
            "corners": ("corner",),
            "shots": ("total shots", "shots"),
            "shots_on_target": ("shots on target", "shotsontarget"),
            "possession": ("possession",),
            "fouls": ("fouls",),
            "offsides": ("offsides",),
            "saves": ("saves",),
        }
        if isinstance(stats, dict):
            for side in ("home", "away"):
                block = stats.get(side)
                if isinstance(block, dict):
                    lowered = {_norm(k): v for k, v in block.items()}
                    for target, keys in aliases.items():
                        for key in keys:
                            normalized = _norm(key)
                            match = next((v for k, v in lowered.items() if normalized in k), None)
                            if match is not None:
                                stats_out[side][target] = match
                                break
        elif isinstance(stats, list):
            for item in stats:
                if not isinstance(item, dict):
                    continue
                label = _norm(item.get("name") or item.get("label") or item.get("type"))
                for target, keys in aliases.items():
                    if any(_norm(key) in label for key in keys):
                        stats_out["home"][target] = item.get("home") or item.get("home_value")
                        stats_out["away"][target] = item.get("away") or item.get("away_value")
                        break

        info = root.get("venue") if isinstance(root.get("venue"), dict) else {}
        return {
            "source": "sportscore",
            "lineups": lineups,
            "goals": goals,
            "cards": cards,
            "substitutions": substitutions,
            "timeline": timeline if isinstance(timeline, list) else [],
            "stats": stats_out,
            "info": {
                "venue": _plain(info.get("name") or info.get("fullName") or root.get("venue_name")),
                "attendance": root.get("attendance"),
                "referees": self._players(root.get("officials") or root.get("referees") or []),
            },
            # Diagnostic seulement : le contrat public ne documente aucun endpoint
            # de cotes. Ces données éventuelles ne doivent jamais alimenter un pari.
            "odds": None,
            "odds_api_documented": False,
            "odds_observed_in_payload": isinstance(root.get("odds"), (dict, list)),
        }

    def _thesportsdb_detail(self, event: dict) -> dict:
        ids = event.get("provider_ids") if isinstance(event.get("provider_ids"), dict) else {}
        event_id = re.sub(r"[^0-9]", "", str(ids.get("thesportsdb") or ""))
        if not event_id:
            return {}
        lineups_payload = self._json(
            "thesportsdb", THESPORTSDB + "/lookuplineup.php", {"id": event_id}, ttl=300
        )
        timeline_payload = self._json(
            "thesportsdb", THESPORTSDB + "/lookuptimeline.php", {"id": event_id}, ttl=120
        )
        stats_payload = self._json(
            "thesportsdb", THESPORTSDB + "/lookupeventstats.php", {"id": event_id}, ttl=120
        )
        lineups = {"home": [], "away": []}
        lineup_rows = []
        if isinstance(lineups_payload, dict):
            for key in ("lineup", "lineups", "players"):
                if isinstance(lineups_payload.get(key), list):
                    lineup_rows = lineups_payload[key]
                    break
        for item in lineup_rows:
            if not isinstance(item, dict):
                continue
            side = _plain(item.get("strHomeAway") or item.get("strSide")).lower()
            if side not in lineups:
                team_name = _plain(item.get("strTeam"))
                if _similarity(team_name, _team_name(event, "home")) >= .55:
                    side = "home"
                elif _similarity(team_name, _team_name(event, "away")) >= .55:
                    side = "away"
            if side in lineups:
                name = _plain(item.get("strPlayer") or item.get("strPlayerName"))
                position = _plain(item.get("strPosition"))
                starter = item.get("strSubstitute") in (None, "", "No", "no", "0", 0, False)
                if name and starter and "sub" not in position.lower():
                    lineups[side].append(name)
        for side in lineups:
            lineups[side] = lineups[side][:11]

        goals, cards, substitutions = [], [], []
        timeline = []
        if isinstance(timeline_payload, dict):
            for key in ("timeline", "events", "results"):
                if isinstance(timeline_payload.get(key), list):
                    timeline = timeline_payload[key]
                    break
        for item in timeline:
            if not isinstance(item, dict):
                continue
            label = _plain(item.get("strTimeline") or item.get("strType") or item.get("strEvent")).lower()
            minute_text = self._minute_text(item.get("intTime") or item.get("strTime"))
            minute_match = re.search(r"\d+", minute_text)
            minute = int(minute_match.group()) if minute_match else None
            player = _plain(item.get("strPlayer") or item.get("strPlayerName"))
            if "goal" in label:
                goals.append({
                    "player": player, "minute": minute, "minute_total": minute,
                    "minute_text": minute_text, "assists": [], "penalty": "pen" in label,
                    "own_goal": "own" in label,
                })
            elif "card" in label:
                cards.append({
                    "player": player, "minute": minute, "minute_text": minute_text,
                    "type": "red" if "red" in label else "yellow",
                })
            elif "sub" in label:
                substitutions.append({"players": [player] if player else [], "minute": minute, "minute_text": minute_text})

        stats_out = {"home": {}, "away": {}}
        stat_rows = []
        if isinstance(stats_payload, dict):
            for key in ("eventstats", "stats", "statistics"):
                if isinstance(stats_payload.get(key), list):
                    stat_rows = stats_payload[key]
                    break
        aliases = {
            "corners": ("corners",), "shots": ("shots", "total shots"),
            "shots_on_target": ("shots on target",), "possession": ("possession",),
            "fouls": ("fouls",), "offsides": ("offsides",), "saves": ("saves",),
        }
        for item in stat_rows:
            if not isinstance(item, dict):
                continue
            label = _norm(item.get("strStat") or item.get("strStatName") or item.get("name"))
            for target, keys in aliases.items():
                if any(_norm(key) in label for key in keys):
                    stats_out["home"][target] = item.get("intHome") or item.get("strHome")
                    stats_out["away"][target] = item.get("intAway") or item.get("strAway")
                    break
        return {
            "source": "thesportsdb", "lineups": lineups, "goals": goals,
            "cards": cards, "substitutions": substitutions, "timeline": timeline,
            "stats": stats_out, "info": {}, "odds": None,
        }

    def get_match_detail(self, event: dict) -> dict:
        """Détail gratuit hors ESPN; SportScore d'abord, TheSportsDB en complément."""
        sportscore = self._sportscore_detail(event)
        tsdb = self._thesportsdb_detail(event)
        if not sportscore:
            return tsdb
        if not tsdb:
            return sportscore
        merged = dict(sportscore)
        merged["source"] = "sportscore+thesportsdb"
        for key in ("lineups", "stats"):
            if key == "lineups":
                for side in ("home", "away"):
                    if len((merged.get("lineups") or {}).get(side, [])) < 11:
                        merged.setdefault("lineups", {})[side] = (tsdb.get("lineups") or {}).get(side, [])
            else:
                for side in ("home", "away"):
                    for stat, value in ((tsdb.get("stats") or {}).get(side, {}) or {}).items():
                        merged.setdefault("stats", {}).setdefault(side, {}).setdefault(stat, value)
        for key in ("goals", "cards", "substitutions"):
            if not merged.get(key):
                merged[key] = tsdb.get(key) or []
        return merged

    def get_h2h_for_fixture(self, fixture: dict, *, ttl: int = 86400) -> dict:
        home, away = _team_name(fixture, "home"), _team_name(fixture, "away")
        if home and away:
            payload = self._json(
                "sportscore", SPORTSCORE_H2H,
                {
                    "sport": "football",
                    "team1": _slug(home),
                    "team2": _slug(away),
                    "limit": "20",
                    "src": "mrxpronos",
                },
                ttl=ttl,
            )
            if isinstance(payload, dict):
                summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
                keys = ("total_matches", "home_wins", "away_wins", "draws")
                if all(summary.get(k) is not None for k in keys):
                    return {**summary, "source": "sportscore_h2h"}
        # Si SportScore ne peut pas répondre, BSD reste le dernier recours.
        if self.bsd is not None:
            event_id = fixture.get("id")
            try:
                if event_id is not None and str(event_id).isdigit():
                    return self.bsd.get_h2h(int(event_id), ttl=ttl)
            except (BSDAPIError, ValueError, requests.RequestException):
                pass
        return {"source": "unavailable", "total_matches": 0}

    def get_h2h(self, event_id: int, *, ttl: int = 86400) -> Any:
        if self.bsd is None:
            return None
        return self.bsd.get_h2h(event_id, ttl=ttl)

    @property
    def source_report(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "quality": PROVIDER_QUALITY[name],
                "requests": row.requests,
                "failures": row.failures,
                "rows": row.rows,
                "last_error": row.last_error,
            }
            for name, row in self.health.items()
        }
