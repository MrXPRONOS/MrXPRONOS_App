"""ESPN-reported fixtures and completed results for priority football competitions.

Experimental personal/test use only. ESPN is an unaffiliated, non-official
third-party provider and its public endpoint may change; never claim UEFA
validation or betting success. Only use final scores before the prediction time.
No mixing of training data across leagues or across suppliers.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import os
import re
import requests

from .daily_rank import RankedFixture
from .daily_popularity import stage_class
from .daily_sources import DailySourceError
from .domain import Match, utc_datetime

BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer'
# A broad editorial discovery pool; no synthetic fixtures and no implicit
# club-ID mapping across competitions. Each competition is trained separately.
# Unsupported ESPN leagues fail individually and are reported in warnings.
ALLOWED = {
    'uefa.champions': 'Ligue des champions UEFA',
    'uefa.europa': 'Europa League UEFA',
    'uefa.europa.conf': 'Conference League UEFA',
    'eng.1': 'Premier League',
    'esp.1': 'Liga',
    'ger.1': 'Bundesliga',
    'ita.1': 'Serie A',
    'fra.1': 'Ligue 1',
    'eng.fa': 'FA Cup',
    'eng.league_cup': 'Coupe de la Ligue anglaise',
    'uefa.wchampions': 'Ligue des champions féminine',
    'eng.trophy': 'EFL Trophy',
}


def _score(value):
    if isinstance(value, dict):
        value = value.get('value', value.get('displayValue'))
    if type(value) is int and 0 <= value <= 30:
        return value
    if isinstance(value, str) and re.fullmatch(r'\d{1,2}', value):
        n = int(value)
        return n if n <= 30 else None
    return None


def _provider_round(event: dict, competition: dict) -> str:
    """Extract confirmed competition phase without guessing from scores.

    ESPN stage/round/notes schemas vary by league; accept only recognizable
    phase strings on structured source fields. Regular-season is the safe fallback.
    """
    values = []
    for source in (event, competition):
        for key in ("stage", "round", "roundName", "phase"):
            raw = source.get(key)
            if isinstance(raw, dict):
                raw = raw.get("name") or raw.get("displayName") or raw.get("label")
            if isinstance(raw, str):
                values.append(raw)
        for note in source.get("notes") or []:
            if isinstance(note, dict):
                title = note.get("headline") or note.get("text")
                if isinstance(title, str):
                    values.append(title)
    for raw in values:
        t = re.sub(r"\s+", " ", raw.strip()).lower()
        if re.search(r"\bsemi[\s-]?finals?\b", t):
            return "SEMI_FINALS"
        if re.search(r"\bquarter[\s-]?finals?\b", t):
            return "QUARTER_FINALS"
        if re.search(r"\b(?:round of 16|last 16|round of sixteen)\b", t):
            return "LAST_16"
        if re.search(r"\b(?:final|finale)\b", t):
            return "FINAL"
        if re.search(r"\bplay[\s-]?offs?\b", t):
            return "PLAYOFFS"
        value = stage_class(t)
        if value in ("FINAL", "SEMI_FINALS", "QUARTER_FINALS", "LAST_16", "PLAYOFFS"):
            return value
    return "REGULAR_SEASON"


def parse_event(event, league: str, *, now: datetime):
    """Return (Match, RankedFixture) after strict validation, or (None, None)."""
    if not isinstance(event, dict):
        return None, None
    event_id = str(event.get('id') or '')
    if not event_id.isdigit():
        return None, None
    try:
        kickoff = utc_datetime(event['date'])
        comp = event['competitions'][0]
        sides = comp['competitors']
        if not isinstance(sides, list) or len(sides) != 2:
            return None, None
        home = next(x for x in sides if x['homeAway'] == 'home')
        away = next(x for x in sides if x['homeAway'] == 'away')
        home_team = home['team']; away_team = away['team']
        hid = str(home_team['id']); aid = str(away_team['id'])
        if not (hid.isdigit() and aid.isdigit() and hid != aid):
            return None, None
        hn = str(home_team.get('displayName') or '').strip()
        an = str(away_team.get('displayName') or '').strip()
        if not (1 <= len(hn) <= 90 and 1 <= len(an) <= 90):
            return None, None
        completed = event.get('status', {}).get('type', {}).get('completed') is True
        status_detail = str(event.get('status', {}).get('type', {}).get('name') or '').upper()
        if status_detail in {'STATUS_CANCELED', 'STATUS_POSTPONED', 'STATUS_ABANDONED'}:
            return None, None
        hs,as_ = _score(home.get('score')), _score(away.get('score'))
        if completed and (hs is None or as_ is None):
            return None, None
        if not completed and kickoff <= now:
            return None, None
        if completed and kickoff >= now:
            return None, None
        def crest(team):
            u = team.get('logo')
            if not isinstance(u, str) or not u:
                images = team.get('logos') or []
                u = images[0].get('href') if images and isinstance(images[0],dict) else None
            return u
        key = f'ES:{league.upper()}'
        match = (Match(
            id=f'espn:{league}:{event_id}',competition=key,kickoff=kickoff,
            home_id=f'espn:{league}:{hid}',away_id=f'espn:{league}:{aid}',
            home_name=hn,away_name=an,status='FINISHED',home_goals=hs,
            away_goals=as_,source='espn-reported',result_provenance='provider_reported',
            season=str(kickoff.year))) if completed else None
        f = RankedFixture(
            id=f'espn:{league}:{event_id}',competition=key,
            competition_name=ALLOWED[league],kickoff=kickoff,
            home_id=f'espn:{league}:{hid}',away_id=f'espn:{league}:{aid}',
            home_name=hn,away_name=an,stage=_provider_round(event,comp),
            source='ESPN public scoreboard',source_verified=True,
            neutral_venue=None,home_logo_url=crest(home_team),
            away_logo_url=crest(away_team)) if not completed else None
        return match, f
    except (KeyError, IndexError, StopIteration, TypeError, ValueError, AttributeError):
        return None, None


class ESPNProvider:
    """Read-only scoreboard feed. Three calendar years retained per competition."""
    name = 'ESPN public scoreboard'
    source_verified = True  # 'provider reported', NOT official UEFA/FIFA confirmation

    def __init__(self, *, session=None, leagues=None, years_back=2):
        self.session = session or requests.Session()
        self.leagues = tuple(leagues or ALLOWED)
        if not self.leagues or any(k not in ALLOWED for k in self.leagues):
            raise DailySourceError('Compétition ESPN non autorisée')
        if years_back not in (1,2,3):
            raise DailySourceError('Fenêtre de saisons ESPN non valide')
        self.years_back=years_back
        self._cache={}
        self._history={}
        self.discovery_counts={}

    def _fetch(self, league: str, date_selector: str):
        k=(league, date_selector)
        if k in self._cache:return self._cache[k]
        if not re.fullmatch(r'\d{4}(\d{4})?', date_selector):
            raise DailySourceError('Date ESPN non valide')
        try:
            r=self.session.get(f'{BASE}/{league}/scoreboard',
                params={'dates':date_selector,'limit':400},
                headers={'Accept':'application/json','User-Agent':'MrXPRONOS-Independent-ScoreResearch/1.0'},
                timeout=(8,30))
            if r.status_code!=200:
                raise DailySourceError(f'ESPN {league} {date_selector}: HTTP {r.status_code}')
            if len(r.content)>4_000_000:
                raise DailySourceError('ESPN : réponse trop volumineuse')
            data=r.json()
            if not isinstance(data,dict) or not isinstance(data.get('events'),list):
                raise DailySourceError('Réponse ESPN invalide')
            if len(data['events'])>400:
                raise DailySourceError('ESPN : limite de résultats dépassée; risque historique tronqué')
            self._cache[k]=data['events']
            return self._cache[k]
        except requests.RequestException as exc:
            raise DailySourceError(f'ESPN {league}: réseau indisponible ({type(exc).__name__})') from None
        except ValueError:
            raise DailySourceError('ESPN : réponse illisible') from None

    def discover(self, target_date:date, now:datetime):
        now=utc_datetime(now)
        out=[];errors=[]
        for league in self.leagues:
            try:
                fixtures=self._fetch(league,target_date.strftime('%Y%m%d'))
                n=0
                for item in fixtures:
                    m,f=parse_event(item,league,now=now)
                    if f and f.kickoff.date()==target_date:
                        out.append(f);n+=1
                self.discovery_counts[f'ESPN/{league}']=n
            except DailySourceError as exc:
                errors.append(str(exc))
                self.discovery_counts[f'ESPN/{league}']=0
        return out,errors

    def history(self, fixture:RankedFixture,now:datetime):
        now=utc_datetime(now)
        key=fixture.competition
        if key in self._history:return self._history[key]
        league=key.removeprefix('ES:').lower()
        if league not in self.leagues:
            raise DailySourceError('Compétition ESPN non configurée')
        history={};errors=[]
        # Calendar years: time-censored, no tomorrow/future results.
        for year in range(now.year-self.years_back,now.year+1):
            try:
                for event in self._fetch(league,str(year)):
                    m,f=parse_event(event,league,now=now)
                    if m and m.id not in history:history[m.id]=m
            except DailySourceError as exc:
                errors.append(str(exc))
        rows=sorted(history.values(),key=lambda m:(m.kickoff,m.id))
        self._history[key]=(rows,errors)
        return rows,errors
