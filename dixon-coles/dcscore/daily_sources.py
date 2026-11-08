"""Two unmixable football sources: licensed football-data.org API and CC0 OpenFootball.

API token is read from environment only. OpenFootball fixtures are unverified schedules.
Never silently equate team IDs between providers, leagues or competitions.
"""
from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
import os
import re
import time
import unicodedata
from zoneinfo import ZoneInfo

import requests

from .daily_rank import RankedFixture
from .domain import Match, utc_datetime
from .sources import parse_fd_matches

UTC=timezone.utc
API_ROOT='https://api.football-data.org/v4'
OPEN_ROOT='https://raw.githubusercontent.com/openfootball/football.json/master'
OPEN_LEAGUES={
 'en.1':('Premier League','Europe/London'),
 'en.2':('Championship','Europe/London'),
 'de.1':('Bundesliga','Europe/Berlin'),
 'es.1':('La Liga','Europe/Madrid'),
 'fr.1':('Ligue 1','Europe/Paris'),
 'it.1':('Serie A','Europe/Rome'),
 'nl.1':('Eredivisie','Europe/Amsterdam'),
 'pt.1':('Primeira Liga','Europe/Lisbon'),
}

class DailySourceError(ValueError):
    pass


def _clean(value: object) -> str:
    text=str(value or '').strip()
    if not text or len(text)>160 or any(ord(x)<32 for x in text):
        raise DailySourceError('Nom de club invalide ou vide.')
    return text


def _slug(value: str) -> str:
    value=''.join(x for x in unicodedata.normalize('NFKD',value.casefold()) if not unicodedata.combining(x))
    result=re.sub(r'[^a-z0-9]+','-',value).strip('-')
    if not result:raise DailySourceError('Identifiant club vide.')
    return result


def _open_kickoff(item: dict, timezone_name: str) -> datetime | None:
    value=item.get('date')
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        return None
    time_string=item.get('time')
    if not isinstance(time_string,str) or not re.fullmatch(r'\d{1,2}:\d{2}',time_string):
        return None
    try:
        day=datetime.fromisoformat(f'{value}T{time_string}:00').replace(tzinfo=ZoneInfo(timezone_name))
        return day.astimezone(UTC)
    except ValueError:
        return None


def _open_result(item:dict) -> tuple[int,int] | None:
    score=item.get('score')
    if isinstance(score,dict):score=score.get('ft')
    if not isinstance(score,list) or len(score)!=2 or any(type(v) is not int or v<0 for v in score):
        return None
    return (score[0],score[1])


class HttpClient:
    """Response validation, bounded 429 retry, and 10-requests/minute throttle for FD."""
    def __init__(self, *, session=None, sleep=None, monotonic=None, min_api_spacing:float=7.0):
        self.session=session or requests.Session()
        self.sleep=sleep or time.sleep
        self.monotonic=monotonic or time.monotonic
        self.min_api_spacing=min_api_spacing
        self._api_last=None

    def get_json(self, url: str, *, token: str | None=None, params: dict | None=None) -> dict:
        if not url.startswith((API_ROOT+'/',OPEN_ROOT+'/')):
            raise DailySourceError('URL du fournisseur non autorisée.')
        headers={'Accept':'application/json','User-Agent':'DixonColes-Daily-Selector/1.0'}
        if token:headers['X-Auth-Token']=token
        for attempt in range(3):
            if token and self._api_last is not None:
                dt=self.monotonic()-self._api_last
                if dt<self.min_api_spacing:self.sleep(self.min_api_spacing-dt)
            if token:self._api_last=self.monotonic()
            try:
                response=self.session.get(url,headers=headers,params=params,timeout=(10,35))
            except requests.RequestException as exc:
                raise DailySourceError(f'Impossible de contacter le fournisseur : {type(exc).__name__}') from exc
            if response.status_code==429 and attempt<2:
                try:retry=float(response.headers.get('Retry-After',8*(attempt+1)))
                except (ValueError,TypeError):retry=8*(attempt+1)
                self.sleep(max(7,min(retry,60)))
                continue
            if response.status_code in (401,403):
                raise DailySourceError(f'Accès aux données refusé (HTTP {response.status_code}), vérifier la clé/abonnement.')
            if response.status_code!=200:
                raise DailySourceError(f'Fournisseur indisponible : HTTP {response.status_code}.')
            if len(response.content)>2_500_000:
                raise DailySourceError('Réponse anormalement volumineuse.')
            try:
                data=response.json()
                if not isinstance(data,dict):raise ValueError('Expected JSON object')
                return data
            except ValueError as exc:
                raise DailySourceError('Réponse JSON invalide.') from exc
        raise DailySourceError('Limite HTTP 429 persistante : quota épuisé.')


class FootballDataProvider:
    name='football-data.org'
    source_verified=True   # API-reported fixture, not independently certified
    def __init__(self, *, token:str|None=None, http:HttpClient|None=None, seasons_back:int=3):
        self.token=(token if token is not None else os.environ.get('FOOTBALL_DATA_TOKEN','')).strip()
        if not self.token:
            raise DailySourceError('FOOTBALL_DATA_TOKEN manquant : service officiel non disponible.')
        self.http=http or HttpClient()
        self.seasons_back=seasons_back
        self._history={}

    def discover(self, target_date:date, now:datetime) -> tuple[list[RankedFixture],list[str]]:
        begin=target_date-timedelta(days=1);end=target_date+timedelta(days=1)
        payload=self.http.get_json(f'{API_ROOT}/matches',token=self.token,
                                    params={'dateFrom':begin.isoformat(),'dateTo':end.isoformat()})
        if not isinstance(payload.get('matches'),list):raise DailySourceError('Réponse API sans liste de matchs.')
        out=[];errors=[];seen=set()
        for item in payload['matches']:
            try:
                if not isinstance(item,dict) or item.get('status') not in ('SCHEDULED','TIMED'):continue
                kick=utc_datetime(item['utcDate'])
                if kick<=now or kick.date()!=target_date:continue  # Africa/Lome = UTC
                home=item.get('homeTeam') or {};away=item.get('awayTeam') or {}
                comp=item.get('competition') or {}
                if any(x is None for x in (item.get('id'),home.get('id'),away.get('id'))):continue
                home_name=_clean(home.get('name'));away_name=_clean(away.get('name'))
                code=_clean(comp.get('code')).upper()
                if not re.fullmatch(r'[A-Z0-9]{2,8}',code):continue
                fid='fd:'+str(item['id'])
                if fid in seen:continue
                seen.add(fid)
                out.append(RankedFixture(
                    id=fid,competition=code,competition_name=_clean(comp.get('name') or code),
                    kickoff=kick,home_id='fd:'+str(home['id']),away_id='fd:'+str(away['id']),
                    home_name=home_name,away_name=away_name,
                    stage=str(item.get('stage') or 'REGULAR_SEASON'),
                    source=self.name,source_verified=True, neutral_venue=None))
            except (KeyError,ValueError,TypeError) as exc:
                errors.append('Rencontre officielle écartée : données incomplètes.')
        return out,errors

    def history(self, fixture:RankedFixture, now:datetime) -> tuple[list[Match],list[str]]:
        code=fixture.competition
        if code in self._history:return self._history[code]
        season_start=fixture.kickoff.year if fixture.kickoff.month>=7 else fixture.kickoff.year-1
        seasons=range(season_start-self.seasons_back+1,season_start+1)
        rows=[];issues=[];seen=set()
        for season in seasons:
            try:
                data=self.http.get_json(f'{API_ROOT}/competitions/{code}/matches',
                                        token=self.token,params={'season':int(season)})
                if not isinstance(data.get('matches'),list):raise DailySourceError('Saison non lisible.')
                for match in parse_fd_matches(data,code):
                    if match.status=='FINISHED' and match.kickoff<now and match.id not in seen:
                        rows.append(match);seen.add(match.id)
            except DailySourceError as exc:
                issues.append(f'{code}/{season}: {exc}')
        rows.sort(key=lambda m:m.kickoff)
        self._history[code]=(rows,issues)
        return rows,issues


class OpenFootballProvider:
    """CC0 fallback with only matching source history and explicit freshness gate."""
    name='openfootball/football.json'
    source_verified=False
    def __init__(self,*,http:HttpClient|None=None,seasons_back:int=3):
        self.http=http or HttpClient()
        self.seasons_back=seasons_back
        self._season_cache={}
        self._history={}

    def _season(self, season:str,code:str):
        key=(season,code)
        if key not in self._season_cache:
            data=self.http.get_json(f'{OPEN_ROOT}/{season}/{code}.json')
            if not isinstance(data.get('matches'),list):raise DailySourceError(f'OpenFootball {season}/{code}: matchs absents.')
            self._season_cache[key]=data['matches']
        return self._season_cache[key]

    def discover(self,target_date:date,now:datetime)->tuple[list[RankedFixture],list[str]]:
        year=target_date.year if target_date.month>=7 else target_date.year-1
        season=f'{year}-{(year+1)%100:02d}'
        found=[];errors=[]
        for code,(name,tz) in OPEN_LEAGUES.items():
            try:records=self._season(season,code)
            except DailySourceError as exc:
                errors.append(f'{code}: {exc}');continue
            for ix,item in enumerate(records):
                if not isinstance(item,dict) or str(item.get('date'))!=target_date.isoformat():continue
                kick=_open_kickoff(item,tz)
                if kick is None or kick<=now or _open_result(item) is not None:continue
                try:home=_clean(item['team1']);away=_clean(item['team2'])
                except (KeyError,ValueError):continue
                fid='of:'+sha256(f'{season}|{code}|{item["date"]}|{home}|{away}'.encode()).hexdigest()[:24]
                found.append(RankedFixture(
                    id=fid,competition='of:'+code.upper(),competition_name=name,
                    kickoff=kick,home_id=f'of:{code}:{_slug(home)}',away_id=f'of:{code}:{_slug(away)}',
                    home_name=home,away_name=away,stage='REGULAR_SEASON',
                    source=self.name,source_verified=False,neutral_venue=None))
        return found,errors

    def history(self,fixture:RankedFixture,now:datetime)->tuple[list[Match],list[str]]:
        comp=fixture.competition
        if comp in self._history:return self._history[comp]
        code=comp.removeprefix('of:').lower()
        if code not in OPEN_LEAGUES:raise DailySourceError('Compétition OpenFootball non autorisée.')
        timezone_name=OPEN_LEAGUES[code][1]
        year=fixture.kickoff.year if fixture.kickoff.month>=7 else fixture.kickoff.year-1
        seasons=[f'{n}-{(n+1)%100:02d}' for n in range(year-self.seasons_back+1,year+1)]
        matches=[];issues=[];seen=set()
        for season in seasons:
            try:records=self._season(season,code)
            except DailySourceError as exc:
                issues.append(f'{season}/{code}: {exc}');continue
            for item in records:
                if not isinstance(item,dict):continue
                result=_open_result(item)
                if result is None:continue
                kickoff=_open_kickoff(item,timezone_name)
                if kickoff is None:
                    # Bare dates are midnight UTC to prevent accidental use of same-date scores.
                    try:kickoff=datetime.fromisoformat(item['date']+'T00:00:00+00:00')
                    except (KeyError,ValueError,TypeError):continue
                if kickoff>=now:continue
                try:home=_clean(item['team1']);away=_clean(item['team2'])
                except (KeyError,ValueError):continue
                fingerprint=f'{season}|{code}|{item.get("date")}|{home}|{away}'
                if fingerprint in seen:continue
                seen.add(fingerprint)
                matches.append(Match(
                    id='of:'+sha256(fingerprint.encode()).hexdigest()[:24],
                    competition=comp,kickoff=kickoff,
                    home_id=f'of:{code}:{_slug(home)}',away_id=f'of:{code}:{_slug(away)}',
                    home_name=home,away_name=away,status='FINISHED',
                    home_goals=result[0],away_goals=result[1],
                    season=season,source=self.name,result_provenance='community_reported'))
        matches.sort(key=lambda m:m.kickoff)
        self._history[comp]=(matches,issues)
        return matches,issues
