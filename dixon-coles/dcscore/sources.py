"""Independent sources: user-provided CSV and official football-data.org v4 API."""
from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from datetime import datetime, timezone
from typing import Any

import requests

from .domain import Match, utc_datetime


class SourceError(ValueError):
    pass


def _value(row: dict, *names: str) -> str:
    lowered={str(k).lower().strip():v for k,v in row.items() if k is not None}
    for name in names:
        val=lowered.get(name.lower())
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return ""


def _csv_date(raw: str) -> datetime:
    if not raw:
        raise SourceError("Date absente du fichier CSV.")
    # A date alone is midnight UTC: it deliberately prevents intraday leakage
    # during walk-forward testing when exact kickoff times are unknown.
    for fmt in ("%d/%m/%Y","%d/%m/%y","%Y-%m-%d","%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw,fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return utc_datetime(raw)
    except ValueError as exc:
        raise SourceError(f"Date non reconnue : {raw}") from exc


def _slug(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def parse_csv(body: bytes, *, default_competition: str="CUSTOM") -> list[Match]:
    if len(body)>15_000_000:
        raise SourceError("CSV trop volumineux (15 Mo maximum).")
    try:
        raw=body.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceError("Le CSV doit être encodé en UTF-8.") from exc
    try:
        dialect=csv.Sniffer().sniff(raw[:4000], delimiters=",;\t")
    except csv.Error:
        dialect=csv.excel
    reader=csv.DictReader(io.StringIO(raw), dialect=dialect)
    if not reader.fieldnames:
        raise SourceError("En-têtes CSV absents.")
    output=[]
    seen=set()
    for lineno,row in enumerate(reader,2):
        if not any(v and str(v).strip() for v in row.values()):
            continue
        try:
            date=_csv_date(_value(row,"kickoff","utcDate","date","Date"))
            home=_value(row,"home_team","HomeTeam","home","Home")
            away=_value(row,"away_team","AwayTeam","away","Away")
            competition = _value(row,"competition","Div","league") or default_competition
            competition=competition.upper().strip()
            if not re.fullmatch(r"[A-Z0-9_\-]{2,25}", competition):
                raise SourceError("Code de compétition invalide.")
            if not home or not away or home.casefold()==away.casefold():
                raise SourceError("Noms des équipes absents ou identiques.")
            home_goals_s=_value(row,"home_goals","FTHG","home_score")
            away_goals_s=_value(row,"away_goals","FTAG","away_score")
            if bool(home_goals_s)!=bool(away_goals_s):
                raise SourceError("Les deux scores doivent être fournis ensemble.")
            scores=bool(home_goals_s and away_goals_s)
            if scores:
                if not (home_goals_s.isdigit() and away_goals_s.isdigit()):
                    raise SourceError("Les buts doivent être des entiers positifs ou nuls.")
                hg,ag=int(home_goals_s),int(away_goals_s)
                status="FINISHED"
            else:
                hg,ag=None,None
                status="SCHEDULED"
            extid = _value(row,"match_id","id")
            fingerprint=f"{competition}|{date.isoformat()}|{_slug(home)}|{_slug(away)}"
            uid="csv:"+hashlib.sha256((f"{competition}|{extid}" if extid else fingerprint).encode()).hexdigest()[:24]
            if uid in seen:
                raise SourceError("Identifiant de match dupliqué dans le fichier.")
            seen.add(uid)
            output.append(Match(id=uid,competition="csv:"+competition,
                        kickoff=date,home_id=f"csv:{competition}:{_slug(_value(row,'home_id') or home)}",
                        away_id=f"csv:{competition}:{_slug(_value(row,'away_id') or away)}",
                        home_name=home,away_name=away,home_goals=hg,away_goals=ag,
                        status=status,season=_value(row,"season","Season"),source="csv"))
        except (ValueError, TypeError) as exc:
            raise SourceError(f"Ligne {lineno} : {exc}") from exc
    if not output:
        raise SourceError("Aucune rencontre trouvée dans le CSV.")
    return output


def _int_score(val: Any) -> int | None:
    if type(val) is int and val>=0:
        return val
    return None


def parse_fd_matches(payload: dict, code: str) -> list[Match]:
    matches=[]
    for item in payload.get("matches",[]):
        status=str(item.get("status", "SCHEDULED"))
        if status in ("CANCELLED","POSTPONED","SUSPENDED","AWARDED"):
            continue
        home=item.get("homeTeam") or {}
        away=item.get("awayTeam") or {}
        if home.get("id") is None or away.get("id") is None:
            continue
        if not home.get("name") or not away.get("name") or not item.get("utcDate"):
            continue
        ft=(item.get("score") or {}).get("fullTime") or {}
        hg,ag=_int_score(ft.get("home")),_int_score(ft.get("away"))
        if status=="FINISHED" and (hg is None or ag is None):
            # Never promote incomplete scores to real final results.
            continue
        if status!="FINISHED":
            hg,ag=None,None
        if item.get("id") is None:
            continue
        try:
            matches.append(Match(
                id="fd:"+str(item["id"]),competition="fd:"+code.upper(),
                kickoff=utc_datetime(item["utcDate"]),
                home_id="fd:"+str(home["id"]),away_id="fd:"+str(away["id"]),
                home_name=home["name"],away_name=away["name"],
                status=status if status=="FINISHED" else "SCHEDULED",
                home_goals=hg,away_goals=ag,
                season=str((item.get("season") or {}).get("startDate") or "")[:4],
                source="football-data.org"
            ))
        except ValueError:
            continue
    return matches


def api_enabled() -> bool:
    return bool(os.getenv("FOOTBALL_DATA_TOKEN", "").strip())


def download_fd_season(code: str, season: int, *, token: str | None=None,
                       session: requests.Session | None=None) -> list[Match]:
    if not re.fullmatch(r"[A-Z0-9]{2,8}",code.upper()):
        raise SourceError("Code championnat invalide (exemple : PL, FL1, PD, BL1, SA).")
    if not 2000<=season<=2100:
        raise SourceError("Année de saison invalide.")
    credential=(token or os.getenv("FOOTBALL_DATA_TOKEN", "")).strip()
    if not credential:
        raise SourceError("Clé API manquante : définir FOOTBALL_DATA_TOKEN.")
    sess=session or requests.Session()
    endpoint=f"https://api.football-data.org/v4/competitions/{code.upper()}/matches"
    try:
        response=sess.get(endpoint,headers={"X-Auth-Token":credential},
                          params={"season":season},timeout=30)
    except requests.RequestException as exc:
        raise SourceError(f"Erreur de connexion football-data.org : {exc}") from exc
    if response.status_code==429:
        raise SourceError("Limite API atteinte (HTTP 429) : réessayer après le délai indiqué par le fournisseur.")
    if response.status_code in (401,403):
        raise SourceError(f"Accès API refusé (HTTP {response.status_code}) : vérifier clé, abonnement et saison demandée.")
    if response.status_code!=200:
        raise SourceError(f"Erreur API HTTP {response.status_code} : {response.text[:240]}")
    try:
        payload=response.json()
        if not isinstance(payload,dict) or not isinstance(payload.get("matches"),list):
            raise ValueError("Réponse sans liste matches")
    except ValueError as exc:
        raise SourceError("Réponse API au format inattendu.") from exc
    return parse_fd_matches(payload,code)
