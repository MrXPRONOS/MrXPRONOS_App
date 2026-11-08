"""Daily ranked fixture selection, strictly prematch forecasts, and video-ready JSON.

Video payload is data, not an actual audiovisual asset or a social publication.
"""
from __future__ import annotations
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol
import json

from .daily_rank import RankedFixture, rank_fixtures, diverse_ranked
from .daily_sources import DailySourceError
from .domain import Match, iso_date, utc_datetime
from .model import fit, forecast, ModelError

class FixtureProvider(Protocol):
    name: str
    source_verified: bool
    def discover(self,target_date:date,now:datetime)->tuple[list[RankedFixture],list[str]]:...
    def history(self,fixture:RankedFixture,now:datetime)->tuple[list[Match],list[str]]:...


def _date_str(v:date)->str:
    return v.isoformat()


def _prediction(model,fixture:RankedFixture)->dict:
    prediction=forecast(model,fixture.home_id,fixture.away_id,top_n=5,
                        neutral_venue=fixture.neutral_venue is True)
    top=prediction['top_scores']
    gap=float(100*(top[0]['probability']-top[1]['probability']))
    risk=('score_presque_ex_aequo' if gap<1.0 else
          'faible_probabilite_de_score_exact' if top[0]['probability']<.15 else 'incertitude_normale')
    venue_sensitivity=None
    if fixture.stage.upper()=='FINAL' and fixture.neutral_venue is None:
        neutral=forecast(model,fixture.home_id,fixture.away_id,top_n=3,neutral_venue=True)
        venue_sensitivity={
            'venue_unverified':True,
            'home_advantage_scenario_score':top[0]['score'],
            'neutral_venue_scenario_score':neutral['top_scores'][0]['score'],
            'neutral_venue_scenario_probability':round(neutral['top_scores'][0]['probability'],6),
            'note':'Finale : lieu neutre non confirmé ; ne pas présenter un score unique comme fiable.',
        }
        risk='terrain_finale_non_confirme'
    return {
        'most_likely_score':top[0]['score'],
        'most_likely_probability':round(top[0]['probability'],6),
        'top_5':[{'score':r['score'],'probability':round(r['probability'],6)} for r in top],
        'top_score_gap_pp':round(gap,3),
        'expected_goals':{
            'home':round(prediction['expected_home_goals'],3),
            'away':round(prediction['expected_away_goals'],3)},
        'outcomes_1x2':{x:round(v,6) for x,v in prediction['one_x_two'].items()},
        'rho':round(model.rho,6),'xi':model.xi,
        'warning':risk,'venue_sensitivity':venue_sensitivity,
        'recommendation_status':'NOT_CALIBRATED_FOR_LEAGUE',
        'note':'Le score modal n’est pas une recommandation de pari; probabilité généralement faible.',
    }


def run_daily(provider:FixtureProvider, *, day:date, as_of:datetime,
              limit:int=10, min_games:int=80, min_team:int=6,
              max_staleness_days:float=21, xi:float=.0065,
              min_importance:int=105, max_candidates:int=150,
              max_per_league:int=4) -> dict:
    """Run immediately, no background work; deterministic for fixed provider and cutoff."""
    now=utc_datetime(as_of)
    if not 1<=limit<=30:raise ValueError('limit doit être entre 1 et 30')
    if min_games<40 or min_team<1:raise ValueError('Historique minimum incorrect.')
    if not 0<=xi<=.3:raise ValueError('xi non valide.')
    if not 0<max_staleness_days<=365:raise ValueError('Délai de fraîcheur non valide.')
    if day<now.date():raise ValueError('Impossible de créer des prévisions live pour une date passée.')
    if day>now.date() and (day-now.date()).days>7:
        raise ValueError('Date trop éloignée : horaires de matchs non fiables (maximum 7 jours).')
    fixtures,source_warnings=provider.discover(day,now)
    ranked=rank_fixtures(fixtures)
    if len(ranked)>max_candidates:ranked=ranked[:max_candidates]
    eligible=[];rejected=[];sources=set(); cache={}
    for f in ranked:
        if f.importance<min_importance:
            rejected.append({'id':f.id,'match':f'{f.home_name} - {f.away_name}',
                             'reason':'prestige_insuffisant','importance':f.importance})
            continue
        if f.competition not in cache:
            try:
                rows,warnings=provider.history(f,now)
                if not rows:
                    cache[f.competition]=('error','historique_absent')
                else:
                    last=max(m.kickoff for m in rows)
                    age=(now-last).total_seconds()/86400
                    if age>max_staleness_days:
                        cache[f.competition]=('error',f'resultats_perimes_depuis_{age:.1f}_jours')
                    elif len(rows)<min_games:
                        cache[f.competition]=('error',f'historique_insuffisant_{len(rows)}_matchs')
                    else:
                        fitted=fit(rows,as_of=now,xi=xi,regularization=.15,min_games=min_games,maxiter=650)
                        cache[f.competition]=('ok',fitted,rows,age,warnings)
                source_warnings.extend(warnings)
            except (ModelError,DailySourceError,ValueError) as exc:
                cache[f.competition]=('error',f'modele_ou_source_indisponible: {exc}')
        item=cache[f.competition]
        if item[0]!='ok':
            rejected.append({'id':f.id,'match':f'{f.home_name} - {f.away_name}',
                             'reason':item[1],'importance':f.importance})
            continue
        model,rows,age,_issues=item[1:]
        home_count=sum(m.home_id==f.home_id or m.away_id==f.home_id for m in rows)
        away_count=sum(m.home_id==f.away_id or m.away_id==f.away_id for m in rows)
        if min(home_count,away_count)<min_team:
            rejected.append({'id':f.id,'match':f'{f.home_name} - {f.away_name}',
                             'reason':f'equipe_historique_insuffisant_{home_count}_{away_count}',
                             'importance':f.importance})
            continue
        try:result=_prediction(model,f)
        except (ModelError,ValueError) as exc:
            rejected.append({'id':f.id,'match':f'{f.home_name} - {f.away_name}',
                             'reason':f'calcul_invalide: {exc}','importance':f.importance})
            continue
        sources.add(f.source)
        eligible.append({
            'fixture':f,'forecast':result,
            'training_n':len(rows),'training_last_result':iso_date(rows[-1].kickoff),
            'history_days_old':round(age,2),
            'teams_history':{'home':home_count,'away':away_count},
        })
    chosen_ids={f.id for f in diverse_ranked([item['fixture'] for item in eligible],
                                             limit,max_per_league=max_per_league)}
    selected=[]
    for item in eligible:
        f=item['fixture']
        if f.id not in chosen_ids:continue
        selected.append({
            'id':f.id,'competition_code':f.competition,
            'competition_name':f.competition_name,
            'stage':f.stage,'kickoff_utc':iso_date(f.kickoff),
            'home':f.home_name,'away':f.away_name,
            'importance':f.importance,
            'importance_reasons':list(f.importance_reasons),
            'source':f.source,'fixture_provider_reported':f.source_verified,
            'neutral_venue':f.neutral_venue,
            'training_matches':item['training_n'],
            'training_last_result':item['training_last_result'],
            'result_age_days':item['history_days_old'],
            'team_history':item['teams_history'],
            'model':'dixon_coles_unvalidated_cross_league',
            'forecast':item['forecast'],
            'disclaimer':'Score exact modal, aucune garantie ni conseil de mise.'
        })
    selected.sort(key=lambda r:(-r['importance'],r['kickoff_utc'],r['id']))
    complete=len(selected)==limit
    provider_reported=all(m['fixture_provider_reported'] for m in selected)
    neutral_unknown=any(x['forecast']['venue_sensitivity'] is not None for x in selected)
    eligible_for_video=complete and provider_reported and not neutral_unknown
    source_credits={
        'football-data.org': {
            'name':'football-data.org','url':'https://www.football-data.org/',
            'note':'Provider-reported schedules/results; subject to the API service terms.'},
        'openfootball/football.json': {
            'name':'OpenFootball','url':'https://github.com/openfootball/football.json',
            'license':'CC0-1.0','note':'Community-maintained fixture times; independent verification required.'},
        'openligadb.de': {
            'name':'OpenLigaDB','url':'https://openligadb.de/',
            'license':'ODbL-1.0','note':'Community-maintained match data; attribution and database licence obligations apply.'},
    }
    credits=[source_credits.get(x, {'name':x,'note':'Rights to be verified'})
             for x in sorted(sources)]
    clips=[]
    for i,m in enumerate(selected,1):
        p=m['forecast'];pct=p['most_likely_probability']*100
        clips.append({
            'order':i,'match_id':m['id'],'headline':f"{m['home']} - {m['away']}",
            'competition':m['competition_name'],'kickoff_utc':m['kickoff_utc'],
            'display_score':p['most_likely_score'],'display_probability_percent':round(pct,1),
            'narration_fr':(f"{m['home']} contre {m['away']}. D'après le modèle statistique, "
                            f"le score le plus probable est {p['most_likely_score']}, "
                            f"avec environ {pct:.1f} pour cent de probabilité. "
                            "Ce n'est pas une certitude."),
            'top_3':p['top_5'][:3],
            'warning':p['warning'],
        })
    return {
        'schema_version':1,'project':'Mr XPRONOS / Dixon-Coles independent',
        'date_local_africa_lome':_date_str(day),'generated_at_utc':iso_date(now),
        'source_mode':provider.name,'status':'READY' if eligible_for_video else
            ('PARTIAL' if selected else 'NO_ELIGIBLE_MATCHES'),
        'required_count':limit,'selected_count':len(selected),
        'count_before_quality_checks':len(fixtures),
        'eligible_count':len(eligible),'rejected_count':len(rejected),
        'ready_for_video':eligible_for_video,
        'reasons_not_ready':([] if eligible_for_video else
            ([f'Seulement {len(selected)}/{limit} matchs admissibles'] if not complete else [])+
            (['Calendrier provenant d’une source non confirmée par une API officielle'] if not provider_reported else [])+
            (['Finale : terrain neutre non vérifié'] if neutral_unknown else [])),
        'warnings':sorted(set(source_warnings))[:60],
        'sources_used':sorted(sources), 'source_credits':credits,
        'rejected':rejected[:150],'selected':selected,
        'video_payload':{
            'format':'9:16','language':'fr','platforms_planned':['YouTube Shorts','TikTok','Instagram Reels','Facebook Reels'],
            'video_title':f'10 affiches du {day.strftime("%d/%m/%Y")} — scores possibles | Mr XPRONOS',
            'video_not_generated':True,'publishing_not_configured':True,
            'footer':'18+ • Pronostics incertains • Joue responsablement',
            'source_credits':credits,
            'clips':clips,
        },
        'methodology':{
            'ranking':'league prestige + club editorial weight + documented final/round + known derbies',
            'probabilities':'Dixon-Coles weighted time-decayed Poisson, rho fitted per competition',
            'historical_xi':xi,'training_scope':'same league + same source only',
            'no_fabricated_scores':True,
            'no_per_league_calibration_claim':True,
            'future_matches_excluded_from_training':True,
            'not_a_betting_recommendation':True,
        },
    }


def save_outputs(report:dict,output:Path,video_output:Path|None=None)->None:
    output.parent.mkdir(exist_ok=True,parents=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if video_output is not None:
        video_output.parent.mkdir(exist_ok=True,parents=True)
        envelope={
            'schema_version':1,'date_local_africa_lome':report['date_local_africa_lome'],
            'ready_for_video':report['ready_for_video'],
            'status':report['status'],'selected_count':report['selected_count'],
            'source':report['source_mode'],'generated_at_utc':report['generated_at_utc'],
            **report['video_payload'],
        }
        video_output.write_text(json.dumps(envelope,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
