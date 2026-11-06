"""Independent public-domain English Premier League results source.

Upstream: https://github.com/openfootball/football.json (CC0 1.0).
No legacy Mr XPRONOS code/data is used. Dates and kickoffs are interpreted in
Europe/London; date-only results deliberately use 00:00 UTC, and validation
always excludes the entire target calendar date from its training set.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from .domain import Match, utc_datetime
from .sources import SourceError

UPSTREAM = "https://raw.githubusercontent.com/openfootball/football.json/master"
SOURCE_NAME = "openfootball/football.json"
COMPETITION = "of:ENG-PL"
MAX_RESPONSE_BYTES = 2_000_000


def _season(value: str) -> str:
    if not re.fullmatch(r"20\d\d-\d\d", value):
        raise SourceError("Saison invalide : format attendu 2024-25.")
    first = int(value[:4]); last = int(value[-2:])
    if last != (first + 1) % 100 or not 2000 <= first <= 2090:
        raise SourceError("Année de saison incohérente.")
    return value


def _team_name_id(name: str) -> str:
    # Stable within a league across successive seasons; do not merge aliases
    # of distinct clubs without an explicitly reviewed mapping.
    text = unicodedata.normalize("NFKD", name.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        raise SourceError("Nom d'équipe vide dans la source.")
    return "of:eng-pl:" + text


def _kickoff(record: dict) -> datetime:
    try:
        day = datetime.strptime(record["date"], "%Y-%m-%d")
        time = record.get("time") or ""
        if time:
            if not re.fullmatch(r"\d{1,2}:\d{2}", time):
                raise ValueError("Heure locale invalide")
            hour,minute = map(int,time.split(":"))
            day=day.replace(hour=hour,minute=minute,tzinfo=ZoneInfo("Europe/London"))
            return day.astimezone(timezone.utc)
        return day.replace(tzinfo=timezone.utc)
    except (KeyError,TypeError,ValueError) as exc:
        raise SourceError("Date/heure de match invalide dans le JSON OpenFootball.") from exc


def parse_openfootball_season(payload: dict, season: str, *, as_of: datetime | None = None) -> list[Match]:
    _season(season)
    cutoff = utc_datetime(as_of or datetime.now(timezone.utc))
    if not isinstance(payload,dict) or not isinstance(payload.get("matches"),list):
        raise SourceError("Fichier OpenFootball sans liste 'matches'.")
    games: list[Match] = []
    keys: set[str] = set()
    for ix,record in enumerate(payload["matches"]):
        if not isinstance(record,dict):
            raise SourceError(f"Rencontre #{ix+1} invalide.")
        home,away=record.get("team1"),record.get("team2")
        if not isinstance(home,str) or not isinstance(away,str) or not home.strip() or not away.strip():
            raise SourceError(f"Noms d'équipes invalides (ligne {ix+1}).")
        hid,aid=_team_name_id(home),_team_name_id(away)
        if hid==aid:
            raise SourceError("Match avec équipes identiques.")
        kick=_kickoff(record)
        raw_score=record.get("score")
        # Upstream encodes most results as {"ft": [home,away]}, but genuine
        # 0-0 draws are sometimes the bare list [0,0] (2025-26, 2026-27).
        # Both representations are full-time results. Missing scores remain
        # non-finished fixtures: do not confuse {} / [] / null with a 0-0.
        if raw_score is None or raw_score == {} or raw_score == []:
            ft=None
        elif isinstance(raw_score,dict):
            ft=raw_score.get("ft")
        elif isinstance(raw_score,list):
            ft=raw_score
        else:
            raise SourceError(f"Structure de score invalide (rencontre #{ix+1}).")
        has_result=(isinstance(ft,list) and len(ft)==2 and all(type(x) is int and x>=0 for x in ft))
        if ft is not None and not has_result:
            raise SourceError(f"Score final mal formé (rencontre #{ix+1}).")
        # Some repositories carry a schedule before the result exists. A final
        # result after our as_of MUST NOT enter a historical calibration.
        if has_result and kick.date() >= cutoff.date():
            continue
        if not has_result and not record.get("time"):
            # A future fixture without reliable kickoff time cannot be selected
            # for safe prematch predictions. Do not fabricate one.
            continue
        status="FINISHED" if has_result else "SCHEDULED"
        fingerprint=f"{season}|{record['date']}|{hid}|{aid}"
        if fingerprint in keys:
            raise SourceError(f"Rencontre dupliquée : {fingerprint}")
        keys.add(fingerprint)
        game_id="of:"+hashlib.sha256(fingerprint.encode()).hexdigest()[:24]
        games.append(Match(id=game_id,competition=COMPETITION,kickoff=kick,
            home_id=hid,away_id=aid,home_name=home.strip(),away_name=away.strip(),
            status=status,home_goals=ft[0] if has_result else None,
            away_goals=ft[1] if has_result else None,
            season=season,source=SOURCE_NAME))
    if not games:
        raise SourceError(f"Aucune rencontre valide dans OpenFootball {season}.")
    return games


def download_openfootball_season(season: str, *, session: requests.Session | None = None,
                                 as_of: datetime | None = None) -> tuple[list[Match],dict]:
    _season(season)
    url=f"{UPSTREAM}/{season}/en.1.json"
    http=session or requests.Session()
    try:
        r=http.get(url,timeout=30,headers={"Accept":"application/json","User-Agent":"DixonColes-XiCalibration/1.1"})
        if r.status_code != 200:
            raise SourceError(f"OpenFootball {season} : HTTP {r.status_code}.")
        if len(r.content)>MAX_RESPONSE_BYTES:
            raise SourceError("Données OpenFootball anormalement volumineuses.")
        data=json.loads(r.content)
    except (requests.RequestException,ValueError,UnicodeError) as exc:
        if isinstance(exc,SourceError):
            raise
        raise SourceError(f"Téléchargement OpenFootball {season} impossible : {exc}") from exc
    rows=parse_openfootball_season(data,season,as_of=as_of)
    return rows,{"season":season,"url":url,"sha256":hashlib.sha256(r.content).hexdigest(),
                 "total_rows":len(rows),"finished":sum(m.status=='FINISHED' for m in rows),
                 "source":SOURCE_NAME,"license":"CC0-1.0"}
