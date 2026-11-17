"""Replay 2026-11-01 with exactly the site's *indicative* pricing and V2.1 gates.

Counterfactual extension of the old V2 football catalogue. Original model
and new candidate competition happen BEFORE model pricing. Chosen market is
frozen; a rejected model quote never triggers a second-choice market.
Uses real BSD scores only to settle the selections after the decision.
"""
from __future__ import annotations
import argparse,json
from collections import Counter
from datetime import date,timedelta
from pathlib import Path
from bsd_archive import MATCHES_FILE,_read_json
from bsd_v2_core import (V2History,fit_rho_2024,fixture_datetime,estimate_goals,
                        score_matrix,predict_v2,classify_quality_category,outcome_scores)
from bsd_v2_btts import fit_btts_model
from bsd_v2_over_under import fit_total_model
from bsd_v2_double_chance import fit_model
from bsd_v2_policies import fit_policy
from bsd_v2_guardrails import V21_MIN_OVER15_CONSERVATIVE
from bsd_v2_publication_policy import eligible_model_choice
from bsd_v2_estimated_odds import DEFAULT_OVERROUND,ESTIMATED_SOURCE
from bsd_v2_market_expansion import candidates,outcome
from bsd_v2_yesterday_market_capacity import (fetch_fixtures,read_site_snapshot,
          quality_market_2025,RESEARCH_NEW_KEYS,NOT_YET_APPROVED)
from bsd_v2_published_paired_backtest import annual_market_training
from bsd_v2_market_expansion import half_time_share
from bsd_v2_indicative_replay import model_only_publication,experimental_model_prediction

def selected_new_candidates(f,index,rho,cal,validation,ht_share,quality_policy):
    feat,why=estimate_goals(f,index)
    if feat is None or quality_policy.check_fixture(feat):return []
    rows=[]
    mat=score_matrix(feat['home'],feat['away'],rho)
    for candidate in candidates(mat,home_xg=feat['home'],away_xg=feat['away'],halftime_share=ht_share):
        if candidate.key in NOT_YET_APPROVED or candidate.key not in RESEARCH_NEW_KEYS:
            continue
        valid=validation.get(candidate.key)
        if not valid or not valid.get('passes'):continue
        p=cal.score(candidate.key,candidate.probability)
        if p<.70:continue
        # The new families have an explicitly provisional uncertainty profile
        # because production has not defined per-family profiles for them yet.
        base=.010 if candidate.family=='asian_handicap' else .014
        uncertainty=base+(.018 if feat['league_samples']<30 else 0)+(
            .018 if min(feat['home_recent_matches'],feat['away_recent_matches'])<8 else 0)
        conservative=max(0.,p-uncertainty)
        quality=experimental_model_prediction(candidate,p,conservative,feat)
        if not eligible_model_choice(quality):continue
        rows.append((conservative,quality))
    rows.sort(key=lambda e:(-e[0],-e[1]['prediction']['probability'],
                             e[1]['prediction']['key']))
    return rows

def verified_scores(fixture,archive_match):
    live=outcome_scores(fixture)
    stored=outcome_scores(archive_match) if archive_match else None
    if live is not None and stored is not None and live!=stored:
        return None,'conflicting_final_scores'
    if live is not None:return live,'bsd_api'
    if stored is not None:return stored,'bsd_archive'
    return None,'missing_final_score'

def settlement(chosen,final):
    if final is None:return None
    key=chosen['key']
    from bsd_markets import candidates_from_goals,realized
    old={c.key:c for c in candidates_from_goals(1.3,1.1)}
    if key in old:return int(realized(old[key],*final))
    v=outcome(key,*final)
    return v if v in (0,1) else None

def summary(rows):
    total=len(rows);settled=[r for r in rows if r['won'] is not None]
    wins=sum(r['won'] for r in settled);n=len(settled)
    return {'selected':total,'settled':n,'won':wins,'lost':n-wins,
            'unsettled':total-n,'win_rate':round(wins/n,6) if n else None,
            'average_indicative_odds':round(sum(r['odds'] for r in rows)/total,3) if total else None,
            'average_predicted_probability':round(sum(r['probability'] for r in settled)/n,6) if n else None}

def run(day,archive,fixtures,api_source):
    index=V2History(archive)
    rho,_=fit_rho_2024(index)
    bm,_=fit_btts_model(index,rho=rho)
    tm,_=fit_total_model(index,rho=rho)
    dm,_=fit_model(index,rho=rho)
    cal,policy,_=fit_policy(index,rho=rho,btts_model=bm,total_model=tm,dc_model=dm)
    ht_share,_=half_time_share([m for _,m in index.global_games if fixture_datetime(m).year==2024])
    expcal,_=annual_market_training(index,rho,ht_share)
    validation=quality_market_2025(index,rho,expcal,ht_share)
    day_archive={str(e['id']):e for _,e in index.global_games
                 if fixture_datetime(e).date()==day}
    unique={str(e['id']):e for e in fixtures if isinstance(e,dict)
            and e.get('id') is not None and fixture_datetime(e).date()==day}
    baseline=[];expanded=[];reject_base=Counter();reject_expanded=Counter()
    decision_change=Counter();raw_new=Counter()
    comparisons=[]
    for fixture in sorted(unique.values(),key=lambda v:(v['event_date'],str(v['id']))):
        clock=fixture_datetime(fixture)-timedelta(seconds=1)
        fake={**fixture,'status':'notstarted','home_score':None,'away_score':None}
        prev,reason=predict_v2(fake,index,calibration=cal,rho=rho,clock=clock,
                                quality_policy=policy,btts_model=bm,total_model=tm,dc_model=dm,
                                excluded_keys={'12','UNDER_45'},
                                selection_conservative_minimums={
                                    'OVER_15':V21_MIN_OVER15_CONSERVATIVE})
        prev_ok=bool(prev and eligible_model_choice(prev))
        prev_priced,prev_reason=model_only_publication(prev,now=clock) if prev else (None,reason)
        if prev_priced is None:reject_base[prev_reason]+=1
        new=selected_new_candidates(fake,index,rho,expcal,validation,ht_share,policy)
        if new:raw_new['at_least_one']+=1
        # A future combined-native engine must rank before pricing.
        # Legacy first choice is retained if more reliable than new proposals,
        # including when it later fails pricing: no substitution on price.
        if new and (prev is None or new[0][0]>float(prev['prediction']['conservative_probability'])):
            selected=new[0][1];selected_type='new'
        elif prev is not None:
            selected=prev;selected_type='old'
        else:selected=None;selected_type='none'
        when=clock
        priced,why=model_only_publication(selected,now=when) if selected else (None,reason)
        if priced is None:reject_expanded[why]+=1
        else:decision_change['selected_'+selected_type]+=1
        if prev and selected and prev['prediction']['key']!=selected['prediction']['key']:
            decision_change['different_football_choice']+=1
        final,source=verified_scores(fixture,day_archive.get(str(fixture['id'])))
        def row(quote):
            return {'event_id':str(fixture['id']),'event_date':fixture['event_date'],
                    'home_team':fixture.get('home_team'),'away_team':fixture.get('away_team'),
                    'market':quote['key'],'odds':quote['odds'],
                    'odds_source':quote['odds_source'],
                    'probability':quote['probability'],
                    'conservative_probability':quote['conservative_probability'],
                    'category':quote['category'],'signal_tier':quote['tier'],
                    'won':settlement(quote,final),
                    'score':list(final) if final else None,
                    'score_source':source}
        if prev_priced:baseline.append(row(prev_priced))
        if priced:expanded.append(row(priced))
        comparisons.append({'event_id':str(fixture['id']),
                            'baseline_selection':prev['prediction']['key'] if prev else None,
                            'baseline_gate':prev_reason,
                            'combined_selection':selected['prediction']['key'] if selected else None,
                            'combined_gate':why,
                            'selected_type':selected_type,
                            'published_baseline':prev_priced is not None,
                            'published_expanded':priced is not None})
    old_ids={x['event_id'] for x in baseline}
    new_ids={x['event_id'] for x in expanded}
    added=[x for x in expanded if x['event_id'] not in old_ids]
    removed=[x for x in baseline if x['event_id'] not in new_ids]
    switched=[x for x in expanded if x['event_id'] in old_ids and
              x['market']!=next(y['market'] for y in baseline if y['event_id']==x['event_id'])]
    def market_breakdown(xs):
        keys=sorted(set(x['market'] for x in xs))
        return {key:summary([x for x in xs if x['market']==key]) for key in keys}
    result={'date':day.isoformat(),'experiment':'model-indicative-publication-v21-replay',
            'source':api_source,'matches_evaluated':len(unique),
            'odds_policy':{'source':ESTIMATED_SOURCE,'hypothetical_default_overround':DEFAULT_OVERROUND,
                           'no_historical_real_odds':True,'native_gate_functions':[
                               'eligible_model_choice','price_selected_market',
                               'post_price_value_guard','v21_accept_priced',
                               'valid_standalone_prediction']},
            'baseline':summary(baseline),'expanded':summary(expanded),
            'additional_unique_matches':summary(added),
            'removed_baseline_matches':summary(removed),
            'changed_market_on_existing_match':summary(switched),
            'new_market_families_validation':validation,
            'baseline_by_market':market_breakdown(baseline),
            'expanded_by_market':market_breakdown(expanded),
            'added_by_market':market_breakdown(added),
            'baseline_rejections':dict(reject_base),
            'expanded_rejections':dict(reject_expanded),
            'football_change':dict(decision_change),
            'new_market_opportunities_before_quotes':dict(raw_new),
            'added_rows':added,
            'baseline_rows':baseline,
            'expanded_rows':expanded,
            'fixture_comparison':comparisons,
            'limitations':[
             'Uses actual site code for estimated odds and publication gates; all actual verified bookmaker offers intentionally omitted.',
             'An indicative odds price is calculated from the prediction itself; it is not bookmaker value or achievable return.',
             'New-market confidence penalties are experimental because no production family profile exists yet.',
             'Historical prospective drift tracker and original decision-time market snapshots are not completely reconstructible.',
             'Decisions are replayed at kickoff minus one second, not exact past publication timestamps.',
             'The research experiment does not change any production feed or Telegram signal.',
             'New markets have never actually been published in production.']
            }
    assert result['baseline']['selected']==len(baseline)
    assert result['expanded']['selected']==len(expanded)
    assert result['expanded']['selected'] == result['baseline']['selected'] + len(added) - len(removed)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--date',default='2026-11-01')
    p.add_argument('--output',default='bsd/nov1_site_indicative_backtest.json')
    args=p.parse_args()
    day=date.fromisoformat(args.date)
    archive=_read_json(MATCHES_FILE,None)
    if not isinstance(archive,list) or not archive:p.error('Restore archive first')
    fixtures,source=fetch_fixtures(day,archive)
    result=run(day,archive,fixtures,source)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('BSD_SITE_INDICATIVE_REPLAY',json.dumps({
        'matches':result['matches_evaluated'],
        'baseline':result['baseline'],'expanded':result['expanded'],
        'added':result['additional_unique_matches'],
        'removed':result['removed_baseline_matches'],
        'changed_market':result['changed_market_on_existing_match'],
        'new_candidates_before_quote':result['new_market_opportunities_before_quotes'],
        'baseline_rejections':result['baseline_rejections'],
        'expanded_rejections':result['expanded_rejections']},ensure_ascii=False))

if __name__=='__main__':main()
