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
    'fifa.world': 'Coupe du monde FIFA',
    'uefa.euro': 'Championnat d’Europe des nations',
    # Expanded candidate registry; candidates are never silently enabled.
    'por.1': 'Primeira Liga Portugal',
    'ned.1': 'Eredivisie Pays-Bas',
    'tur.1': 'Süper Lig Turquie',
    'sco.1': 'Premiership Écosse',
    'bel.1': 'Pro League Belgique',
    'eng.2': 'Championship Angleterre',
    'bra.1': 'Série A Brésil',
    'arg.1': 'Primera División Argentine',
    'usa.1': 'Major League Soccer',
    'mex.1': 'Liga MX Mexique',
    'col.1': 'Primera A Colombie',
    'jpn.1': 'J1 League Japon',
    'kor.1': 'K League 1 Corée du Sud',
    'ksa.1': 'Saudi Pro League',
    'egy.1': 'Premier League Égypte',
    'mar.1': 'Botola Maroc',
    'rsa.1': 'Premiership Afrique du Sud',
    'uefa.nations': 'Ligue des Nations UEFA',
    'conmebol.libertadores': 'Copa Libertadores',
    'conmebol.sudamericana': 'Copa Sudamericana',
    'concacaf.champions': 'CONCACAF Champions Cup',
    'caf.champions': 'CAF Champions League',
    'caf.confederation': 'CAF Confederation Cup',
    'afc.champions': 'AFC Champions League',
    'ger.dfb_pokal': 'DFB Pokal',
    'esp.copa_del_rey': 'Coupe du Roi',
    'ita.coppa_italia': 'Coupe d’Italie',
    'fra.coupe_de_france': 'Coupe de France',
    'fifa.worldq.uefa': 'Qualifications Coupe du Monde Europe',
    'fifa.worldq.caf': 'Qualifications Coupe du Monde Afrique',
    'fifa.worldq.conmebol': 'Qualifications Coupe du Monde Amérique du Sud',
    'conmebol.america': 'Copa América',
    'caf.nations': 'Coupe d’Afrique des Nations',
    'concacaf.gold': 'Gold Cup',
    # Additional documented ESPN scoreboard slugs. Discovery ONLY in fallback.
    # Slugs may return HTTP 404 or 0 fixtures; we never invent a game.
    'fifa.friendly': 'Matchs amicaux internationaux',
    'fifa.friendly.w': 'Matchs amicaux internationaux féminins',
    'fifa.friendly_u21': 'Matchs amicaux internationaux U21',
    'club.friendly': 'Matchs amicaux de clubs',
    'concacaf.nations.league': 'CONCACAF Ligue des Nations',
    'caf.nations_qual': 'Qualifications CAN',
    'fifa.worldq.afc': 'Qualifications Coupe du Monde AFC',
    'fifa.worldq.concacaf': 'Qualifications Coupe du Monde CONCACAF',
    'fifa.worldq.ofc': 'Qualifications Coupe du Monde OFC',
    'fifa.world.u20': 'Coupe du monde U20',
    'fifa.world.u17': 'Coupe du monde U17',
    'usa.nwsl': 'NWSL féminine',
    'usa.usl.1': 'USL Championship',
    'usa.usl.l1': 'USL League One',
    'usa.open': 'US Open Cup',
    'mex.2': 'Liga Expansión MX',
    'bra.2': 'Série B Brésil',
    'chi.1': 'Première division Chili',
    'uru.1': 'Première division Uruguay',
    'per.1': 'Liga 1 Pérou',
    'par.1': 'Première division Paraguay',
    'bol.1': 'Première division Bolivie',
    'ecu.1': 'LigaPro Équateur',
    'ven.1': 'Première division Venezuela',
    'arg.copa': 'Coupe Argentine',
    'nga.1': 'Premier League Nigeria',
    'gha.1': 'Premier League Ghana',
    'afc.cup': 'AFC Champions League Two',
    'chn.1': 'Chinese Super League',
    'ind.1': 'Indian Super League',
    'tha.1': 'Thai League 1',
    'mys.1': 'Super League Malaisie',
    'idn.1': 'Super League Indonésie',
    'sgp.1': 'Premier League Singapour',
    'aus.1': 'A-League Australie',
    'aus.w.1': 'A-League féminine Australie',
    # Further ESPN league slugs confirmed in public community documentation.
    # These do NOT become part of the first-pass audited ENABLED list.
    'irl.1': 'Première division Irlande',
    'nor.1': 'Eliteserien Norvège',
    'swe.1': 'Allsvenskan Suède',
    'den.1': 'Superliga Danemark',
    'aut.1': 'Bundesliga Autriche',
    'gre.1': 'Super League Grèce',
    'cyp.1': 'Première division Chypre',
    'rus.1': 'Premier League Russie',
    'eng.3': 'League One Angleterre',
    'eng.4': 'League Two Angleterre',
    'eng.5': 'National League Angleterre',
    'eng.w.1': 'Women Super League Angleterre',
    'esp.2': 'La Liga 2 Espagne',
    'esp.w.1': 'Liga F féminine Espagne',
    'ger.2': '2. Bundesliga Allemagne',
    'ita.2': 'Serie B Italie',
    'fra.2': 'Ligue 2 France',
    'fra.w.1': 'Première Ligue féminine France',
    'ned.2': 'Eerste Divisie Pays-Bas',
    'ned.3': 'Tweede Divisie Pays-Bas',
    'usa.w.usl.1': 'USL Super League féminine',
    'can.w.nsl': 'Northern Super League Canada',
    'fifa.u20.friendly': 'Amicaux internationaux U20',
    'fifa.wworldq.uefa': 'Qualifications Coupe du monde féminine UEFA',
    'uefa.w.nations': 'Ligue des nations féminine UEFA',
    'nonfifa': 'Matchs amicaux hors FIFA',
}

# The catalog above is a *candidate* pool, not a claim of coverage.
# The enabled list retains 14 already tested competitions. New leagues are
# promoted only after separate historical and crest audits.
ENABLED = (
    'uefa.champions', 'uefa.europa', 'uefa.europa.conf',
    'eng.1', 'esp.1', 'ger.1', 'ita.1', 'fra.1',
    'eng.fa', 'eng.league_cup', 'uefa.wchampions', 'eng.trophy',
    'fifa.world', 'uefa.euro',
    # Enabled after four-shard V3 audit: >=80 past matches,
    # >=8 clubs with >=4 games, recent results, valid archived crests,
    # and no annual result page hitting the 400-event limit.
    'por.1', 'ned.1', 'tur.1', 'sco.1', 'bel.1',
    'bra.1', 'mex.1', 'ksa.1', 'jpn.1', 'rsa.1',
    'conmebol.libertadores', 'conmebol.sudamericana',
    'caf.champions', 'afc.champions',
    'ger.dfb_pokal', 'esp.copa_del_rey', 'fra.coupe_de_france',
)
CANDIDATES = tuple(code for code in ALLOWED if code not in ENABLED)


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
        if (re.search(r"\b(?:final|finale)\b", t)
                and not re.search(r"\bfinal (?:round|matchday|day)\b", t)):
            return "FINAL"
        if re.search(r"\bplay[\s-]?offs?\b", t):
            return "PLAYOFFS"
        if re.search(r"\b(?:round of 32|last 32)\b", t):
            return "LAST_32"
        value = stage_class(t)
        if value in ("FINAL", "SEMI_FINALS", "QUARTER_FINALS", "LAST_16",
                     "LAST_32", "PLAYOFFS", "CHAMPIONSHIP_ROUND", "CHAMPIONSHIP"):
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
        neutral = comp.get('neutralSite')
        if type(neutral) is not bool:
            neutral = None
        key = f'ES:{league.upper()}'
        match = (Match(
            id=f'espn:{league}:{event_id}',competition=key,kickoff=kickoff,
            home_id=f'espn:{league}:{hid}',away_id=f'espn:{league}:{aid}',
            home_name=hn,away_name=an,status='FINISHED',home_goals=hs,
            away_goals=as_,neutral_venue=neutral is True,source='espn-reported',result_provenance='provider_reported',
            season=str(kickoff.year))) if completed else None
        f = RankedFixture(
            id=f'espn:{league}:{event_id}',competition=key,
            competition_name=ALLOWED[league],kickoff=kickoff,
            home_id=f'espn:{league}:{hid}',away_id=f'espn:{league}:{aid}',
            home_name=hn,away_name=an,stage=_provider_round(event,comp),
            source='ESPN public scoreboard',source_verified=True,
            neutral_venue=neutral,home_logo_url=crest(home_team),
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
        self.leagues = tuple(ENABLED if leagues is None else leagues)
        # Only the default broad discovery may inspect catalogued alternatives.
        # Explicit test/custom league selections stay strict and deterministic.
        self.fallback_leagues = CANDIDATES if leagues is None else ()
        self._secondary_enabled: set[str] = set()
        if not self.leagues or len(set(self.leagues)) != len(self.leagues) or any(k not in ALLOWED for k in self.leagues):
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
            if len(r.content)>8_000_000:
                raise DailySourceError('ESPN : réponse trop volumineuse')
            data=r.json()
            if not isinstance(data,dict) or not isinstance(data.get('events'),list):
                raise DailySourceError('Réponse ESPN invalide')
            if len(data['events'])>400:
                raise DailySourceError('ESPN : limite de résultats dépassée; risque historique tronqué')
            if len(date_selector)==4 and len(data['events'])==400:
                # ESPN year scoreboards can silently stop at the requested 400
                # event limit. Never train on an incomplete 400-match sample.
                raise DailySourceError(f'ESPN {league} {date_selector}: troncature historique possible à 400 matchs')
            self._cache[k]=data['events']
            return self._cache[k]
        except requests.RequestException as exc:
            raise DailySourceError(f'ESPN {league}: réseau indisponible ({type(exc).__name__})') from None
        except DailySourceError:
            raise
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

    def discover_more(self, target_date:date, now:datetime):
        """Second-pass discovery only when the core pools cannot fill ten.

        A genuine ESPN event must still include the provider's scheduled match,
        two distinct team IDs and a future kickoff; no speculative fixtures.
        Source errors never silently create matches.
        """
        now=utc_datetime(now)
        found=[];errors=[]
        for league in self.fallback_leagues:
            try:
                records=self._fetch(league,target_date.strftime('%Y%m%d'))
                n=0
                for event in records:
                    _past,fixture=parse_event(event,league,now=now)
                    if fixture and fixture.kickoff.date()==target_date:
                        found.append(fixture)
                        self._secondary_enabled.add(league)
                        n+=1
                self.discovery_counts[f'ESPN/fallback/{league}']=n
            except DailySourceError as exc:
                errors.append(str(exc))
                self.discovery_counts[f'ESPN/fallback/{league}']=0
        return found,errors

    def history(self, fixture:RankedFixture,now:datetime):
        now=utc_datetime(now)
        key=fixture.competition
        if key in self._history:return self._history[key]
        league=key.removeprefix('ES:').lower()
        if league not in self.leagues and league not in self._secondary_enabled:
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
        if any('troncature historique' in warning for warning in errors):
            # A partial annual archive is not safe for fitting Dixon-Coles.
            self._history[key]=([],errors)
            return self._history[key]
        rows=sorted(history.values(),key=lambda m:(m.kickoff,m.id))
        self._history[key]=(rows,errors)
        return rows,errors
