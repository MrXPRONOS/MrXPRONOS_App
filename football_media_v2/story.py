"""Éditorial vérifiable, sans récit fictif de buts ou d'actions.

Toute affirmation est dérivée de champs confirmés de football-data.org.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import datetime as dt
import re

@dataclass(frozen=True)
class Scene:
    kind: str
    eyebrow: str
    headline: str
    sub: str
    voice: str
    duration: float


def _clean(s: str, limit=65) -> str:
    return re.sub(r'\s+', ' ', str(s or '')).strip()[:limit]


def parse_match(raw: dict) -> dict | None:
    if raw.get('status') != 'FINISHED':
        return None
    score = (raw.get('score') or {}).get('fullTime') or {}
    a, b = score.get('home'), score.get('away')
    if type(a) is not int or type(b) is not int or min(a,b)<0 or max(a,b)>35:
        return None
    home, away = _clean((raw.get('homeTeam') or {}).get('name')), _clean((raw.get('awayTeam') or {}).get('name'))
    if not home or not away or home == away or not raw.get('id'):
        return None
    return dict(id=str(raw['id']), home=home, away=away, a=a, b=b,
                competition=_clean((raw.get('competition') or {}).get('name') or 'Football'),
                date=str(raw.get('utcDate') or '')[:10], source='football-data.org')


def select_match(matches: list[dict], seen: set[str]) -> dict | None:
    eligible=[m for raw in matches if (m:=parse_match(raw)) and ('match:'+m['id']) not in seen]
    def score(m):
        total=m['a']+m['b']; diff=abs(m['a']-m['b'])
        # Sélection éditoriale : buts et tension *du score final*, sans inventer de déroulé.
        return (4*min(total,8) + (9 if diff==1 and total>=3 else 0)
                + (5 if m['a']>0 and m['b']>0 else 0) + (4 if total>=5 else 0),m['date'],m['id'])
    return max(eligible,key=score) if eligible else None


def match_scenes(m: dict) -> list[Scene]:
    a,b=m['a'],m['b']; total=a+b; delta=abs(a-b)
    home,away=m['home'],m['away']
    if total>=5:
        hook=f'{total} BUTS.'; mini='UN SCORE QUI FAIT RÉAGIR'
        vocal=f'{total} buts dans une seule rencontre. Et voici le score officiel.'
    elif delta==1 and total>0:
        hook='UN SEUL BUT.'; mini="D'ÉCART AU FINAL"
        vocal="Un seul but sépare ces deux équipes au coup de sifflet final."
    elif a==b:
        hook='PERSONNE NE GAGNE.'; mini='LE SCORE EST TOMBÉ'
        vocal="Au bout du match, impossible de départager les deux équipes."
    else:
        hook='LE VERDICT.'; mini='DÉCOUVRE LE SCORE FINAL'
        vocal='Voici un résultat de football qui mérite un coup d’œil.'
    if a==b:
        verdict='MATCH NUL'; resolution=f'{home} et {away} repartent sur un nul.'
    else:
        victor=home if a>b else away
        verdict=f'VICTOIRE : {victor.upper()}'
        resolution=f'{victor} remporte ce match avec {delta} but' + ('s' if delta>1 else '') + " d'écart."
    both=a>0 and b>0
    insight=('LES 2 ONT MARQUÉ' if both else ('ZÉRO BUT ENCAISSÉ' if min(a,b)==0 and max(a,b)>0 else 'AUCUN BUT'))
    insight_voice=('Les deux équipes ont marqué au moins une fois.' if both else
                   ('Une équipe termine ce match sans encaisser de but.' if total else 'Aucune équipe n’a trouvé le chemin des filets.'))
    date=m['date'] or 'DATE NON PRÉCISÉE'
    return [
      Scene('hook','STOP SCROLL',hook,mini,vocal,2.3),
      Scene('stadium','FOOTBALL / DÉCRYPTAGE','LE SCORE ?','LA RÉPONSE DANS UN INSTANT',f'{home} face à {away}.',2.0),
      Scene('versus','FACE À FACE',home.upper(),'VS  '+away.upper(),"Regardons les faits vérifiés, sans inventer le déroulement.",2.4),
      Scene('score','RÉSULTAT OFFICIEL',f'{a}  :  {b}',f'{home.upper()}  —  {away.upper()}',f'Score final : {home}, {a}. {away}, {b}.',3.0),
      Scene('goal','CE QUE DIT LE SCORE',f'{total} BUT' + ('S' if total!=1 else ''),'AU TOTAL DANS LE MATCH',f'Il y a eu {total} but' + ('s' if total!=1 else '') + ' au total.',2.4),
      Scene('pitch','LE FAIT À RETENIR',insight,'CHIFFRE CONFIRMÉ',insight_voice,2.5),
      Scene('verdict','LE VERDICT',verdict,f'ÉCART : {delta} BUT' + ('S' if delta!=1 else ''),resolution,2.7),
      Scene('source','PAS DE STAT INVENTÉE','DES FAITS.','PAS DES SUPPOSITIONS.',f'Données issues de football data point org, match du {date}.',2.2),
      Scene('cta','À TOI DE JOUER','TON AVIS ?','COMBIEN TU METS À CE MATCH ?','Sur dix, tu donnes combien à ce score ? Dis-le en commentaire et abonne-toi à Mister X Pronos.',3.1)
    ]


def parse_scorers(raw: dict, code='PL') -> dict | None:
    arr=raw.get('scorers')
    if not isinstance(arr,list): return None
    data=[]
    for item in arr:
        p=item.get('player') or {}; team=item.get('team') or {}
        name=_clean(p.get('name'),45); count=item.get('goals')
        if name and type(count) is int and 0<=count<=100:
            entry={'name':name,'goals':count,'team':_clean(team.get('name'),40)}
            for metric in ('playedMatches','assists'):
                value=item.get(metric)
                if type(value) is int and 0<=value<=1000:
                    entry[metric]=value
            data.append(entry)
    if len(data)<3: return None
    data.sort(key=lambda x:(-x['goals'],x['name']))
    comp=_clean((raw.get('competition') or {}).get('name') or code)
    return {'code':code,'competition':comp,'scorers':data[:5], 'source':'football-data.org'}


def scorers_scenes(r: dict)->list[Scene]:
    lst=r['scorers']; comp=r['competition']; lead=lst[0]
    arr=[Scene('hook','CLASSEMENT ACTUEL','QUI DOMINE ?','LES BUTEURS EN CHIFFRES',f'Qui domine le classement des buteurs en {comp} ? Voici les chiffres disponibles.',2.4),
         Scene('stadium','ÉDITION BUTEURS','TOP 5','DES NOMS. DES BUTS.',f'On remonte le classement jusqu’à la première place.',2.0)]
    for i,player in enumerate(reversed(lst)):
        rank=len(lst)-i
        arr.append(Scene('scorer',f'PLACE NUMÉRO {rank}',player['name'].upper(),f"{player['goals']} BUTS  •  {player['team'].upper()}",
                         f"Numéro {rank}, {player['name']}, {player['goals']} buts.",2.6 if rank==1 else 2.3))
    arr.extend([Scene('verdict','EN TÊTE DU CLASSEMENT',lead['name'].upper(),f"{lead['goals']} BUTS  •  {comp.upper()}",
                      f"À la première place de ce classement : {lead['name']}, avec {lead['goals']} buts.",2.4),
                Scene('cta','ET TOI ?','TON FAVORI ?','DIS-LE EN COMMENTAIRE',
                      "Qui va terminer meilleur buteur ? Donne ton avis en commentaire et abonne-toi à Mister X Pronos.",2.9)])
    return arr


def demo_match():
    return {'id':'DEMO-NO-PUBLISH','home':'Équipe Azur','away':'Équipe Éclair','a':3,'b':2,
            'date':'2026-01-01','competition':'DÉMONSTRATION FICTIVE','source':'DEMO'}
