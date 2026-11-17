"""Mr XPRONOS — editorial decision engine, lot 2 (items 7–17).

All narrative facts are structured, attributed evidence, not model-generated
assertions. football-data.org scores NEVER imply goal timing, comebacks,
records or tactical dominance. A source URL is provenance, NOT proof by itself:
curated storypacks require separate human fact review before production.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import hashlib
import json
import re

from .story import Scene, parse_match, parse_scorers

FORMAT_NAMES = ('highlights', 'portrait', 'story', 'tactical', 'ranking', 'comparison')
GENERIC_HOOKS = ('stop scroll', 'les faits', 'le verdict', 'incroyable', 'le score ?', 'tu ne vas pas croire', 'des faits', 'qui domine ?')
ALLOWED_DOMAINS = ('fifa.com', 'uefa.com', 'football-data.org', 'the-afc.com', 'cafonline.com', 'thefa.com', 'premierleague.com', 'bundesliga.com', 'laliga.com', 'legaseriea.it', 'ligue1.com')


@dataclass(frozen=True)
class Fact:
    id: str
    value: str
    source: str
    url: str
    provenance: str = 'api'  # api | reviewed


@dataclass
class Topic:
    event_id: str
    angle: str
    format: str
    subject: str
    competition: str
    event_date: str
    facts: list[Fact]
    data: dict = field(default_factory=dict)
    verified: bool = False
    media_count: int = 0
    reason: str = ''
    score: int = 0
    score_breakdown: dict = field(default_factory=dict)

    @property
    def fingerprint(self):
        return hashlib.sha256(f'{self.event_id}|{self.angle}'.casefold().encode()).hexdigest()[:16]

    @property
    def state_key(self):
        return f'editorial:{self.fingerprint}'


def source_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        return parsed.scheme == 'https' and any(host == d or host.endswith('.'+d) for d in ALLOWED_DOMAINS)
    except ValueError:
        return False


def _fact(fid, value, url, provenance='api') -> Fact:
    if not value or not source_url(url):
        raise ValueError(f'Source manquante ou non autorisée : {fid}')
    return Fact(str(fid), str(value), urlparse(url).hostname or '', url, provenance)


def _date_age(when: str, today: date) -> int:
    try:
        return max(0, (today - date.fromisoformat(when[:10])).days)
    except (ValueError, TypeError):
        return 730


def _match_topics(raw: dict) -> list[Topic]:
    m = parse_match(raw)
    if not m:
        return []
    a,b=m['a'],m['b']
    total=a+b
    diff=abs(a-b)
    # No timeline, no comeback, no 'decisive goal'. Only rare scoreline is eligible
    # as a draft candidate, NOT a substantiated long-form narrative.
    if total < 6 or diff > 1:
        return []
    comp = m['competition']
    url = f"https://api.football-data.org/v4/matches/{m['id']}"
    facts=[_fact('score', f"{m['home']} {a}-{b} {m['away']}",url),
           _fact('total', f'{total} buts au total (calcul du score final)',url),
           _fact('margin', f'{diff} but d’écart au coup de sifflet final',url)]
    t=Topic(f"match:{m['id']}",'goal_festival','story',f"{m['home']} – {m['away']}",comp,m['date'],facts,
            {'home':m['home'],'away':m['away'],'a':a,'b':b,'total':total,'margin':diff,'is_score_only':True},
            verified=True,reason='Score final spectaculaire, mais déroulement inconnu')
    return [t]


def _scorer_topics(raw: dict, code='PL') -> list[Topic]:
    data = parse_scorers(raw, code)
    if not data or len(data['scorers']) < 5:
        return []
    players=data['scorers']; comp=data['competition']
    if players[0]['goals'] < 7: return []
    # No made-up 'rank 1' when several scorers share the same total.
    if len({p['goals'] for p in players}) != len(players):return []
    url=f'https://api.football-data.org/v4/competitions/{code}/scorers'
    facts=[_fact(f'scorer-{i}',f"{p['name']} : {p['goals']} buts, {p['team']}",url) for i,p in enumerate(players,1)]
    stamp=str(raw.get('season',{}).get('id') or raw.get('season',{}).get('startDate') or 'current')
    topics=[Topic(f'scorers:{code}:{stamp}', 'top_five', 'ranking',f'Classement des buteurs — {comp}', comp,
                  date.today().isoformat(),facts, {'players':players,'code':code}, verified=True,
                  reason='Cinq statistiques individuelles issues du même classement officiel')]
    gap=players[0]['goals']-players[1]['goals']
    if gap<=2 and players[1]['goals']>=7:
        topics.append(Topic(f'scorers:{code}:{stamp}', 'neck_and_neck','comparison',
            f"{players[0]['name']} / {players[1]['name']}",comp,date.today().isoformat(),facts[:2],
            {'players':players[:2],'gap':gap},verified=True,reason='Deux buteurs au coude-à-coude'))
    if players[0].get('playedMatches') and players[0]['goals']>=10:
        player=players[0]
        f=facts[:1]+[_fact('appearances',f"{player['playedMatches']} matches joués",url)]
        if type(player.get('assists')) is int:
            f.append(_fact('assists',f"{player['assists']} passes décisives",url))
        topics.append(Topic(f'scorers:{code}:{stamp}', 'leader_focus','portrait',
            player['name'],comp,date.today().isoformat(),f, {'player':player},verified=True,
            reason='Profil avec buts, matches et éventuellement passes décisives'))
    return topics


def _curated_topic(pack:dict) -> Topic | None:
    if not isinstance(pack,dict) or pack.get('format') not in FORMAT_NAMES or pack.get('reviewed') is not True:
        return None
    fields=['id','angle','subject','competition','event_date','facts','script_data']
    if any(not pack.get(k) for k in fields):return None
    facts=[];seen=set()
    for f in pack['facts']:
        if not isinstance(f,dict) or any(not f.get(k) for k in ('id','value','source_url')):return None
        if f['id'] in seen:return None
        seen.add(f['id'])
        try:facts.append(_fact(f['id'],f['value'],f['source_url'],'reviewed'))
        except ValueError:return None
    if len(facts)<4:return None
    if pack['format']=='story':
        data=pack['script_data']
        if not isinstance(data,dict) or data.get('template')!='comeback_final' or not all(k in data for k in ('goals','winner','penalty_score','half_time_leader','half_time_score','final_score')):return None
        goals=data['goals']
        if len(goals)!=4 or any(not all(k in g for k in ('minute','player','side','fact_id')) or g['fact_id'] not in seen for g in goals):return None
        if not all(type(g['minute']) is int and 1<=g['minute']<=130 for g in goals):return None
    if pack['format']=='highlights':return None  # must come from rights.cleared(), never JSON text alone
    if pack['format'] in ('ranking','comparison','portrait'):
        # Their API-backed versions use structured goals/matches data. Reject
        # manually curated free-form packs that cannot supply this schema.
        if pack['format']=='ranking' and len(pack['script_data'].get('players',[]))<5:return None
        if pack['format']=='comparison' and len(pack['script_data'].get('players',[]))!=2:return None
        if pack['format']=='portrait' and not pack['script_data'].get('player',{}).get('playedMatches'):return None
    if pack['format']=='tactical':
        data=pack['script_data']
        if not isinstance(data,dict) or len(data.get('metrics',[]))<2:return None
        if any(m.get('fact_id') not in seen for m in data['metrics']):return None
    return Topic(str(pack['id']),str(pack['angle']),pack['format'],str(pack['subject']),
          str(pack['competition']),str(pack['event_date']),facts,pack['script_data'],True,
          int(pack.get('licensed_media_count',0)),reason='Dossier factuel relu et liens officiels associés')


def load_storypacks(path:Path)->list[dict]:
    if not path.is_file():return []
    raw=json.loads(path.read_text('utf-8'))
    if not isinstance(raw,dict) or not isinstance(raw.get('stories'),list):
        raise ValueError('Format des dossiers éditoriaux invalide')
    return raw['stories']


def discover_topics(matches:list[dict]|None=None,scorers:dict|None=None,storypacks:list[dict]|None=None,
                    competition_code='PL')->list[Topic]:
    candidates=[]
    for match in (matches or []):candidates.extend(_match_topics(match))
    if scorers:candidates.extend(_scorer_topics(scorers,competition_code))
    for raw in (storypacks or []):
        t=_curated_topic(raw)
        if t:candidates.append(t)
    return candidates


def is_duplicate(topic:Topic,history:dict,today:date)->bool:
    keys=set(history.get('seen',[]))
    if topic.state_key in keys:return True
    # Older versions stored only a match id. Honour those markers.
    if topic.event_id in keys:return True
    for item in history.get('editorial_history',[]):
        if item.get('fingerprint')==topic.fingerprint:return True
        if item.get('event_id')==topic.event_id:
            try:
                age=(today-date.fromisoformat(item['published_at'][:10])).days
            except (ValueError,KeyError):age=0
            if 0<=age<=14:return True
    return False


def score_topic(topic:Topic,today:date|None=None,media_count:int|None=None)->Topic:
    today=today or date.today()
    age=_date_age(topic.event_date,today)
    freshness = 20 if age<=1 else 16 if age<=3 else 10 if age<=14 else 4 if age<=365 else 1
    amount=len(topic.facts)
    evidence=min(25,amount*4 + (5 if all(source_url(f.url) for f in topic.facts) else 0))
    if topic.format=='story' and topic.data.get('template')=='comeback_final':
        surprise,story,importance=20,20,15
    elif topic.format=='ranking':
        surprise,story,importance=8,15,12
    elif topic.format=='comparison':
        surprise,story,importance=13,16,13
    elif topic.format=='portrait':
        surprise,story,importance=8,13,13
    elif topic.format=='tactical':
        surprise,story,importance=10,16,13
    elif topic.format=='highlights':
        surprise,story,importance=15,15,13
    else:surprise,story,importance=0,0,0
    if topic.data.get('is_score_only'):
        story=2; surprise=8; evidence=min(evidence,10)
    available=topic.media_count if media_count is None else media_count
    media=min(10,max(0,available)*2)
    total=freshness+evidence+surprise+story+importance+media
    topic.score=min(100,total)
    topic.score_breakdown={'actualite':freshness,'preuves':evidence,'surprise':surprise,
        'angle':story,'importance':importance,'medias':media,'total':topic.score}
    return topic


def merits_video(topic:Topic)->tuple[bool,str]:
    if not topic.verified:return False,'Faits non vérifiés'
    if topic.data.get('is_score_only'):return False,'Le score seul ne suffit pas à raconter une histoire'
    if topic.format=='highlights' and topic.media_count<2:return False,'Au moins 2 clips autorisés nécessaires'
    if topic.format=='story' and len(topic.facts)<6:return False,'Histoire insuffisamment étayée'
    if topic.format=='tactical' and len(topic.data.get('metrics',[]))<2:return False,'Statistiques tactiques absentes'
    if topic.score<60:return False,f'Intérêt éditorial insuffisant ({topic.score}/100)'
    return True,'Angle documenté et intérêt suffisant (à valider par spectateur)'


def select_topic(topics:list[Topic], history:dict|None=None, today:date|None=None,
                 min_score=60)->tuple[Topic|None,list[dict]]:
    history=history or {'seen':[]};today=today or date.today()
    report=[];accepted=[]
    for topic in topics:
        score_topic(topic,today)
        ok,why=merits_video(topic)
        if topic.score<min_score:ok=False;why='Score éditorial sous seuil'
        if is_duplicate(topic,history,today):ok=False;why='Déjà publié : événement/angle'
        report.append({'id':topic.event_id,'angle':topic.angle,'format':topic.format,
                       'score':topic.score,'breakdown':topic.score_breakdown,'eligible':ok,'reason':why})
        if ok:accepted.append(topic)
    return (max(accepted,key=lambda t:(t.score,t.fingerprint)) if accepted else None),report


@dataclass
class Draft:
    variant: str
    scenes: list[Scene]
    evidence: list[list[str]]
    score: int = 0
    rubric: dict = field(default_factory=dict)
    @property
    def voice(self):return ' '.join(s.voice.strip() for s in self.scenes if s.voice.strip())


def _s(kind,eyebrow,title,sub,voice,seconds):return Scene(kind,eyebrow,title,sub,voice,seconds)


def _verified_comeback(topic:Topic,variant:str)->Draft:
    """A source-linked *2-0 to 2-2* comeback, not an imagined match timeline.

    Requires a reviewed pack: the first two events belong to the chasing side;
    the late events alternate leader/chaser, and the final score is documented.
    The story can be narrated non-chronologically, but no event is fabricated.
    """
    d=topic.data
    g=sorted(d['goals'],key=lambda v:v['minute'])
    a,b,c,e=g[:4]
    leader=d['half_time_leader']
    chaser=a['side']
    winner=d['winner']
    speech=d.get('team_speech',{})
    leader_voice=speech.get(leader,leader)
    chaser_voice=speech.get(chaser,chaser)
    winner_voice=speech.get(winner,winner)
    focus=d.get('focus_player','')
    if not (d.get('half_time_score')=='2-0' and len(g)==4
            and a['side']==b['side']==e['side']==chaser
            and c['side']==leader and chaser!=leader and winner==leader
            and d.get('final_score')=='3-3'):
        raise ValueError('Déroulement non compatible avec ce modèle de finale')
    if not (a['minute']<b['minute']<c['minute']<e['minute']):
        raise ValueError('Ordre des événements incohérent')
    double=a['player']==b['player']
    triplet=double and b['player']==e['player']
    if focus and (focus!=a['player'] or not triplet):
        raise ValueError('Triplé non corroboré par les événements détaillés')
    if variant=='paradox':
        if not ('hat_trick' in {x.id for x in topic.facts} and triplet and focus):
            raise ValueError('Triplé non attesté par une source')
        hook='3 BUTS. PAS DE TITRE.'
        opening='Trois buts. Pas de titre.'
        ids=['hat_trick','penalties']
    elif variant=='minutes':
        hook=f"{a['minute']}e. {b['minute']}e. LE RETOUR."
        opening='Deux buts en une minute.' if b['minute']-a['minute']==1 else 'Deux buts rapprochés. Une égalisation.'
        ids=[a['fact_id'],b['fact_id']]
    else:
        hook='DE 2-0 À 2-2.'
        opening='De deux-zéro à deux partout.'
        ids=['halftime',a['fact_id'],b['fact_id']]
    s=[
      _s('hook','UNE FINALE HORS NORME',hook,topic.subject,opening,3.2),
      _s('stadium','REVENONS EN ARRIÈRE','2 - 0',f'{leader.upper()} À LA PAUSE',
         f"Revenons à la mi-temps : {leader_voice} mène deux à zéro.",2.7),
      _s('versus','LE PREMIER DÉCLIC',f"{a['minute']}e : {a['player'].split()[-1].upper()}",'LE RETOUR COMMENCE',
         f"À la {a['minute']}e minute, {a['player']} réduit l’écart" + (' sur penalty.' if d.get('first_penalty') else '.'),2.9),
      _s('goal','LE DEUXIÈME BUT',f'{b["minute"]}e : ÉGALISATION',f"{chaser.upper()} REVIENT", 
         f"À la {b['minute']}e minute, {b['player']} égalise.",2.8),
      _s('pitch','LA PROLONGATION',f"{c['minute']}e : {c['player'].split()[-1].upper()}",f'{leader.upper()} REPREND LA TÊTE',
         f"En prolongation, {c['player']} redonne l’avantage à {leader_voice}.",2.9),
      _s('score','MAIS CE N’EST PAS FINI',f"{e['minute']}e : {e['player'].split()[-1].upper()}",f'{chaser.upper()} ÉGALISE ENCORE',
         f"À la {e['minute']}e, {e['player']} égalise encore" + ('.' if not triplet else ' : son troisième but.'),2.7),
      _s('verdict','APRÈS PROLONGATION','3 - 3','LE MATCH SE DÉCIDE AUTREMENT',
         'Trois partout après prolongation. Direction les tirs au but.',2.5),
      _s('source','AUX TIRS AU BUT',d['penalty_score'],f"{winner.upper()} CHAMPIONNE", 
         f"Aux tirs au but, {winner_voice} s’impose {d['penalty_score'].replace('-', ' à ')}.",3.1),
      _s('cta','TON MOMENT FORT','LEQUEL RETIENS-TU ?',"LE DOUBLÉ OU LES TIRS AU BUT ?",
         'Quel moment retiens-tu de cette finale : le doublé express ou la séance de tirs au but ?',3.2)
    ]
    # Versions vraiment distinctes : angle, cadence et conclusion, pas seulement
    # trois titres sur un même script.
    from dataclasses import replace
    if variant=='minutes':
        s[1]=replace(s[1],voice=f"Pour comprendre ces deux minutes, retournons à la pause : {leader_voice} mène deux-zéro.")
        s[6]=replace(s[6],voice="Six buts, trois partout, et une décision aux tirs au but.")
        s[8]=replace(s[8],voice=f"Entre les buts des {a['minute']}e et {b['minute']}e minutes, lequel est ton moment fort ?")
    elif variant=='comeback':
        s[1]=replace(s[1],voice=f"Au départ, {leader_voice} semble bien parti : deux buts d’avance à la pause.")
        s[6]=replace(s[6],voice="Deux égalisations plus tard, le score affiche trois partout après prolongation.")
        s[8]=replace(s[8],voice=f"Et toi, as-tu été plus surpris par le retour de {chaser_voice} ou par le résultat final ?")
    ev=[ids,['halftime'],[a['fact_id']],[b['fact_id']],[c['fact_id']],
        [e['fact_id']]+(['hat_trick'] if triplet and 'hat_trick' in {x.id for x in topic.facts} else []),
        ['finalscore'],['penalties'],[a['fact_id'],b['fact_id'],'penalties']]
    return Draft(variant,s,ev)


def _ranking(topic:Topic,variant:str)->Draft:
    people=topic.data['players']
    if len(people)<5:raise ValueError('Classement trop court')
    leader=people[0];runner=people[1]
    gap=leader['goals']-runner['goals']
    if variant=='gap':
        hook=f'{gap} BUT' + ('S' if gap>1 else '') + ' D’ÉCART.'
        opening=f"Seulement {gap} but" + ('s d’écart.' if gap>1 else ' d’écart.')
    elif variant=='leader':
        hook=f"{leader['goals']} BUTS. EN TÊTE."
        opening=f"{leader['goals']} buts. Premier du classement."
    else:
        hook='TOP 5 DES BUTEURS.'
        opening='Cinq buteurs. Une première place.'
    scenes=[_s('hook','COURSE AU SOULIER D’OR',hook,topic.competition,opening,2.6)]
    evidence=[['scorer-1','scorer-2'] if variant=='gap' else ['scorer-1']]
    kinds=['stadium','versus','goal','pitch','score']
    for position,p in enumerate(reversed(people),1):
        place=6-position;kind=kinds[position-1]
        scenes.append(_s(kind,f'PLACE N° {place}',p['name'].upper(),f"{p['goals']} BUTS • {p['team']}",
                         f"En numéro {place}, {p['name']}, avec {p['goals']} buts.",2.5))
        evidence.append([f'scorer-{place}'])
    scenes.extend([
      _s('verdict','LE LEADER',leader['name'].upper(),f"{leader['goals']} BUTS",f"Il est donc en tête avec {leader['goals']} buts.",2.5),
      _s('cta','TON PRONOSTIC','QUI FINIRA 1er ?',"DONNE TON FAVORI",'Qui terminera premier à la fin de la saison ? Donne ton pronostic.',2.4)
    ])
    evidence.extend([['scorer-1'],['scorer-1','scorer-2']])
    return Draft(variant,scenes,evidence)


def _comparison(topic:Topic,variant:str)->Draft:
    a,b=topic.data['players'][:2];gap=topic.data['gap']
    choices={'numbers':(f"{a['goals']} CONTRE {b['goals']}.",f"{a['goals']} contre {b['goals']} : la course est serrée."),
             'names':(f"{a['name']} OU {b['name']} ?",'Deux noms pour une première place.'),
             'gap':(f"{gap} BUT D’ÉCART.",f"Seulement {gap} but"+('s d’écart.' if gap>1 else ' d’écart.') )}
    headline,vocal=choices[variant]
    scenes=[_s('hook','DUEL DE BUTEURS',headline,topic.competition,vocal,2.9),
            _s('versus','PREMIER AU CLASSEMENT',a['name'].upper(),f"{a['goals']} BUTS",f"{a['name']} compte {a['goals']} buts.",2.8),
            _s('stadium','JUSTE DERRIÈRE',b['name'].upper(),f"{b['goals']} BUTS",f"Juste derrière, {b['name']} en compte {b['goals']}.",2.7),
            _s('goal','L’ÉCART',f'{gap} BUT'+('S' if gap>1 else ''),"CLASSEMENT DISPONIBLE",f"La différence n’est que de {gap} but"+('s.' if gap>1 else '.'),2.4),
            _s('pitch','DEUX CHIFFRES','MÊME COURSE.',"LES BUTS NE DISENT PAS TOUT",'Ces chiffres comparent les buts inscrits, pas toutes les qualités de ces joueurs.',2.5),
            _s('score','EN TÊTE',a['name'].upper(),f"{a['goals']} BUTS",f"Pour l’instant, {a['name']} reste en tête de ce classement.",2.7),
            _s('verdict','À SURVEILLER','LE PROCHAIN MATCH',"L’ÉCART PEUT CHANGER",'Ce classement peut évoluer dès les prochaines rencontres.',2.5),
            _s('cta','À TON AVIS','QUI FINIRA DEVANT ?',"TON AVIS EN COMMENTAIRE",'Qui terminera devant ? Fais ton choix.',2.6)]
    return Draft(variant,scenes,[['scorer-1','scorer-2'],['scorer-1'],['scorer-2'],['scorer-1','scorer-2'],['scorer-1','scorer-2'],['scorer-1'],['scorer-1','scorer-2'],['scorer-1','scorer-2']])


def _portrait(topic:Topic,variant:str)->Draft:
    p=topic.data['player'];goals=p['goals'];matches=p['playedMatches'];ratio=goals/matches if matches else 0
    lead=f"{p['name']} : {goals} buts en {matches} matchs."
    hook={ 'numbers':f'{goals} BUTS EN {matches} MATCHS.',
           'name':p['name'].upper(),
           'question':'QUELLE RÉGULARITÉ ?'}[variant]
    opening={'numbers':f'{goals} buts. {matches} matchs.', 'name':f'Focus sur {p["name"]}.',
             'question':f'Quel rendement pour {p["name"]} ?'}[variant]
    scenes=[_s('hook','PORTRAIT DE BUTEUR',hook,topic.competition,opening,2.8),
            _s('stadium','L’ESSENTIEL',p['name'].upper(),p['team'],f"Il évolue à {p['team']}.",2.5),
            _s('versus','BILAN','BUTS MARQUÉS',f'{goals} BUTS',f"Son total : {goals} buts.",2.4),
            _s('goal','MATCHS JOUÉS',f'{matches} MATCHS',"STATISTIQUE OFFICIELLE",f"Et {matches} rencontres disputées.",2.5),
            _s('pitch','RENDEMENT',f'{ratio:.2f} BUT / MATCH',"MOYENNE CALCULÉE",f"Soit une moyenne de {ratio:.2f} but par match.",2.8),
            _s('score','EN TÊTE',p['name'].upper(),"CLASSEMENT DES BUTEURS",'C’est le premier du classement de buteurs consulté.',2.5),
            _s('verdict','LE FAIT',f'{goals} BUTS',f'EN {matches} MATCHS',"C’est son bilan chiffré actuel.",2.1),
            _s('cta','À TON AVIS','MEILLEUR BUTEUR ?',"TON PRONOSTIC",'Va-t-il conserver la tête du classement ?',2.4)]
    evidence=[['scorer-1','appearances'],['scorer-1'],['scorer-1'],['appearances'],['scorer-1','appearances'],['scorer-1'],['scorer-1','appearances'],['scorer-1']]
    return Draft(variant,scenes,evidence)


def _tactical(topic:Topic,variant:str)->Draft:
    data=topic.data
    metrics=data['metrics'];a,b=metrics[:2]
    # Never interpret possession as dominance or infer formation without data.
    hook={'contrast':f"{a['label']} : {a['home']} / {a['away']}",
          'focus':f"{b['label']} : {b['home']} / {b['away']}",
          'question':'QUE RACONTENT LES CHIFFRES ?'}[variant]
    voice={'contrast':f"{a['home']} contre {a['away']} : {a['label']}.",
           'focus':f"{b['home']} contre {b['away']} : {b['label']}.",
           'question':'Que disent vraiment les chiffres ?'}[variant]
    scenes=[_s('hook','STATISTIQUES DU MATCH',hook,topic.subject,voice,2.8),
            _s('versus','LES ÉQUIPES',topic.subject.upper(),topic.competition,f"Un face-à-face en {topic.competition}.",2.5),
            _s('goal',a['label'],f"{a['home']} / {a['away']}","STAT CONFIRMÉE",f"{a['label']} : {a['home']} pour la première équipe, {a['away']} pour la seconde.",3),
            _s('pitch',b['label'],f"{b['home']} / {b['away']}","STAT CONFIRMÉE",f"{b['label']} : {b['home']} contre {b['away']}.",3),
            _s('stadium','À NE PAS CONFONDRE','UN CHIFFRE ≠ UN MATCH',"AUCUNE CAUSE INVENTÉE",'Ces données ne suffisent pas à expliquer chaque action du match.',2.5),
            _s('score','DEUX INDICATEURS',"À COMPARER",topic.subject,'Ils donnent deux regards différents sur la rencontre.',2.4),
            _s('verdict','DÉCRYPTAGE','LES STATS SONT LÀ',"LE CONTEXTE RESTE IMPORTANT",'Sans les séquences de jeu, on ne peut pas conclure sur les intentions tactiques.',2.5),
            _s('cta','À TON AVIS','QUELLE STAT COMPTE ?',"RÉPONDS EN COMMENTAIRE",'Laquelle de ces deux statistiques te semble la plus révélatrice ?',2.4)]
    return Draft(variant,scenes,[[a['fact_id']],[a['fact_id'],b['fact_id']],[a['fact_id']],[b['fact_id']],[a['fact_id'],b['fact_id']],[a['fact_id'],b['fact_id']],[a['fact_id'],b['fact_id']],[a['fact_id'],b['fact_id']]])


def _draft_variants(topic:Topic)->list[Draft]:
    if topic.format=='story' and topic.data.get('template')=='comeback_final':
        variants=('paradox','minutes','comeback') if 'hat_trick' in {x.id for x in topic.facts} else ('minutes','comeback')
        return [_verified_comeback(topic,v) for v in variants]
    if topic.format=='ranking':return [_ranking(topic,v) for v in ('gap','leader','list')]
    if topic.format=='comparison':return [_comparison(topic,v) for v in ('numbers','names','gap')]
    if topic.format=='portrait':return [_portrait(topic,v) for v in ('numbers','name','question')]
    if topic.format=='tactical':return [_tactical(topic,v) for v in ('contrast','focus','question')]
    # Highlights require footage rights. It has its own editing pipeline.
    raise ValueError(f'Format sans scénario narratif documenté : {topic.format}')


def _score_draft(draft:Draft,topic:Topic)->tuple[int,dict]:
    narration=draft.voice
    first=draft.scenes[0].voice
    words=len(re.findall(r"[\wÀ-ÿ]+",narration))
    hook_words=len(first.split())
    unique=len({re.sub(r'\W+','',s.voice.lower()) for s in draft.scenes})
    grounded=all(ids and all(fid in {f.id for f in topic.facts} for fid in ids) for ids in draft.evidence)
    # Suggested 80-125 French words / 35-50s at conversational rate.
    pace=12 if 65<=words<=130 else 8 if 50<=words<=150 else 0
    specificity=20 if bool(re.search(r'\d',first + ' ' + draft.scenes[0].headline)) else 10
    compact=15 if 5<=hook_words<=14 else 8 if hook_words<=20 else 0
    variation=min(13,unique*2)
    clean=12 if not any(g in first.casefold() for g in GENERIC_HOOKS) else 0
    evidence=16 if grounded else 0
    score=pace+specificity+compact+variation+clean+evidence + (12 if draft.variant=='paradox' and topic.format=='story' else (5 if draft.variant=='minutes' and topic.format=='story' else 0))
    return score,{'words':words,'hook_words':hook_words,'specificity':specificity,'pace':pace,
        'compact':compact,'variety':variation,'curiosity_bonus':(12 if draft.variant=='paradox' else 5 if draft.variant=='minutes' else 0),'no_generic_hook':bool(clean),'facts_traceable':grounded}


def review_draft(draft:Draft,topic:Topic)->list[str]:
    issues=[]
    if len(draft.scenes)<6:issues.append('Moins de six plans narratifs')
    if len(draft.evidence)!=len(draft.scenes):issues.append('Provenance plan non alignée')
    known={f.id for f in topic.facts}
    for i,refs in enumerate(draft.evidence):
        if not refs or not set(refs).issubset(known):issues.append(f'Plan {i}: références de faits invalides')
    if not draft.scenes or any(not s.voice.strip() for s in draft.scenes):issues.append('Narration absente')
    if draft.scenes and any(c in draft.scenes[0].eyebrow.casefold() or c in draft.scenes[0].headline.casefold() for c in GENERIC_HOOKS):issues.append('Accroche cliché')
    if draft.scenes and len(draft.scenes[0].voice.split())>12:issues.append('Accroche orale trop longue pour ouverture')
    sentences=[re.sub(r'\W+','',s.voice.lower()) for s in draft.scenes]
    if len(sentences)!=len(set(sentences)):issues.append('Phrase identique répétée')
    if len(draft.voice.split())>150:issues.append('Scénario trop long pour un Short')
    return issues


def choose_script(topic:Topic)->tuple[Draft,list[dict]]:
    candidates=[]
    for draft in _draft_variants(topic):
        draft.score,draft.rubric=_score_draft(draft,topic)
        issues=review_draft(draft,topic)
        if issues:draft.score=0
        candidates.append((draft,issues))
    ranked=sorted(candidates,key=lambda x:(-x[0].score,x[0].variant))
    best,issues=ranked[0]
    if issues or best.score<65:raise ValueError(f'Aucun scénario retenu : {[(d.variant,d.score,e) for d,e in ranked]}')
    return best,[{'variant':d.variant,'score':d.score,'rubric':d.rubric,'issues':issues,
                  'selected':d is best,'hook':d.scenes[0].voice} for d,issues in ranked]


def editorial_report(topic:Topic,draft:Draft,variants:list[dict],candidates:list[dict])->dict:
    return {'topic':{'id':topic.event_id,'angle':topic.angle,'format':topic.format,'date':topic.event_date,
                     'subject':topic.subject,'score':topic.score,'breakdown':topic.score_breakdown,
                     'fingerprint':topic.fingerprint,'reason':topic.reason},
            'sources':[asdict(f) for f in topic.facts],
            'selection':candidates,'script_choices':variants,
            'chosen_variant':draft.variant,'narration':draft.voice,
            'timeline':[{'kind':s.kind,'headline':s.headline,'voice':s.voice,'seconds':s.duration,
                         'fact_ids':draft.evidence[i]} for i,s in enumerate(draft.scenes)],
            'publication_allowed_by_lot2':False,
            'review_note':'Contrôle automatique des références et de l’écriture ; validation humaine de l’intérêt et des sources nécessaire.'}
