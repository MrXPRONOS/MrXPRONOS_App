"""Transparent, editorial importance ranking. Never reads match results or betting odds."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

# Fixed editorial priority. Not a probability or prediction.
LEAGUE_WEIGHT = {
    'CL': 150, 'EC': 145, 'EL': 135, 'PL': 123, 'PD': 122,
    'BL1': 117, 'SA': 117, 'FL1': 115, 'PPL': 108, 'DED': 105,
    'ELC': 87, 'BSA': 90, 'OF:EN.1': 123, 'OF:ES.1': 122,
    'OF:DE.1': 117, 'OF:IT.1': 117, 'OF:FR.1': 115,
    'OF:PT.1': 108, 'OF:NL.1': 105, 'OF:EN.2': 87,
    'OL:BL1':117, 'OL:BL2':90, 'OL:BL3':76,
}
STAGE_WEIGHT = {
    'FINAL': 225, 'SEMI_FINALS': 105, 'QUARTER_FINALS': 62,
    'LAST_16': 35, 'PLAYOFFS': 38,
    'CHAMPIONSHIP': 22, 'CHAMPIONSHIP_ROUND': 22,
}
# Stable editorial labels: teams are prominent, not automatically strong on the pitch.
TEAM_WEIGHT = {
    'real madrid': 42, 'barcelona': 42, 'bayern': 41,
    'manchester city': 40, 'liverpool': 40, 'arsenal': 39,
    'manchester united': 38, 'chelsea': 37,
    'paris saint germain': 40, 'psg': 40, 'juventus': 38,
    'internazionale': 39, 'inter milan': 39, 'milan': 36,
    'borussia dortmund': 36, 'atletico madrid': 38,
    'napoli': 33, 'tottenham': 30, 'newcastle': 29,
    'bayer leverkusen': 33, 'rb leipzig': 29,
    'benfica': 33, 'porto': 31, 'sporting': 30,
    'ajax': 31, 'psv': 28, 'feyenoord': 27,
    'olympique marseille': 30, 'marseille': 30,
    'olympique lyonnais': 29, 'lyon': 29, 'monaco': 29,
    'lille': 24, 'nice': 23, 'roma': 29, 'lazio': 26,
    'atalanta': 29, 'fiorentina': 25, 'sevilla': 25,
    'real betis': 25, 'athletic club': 26,
    'real sociedad': 24, 'valencia': 23, 'villarreal': 24,
    'celtic': 27, 'rangers': 27, 'galatasaray': 27,
    'fenerbahce': 27, 'besiktas': 23, 'braga': 22,
    'boca juniors': 32, 'river plate': 32, 'flamengo': 32,
    'palmeiras': 32, 'santos': 25, 'sao paulo': 27,
}
DERBIES = (
    frozenset({'real madrid','barcelona'}),
    frozenset({'manchester united','manchester city'}),
    frozenset({'liverpool','manchester united'}),
    frozenset({'arsenal','tottenham'}),
    frozenset({'milan','internazionale'}),
    frozenset({'bayern','borussia dortmund'}),
    frozenset({'atletico madrid','real madrid'}),
    frozenset({'boca juniors','river plate'}),
    frozenset({'celtic','rangers'}),
)


def normalize(text: str) -> str:
    s=''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def _team_class(name: str) -> tuple[str, int]:
    s=' '+normalize(name)+' '
    matches=[(len(k), k, v) for k,v in TEAM_WEIGHT.items() if ' '+k+' ' in s]
    if not matches:
        return ('',0)
    _,team,weight=max(matches)
    return (team,weight)


@dataclass(frozen=True)
class RankedFixture:
    id: str
    competition: str
    competition_name: str
    kickoff: datetime
    home_id: str
    away_id: str
    home_name: str
    away_name: str
    stage: str
    source: str
    source_verified: bool
    neutral_venue: bool | None = None
    importance: int = 0
    importance_reasons: tuple[str,...] = ()


def importance(fixture: RankedFixture) -> RankedFixture:
    from dataclasses import replace
    code=fixture.competition.upper()
    key1,v1=_team_class(fixture.home_name)
    key2,v2=_team_class(fixture.away_name)
    weight=LEAGUE_WEIGHT.get(code, 60)
    reasons=[f'competition={weight}']
    if v1:
        weight+=v1;reasons.append(f'club_domicile={v1}')
    if v2:
        weight+=v2;reasons.append(f'club_exterieur={v2}')
    if v1>=29 and v2>=29:
        weight+=28;reasons.append('deux_grands_clubs=28')
    if key1 and key2 and frozenset({key1,key2}) in DERBIES:
        weight+=75;reasons.append('derby_reconnu=75')
    stage=STAGE_WEIGHT.get(fixture.stage.upper(),0)
    if stage:
        weight+=stage;reasons.append(f'tour_{fixture.stage.lower()}={stage}')
    return replace(fixture,importance=weight,importance_reasons=tuple(reasons))


def rank_fixtures(fixtures: list[RankedFixture]) -> list[RankedFixture]:
    return sorted([importance(f) for f in fixtures], key=lambda f:(-f.importance,f.kickoff,f.id))


def diverse_ranked(fixtures: list[RankedFixture], limit: int, max_per_league: int=4) -> list[RankedFixture]:
    """Choose broad coverage first; fill remaining slots in ranking order if necessary."""
    if limit<1:
        return []
    ranked=rank_fixtures(fixtures)
    result=[]; seen=set();counts={}
    for fixture in ranked:
        if fixture.id in seen or counts.get(fixture.competition,0)>=max_per_league:
            continue
        result.append(fixture);seen.add(fixture.id)
        counts[fixture.competition]=counts.get(fixture.competition,0)+1
        if len(result)==limit:return result
    for fixture in ranked:
        if fixture.id not in seen:
            result.append(fixture);seen.add(fixture.id)
            if len(result)==limit:break
    return result
