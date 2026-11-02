"""All-fixture x all-market prospective diagnostic: model odds versus providers.

25 distinct outcomes for EVERY upcoming fixture, not just published Pro/VIP picks.
Historical match outcomes are used only to fit prematch models, never to
synthesize external quotes. No writes to publication ledger or site.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from statistics import median,mean

from bsd_api import BSDClient
from bsd_archive import MATCHES_FILE,_read_json
from bsd_odds_fallback import OddsRouter,ORDER,CODES,MAX_COMPARABLE_QUOTE_AGE_SECONDS,utc
from bsd_v2_odds import fetch_event_odds
from bsd_v2_core import V2History,fit_rho_2024,fixture_datetime
from bsd_v2_over_under import fit_total_model
from bsd_v2_btts import fit_btts_model
from bsd_v2_double_chance import fit_model
from bsd_v2_policies import fit_policy
from bsd_v2_all_market_price_audit import (
    CATALOG_KEYS,OLD_KEYS,fit_new_market_calibration,all_markets_for_fixture,
)
from bsd_v2_odds_comparison import valid_independent_quote,choose_upcoming,SOURCE_NAMES
from bsd_v2_market_no_vig import no_vig_probability

SUPPORTED_NATIVE_CODES=frozenset(CODES.values())

def independent_rows(client,event,captured):
    """Only a real BSD quote, preserving original updated_at and captured_at."""
    quotes,diag=fetch_event_odds(client,int(event['id']),kickoff=fixture_datetime(event),
                                 captured_at=captured,bookmaker_slug='consensus')
    for q in quotes.values():
        q['captured_at']=captured.isoformat()
        q['quote_timestamp_verified']=True
        q['quote_timestamp_type']='market_update'
    return quotes,diag

def quote_gap(model,external,market_code,captured,kickoff):
    """Price gap for every model market, including sub-1.20 research quotes."""
    valid,reason=valid_independent_quote(external,code=market_code,now=captured,kickoff=kickoff)
    if not valid:return None,reason
    price=model.get('indicative_odds')
    if type(price) not in (int,float) or price<=1.01 or price>100:
        return None,'model_price_missing'
    ext=float(external['odds'])
    delta=ext-price
    return {'model_price':price,'external_price':round(ext,4),
       'absolute_difference':round(delta,4),
       'relative_difference_pct':round(100*(ext/price-1),3),
       'abs_relative_pct':round(abs(100*(ext/price-1)),3),
       'implied_prob_model_pct':round(100/price,3),
       'implied_prob_external_pct':round(100/ext,3),
       'implied_probability_difference_points':round(100/ext-100/price,3),
       'source':external.get('origin'),
       'bookmaker':external.get('bookmaker'),
       'external_updated_at':external.get('updated_at'),
       'external_captured_at':external.get('captured_at'),
       'timestamp_type':external.get('quote_timestamp_type') or 'market_update'},'ok'

def aggregate(pairs):
    if not pairs:return {'n':0,'mean_price_delta':None,'mean_abs_price_delta':None,
                       'median_abs_price_delta':None,'median_abs_relative_pct':None,
                       'within_5pct':None,'within_10pct':None,'higher_external_pct':None}
    diffs=[q['absolute_difference'] for q in pairs]
    rel=[q['abs_relative_pct'] for q in pairs]
    n=len(pairs)
    return {'n':n,'mean_price_delta':round(mean(diffs),4),
            'mean_abs_price_delta':round(mean(abs(d) for d in diffs),4),
            'median_abs_price_delta':round(median(abs(d) for d in diffs),4),
            'median_abs_relative_pct':round(median(rel),3),
            'within_5pct':round(100*sum(x<=5 for x in rel)/n,2),
            'within_10pct':round(100*sum(x<=10 for x in rel)/n,2),
            'higher_external_pct':round(100*sum(x>0 for x in diffs)/n,2)}

def evaluate(fixtures,index,client,*,now,horizon_hours,max_fixtures,
             sources=SOURCE_NAMES):
    selected,available=choose_upcoming(fixtures,now,horizon_hours,max_fixtures)
    rho,rho_info=fit_rho_2024(index)
    totals,tm_info=fit_total_model(index,rho=rho)
    btts,bm_info=fit_btts_model(index,rho=rho)
    dc,dm_info=fit_model(index,rho=rho)
    calibration,policy,policy_info=fit_policy(index,rho=rho,total_model=totals,
                                               btts_model=btts,dc_model=dc)
    new_cal,ht_ratio,new_info=fit_new_market_calibration(index,rho)
    # One router per source, with provider endpoint cache reused across events.
    # market_code=None returns all unfiltered codes from ONE matched fixture;
    # each code is then independently vetted against its real quote timestamp.
    routers={name:OddsRouter(
                lambda event,stamp:independent_rows(client,event,stamp),
                order=(name,),clock=lambda:datetime.now(timezone.utc))
             for name in sources}
    coverage=Counter()
    rejects=Counter()
    by_market_status=defaultdict(Counter)
    pairs=[]
    market_rows=[]
    matches=[]
    for event in selected:
        if fixture_datetime(event)<=datetime.now(timezone.utc):
            coverage['started_during_scan']+=1
            continue
        coverage['fixtures_scanned']+=1
        fixture_id=str(event['id'])
        kickoff=fixture_datetime(event)
        capture=datetime.now(timezone.utc)
        predictions=all_markets_for_fixture(event,index,rho=rho,calibration=calibration,
            totals=totals,btts=btts,dc=dc,new_calibration=new_cal,ht_ratio=ht_ratio,now=capture)
        assert len(predictions)==25
        model_index={m['market_code']:m for m in predictions if m.get('market_code')}
        source_quotes={}
        source_issues={}
        for name,router in routers.items():
            coverage['source_fixture_attempts']+=1
            when=datetime.now(timezone.utc)
            if kickoff<=when:
                source_quotes[name]={};source_issues[name]='fixture_started'
                continue
            try:
                quotes,diag=router.fetch(event,when,market_code=None)
                source_quotes[name]=quotes if isinstance(quotes,dict) else {}
                if not quotes:
                    source_issues[name]='source_unavailable_or_no_matching_fixture'
                else:
                    source_issues[name]='returned_quote_data'
            except Exception as exc:
                source_quotes[name]={}
                source_issues[name]='provider_error_'+type(exc).__name__
        fixture_matched=0
        for m in predictions:
            coverage['market_observations']+=1
            key=m['key']
            code=m.get('market_code')
            row={**m,'event_id':fixture_id,'kickoff':kickoff.isoformat(),
                 'home_team':event.get('home_team'),'away_team':event.get('away_team'),
                 'league':event.get('league_name') or event.get('league'),
                 'provider_results':{}}
            if m.get('indicative_odds') is None:
                coverage['missing_model_price']+=1
                by_market_status[key]['model_price_unavailable']+=1
            else:
                coverage['model_price_available']+=1
            if code not in SUPPORTED_NATIVE_CODES:
                coverage['market_codes_without_existing_provider_adapter']+=1
                by_market_status[key]['adapter_missing']+=1
            for name in sources:
                external=source_quotes[name].get(code) if code else None
                if external is None:
                    if code not in SUPPORTED_NATIVE_CODES:
                        status='adapter_market_not_implemented'
                    else:
                        status=source_issues.get(name,'source_missing')
                        if status=='returned_quote_data':
                            status='exact_market_not_offered_or_unavailable'
                    row['provider_results'][name]={'status':status}
                    by_market_status[key][name+':'+status]+=1
                    continue
                when=utc(external.get('captured_at'))
                if when is None:
                    when=datetime.now(timezone.utc)
                gap,reason=quote_gap(m,external,code,when,kickoff)
                if gap is None:
                    row['provider_results'][name]={'status':reason}
                    by_market_status[key][name+':'+reason]+=1
                    rejects[name+':'+reason]+=1
                    continue
                coverage['valid_pairs']+=1
                fixture_matched+=1
                enriched={'event_id':fixture_id,'kickoff':kickoff.isoformat(),
                          'home_team':event.get('home_team'),'away_team':event.get('away_team'),
                          'market_key':key,'market_code':code,'family':m.get('family'),
                          'model_status':m.get('model_status'),
                          'model_pricing_method':m.get('odds_method'),
                          'model_probability':m.get('probability'),**gap,
                          'provider':name}
                adjusted,why=no_vig_probability(code,source_quotes[name],captured=when,kickoff=kickoff)
                if adjusted is not None:
                    enriched['external_no_vig_probability_pct']=round(100*adjusted['no_vig_probability'],3)
                    enriched['external_market_overround_pct']=round(100*adjusted['overround'],3)
                    enriched['model_probability_pct']=round(100*m['probability'],3) if m.get('probability') is not None else None
                    if m.get('probability') is not None:
                        enriched['no_vig_probability_gap_pp']=round(
                            100*(m['probability']-adjusted['no_vig_probability']),3)
                    coverage['pairs_with_fair_external_probability']+=1
                else:
                    enriched['no_vig_unavailable_reason']=why
                pairs.append(enriched)
                row['provider_results'][name]={'status':'compared','external_odds':gap['external_price'],
                    'difference':gap['absolute_difference'],'relative_pct':gap['relative_difference_pct'],
                    'bookmaker':gap['bookmaker'],'updated_at':gap['external_updated_at']}
                by_market_status[key][name+':compared']+=1
            market_rows.append(row)
        matches.append({'event_id':fixture_id,'kickoff':kickoff.isoformat(),
                        'home_team':event.get('home_team'),'away_team':event.get('away_team'),
                        'markets_examined':25,'valid_comparisons':fixture_matched})
        if fixture_matched:coverage['fixtures_with_at_least_one_pair']+=1
    per_market={key:{'observations':sum(1 for m in market_rows if m['key']==key),
                     'with_model_price':sum(1 for m in market_rows if m['key']==key and m.get('indicative_odds') is not None),
                     'by_source_status':dict(by_market_status[key]),
                     'comparison':aggregate([p for p in pairs if p['market_key']==key])}
                for key in CATALOG_KEYS}
    per_source={name:{'comparison':aggregate([p for p in pairs if p['provider']==name]),
                       'requests':routers[name].usage.get(name,0),
                       'source_disabled':name in routers[name].disabled,
                       'events':routers[name].events[-25:]}
                for name in sources}
    return {
       'schema':'bsd-v2-all-markets-model-vs-independent-odds-v2',
       'captured_at':now.isoformat(),
       'target':'All available upcoming fixtures x all 25 backtest markets, regardless of primary BSD V2 choice or publication thresholds',
       'period':'full_time_except_explicit_ht_under_1.5',
       'catalog':list(CATALOG_KEYS),
       'coverage':{'fixture_candidates_in_horizon':available,
                   'selected_for_scan':len(selected),
                   'truncated_due_to_max_fixtures':available>len(selected),
                   **dict(coverage),'market_rows':len(market_rows),
                   'provider_pairs':len(pairs)},
       'overall':aggregate(pairs),
       'no_vig_summary':{
           'pairs_with_complete_market':sum('no_vig_probability_gap_pp' in p for p in pairs),
           'mean_absolute_probability_gap_pp':round(
               mean(abs(p['no_vig_probability_gap_pp']) for p in pairs
                    if 'no_vig_probability_gap_pp' in p),3)
               if any('no_vig_probability_gap_pp' in p for p in pairs) else None,
       },
       'by_market':per_market,
       'by_source':per_source,
       'rejections':dict(rejects),
       'fixtures':matches,
       'market_observations':market_rows,
       'pairs':pairs,
       'model_training':{'new':new_info,'rho':rho_info,
                         'total':tm_info,'btts':bm_info,'double_chance':dm_info,
                         'policy':policy_info},
       'limitations':[
         'Every scheduled fixture receives all 25 market slots even when model data is unavailable.',
         'Only markets returned by existing provider adapters can be compared; absent adapter never means no bookmaker offers market.',
         'Diagnostic prices below site minimum odds 1.20 are observational and cannot be described as published model odds.',
         'DNB refund-aware price is experimental conditional on a non-draw and not separately calibrated.',
         'If 2024 half-time scores are absent, no first-half probability or model odds are fabricated.',
         'Raw implied probabilities include margin; no-vig probabilities are calculated only for complete same-book groups.',
         'For true predictive quality compare outcome frequencies/Brier against quoted implied probabilities after matches are finished.',
         'Supplier quotes are only contemporary snapshots; old pre-match prices cannot be reconstructed from a live endpoint.',
         'No changes to production market choice, website feed, or Telegram.',
       ]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',default='bsd/odds_all_markets_external_report.json')
    ap.add_argument('--horizon-hours',type=int,default=48)
    ap.add_argument('--max-fixtures',type=int,default=300)
    args=ap.parse_args()
    if not 1<=args.horizon_hours<=120:ap.error('horizon must be 1..120')
    if not 1<=args.max_fixtures<=2000:ap.error('max-fixtures must be 1..2000')
    history=_read_json(MATCHES_FILE,None)
    if not isinstance(history,list) or not history:ap.error('Restore encrypted archive')
    now=datetime.now(timezone.utc)
    client=BSDClient(max_requests=max(300,args.max_fixtures+60))
    end=now+timedelta(hours=args.horizon_hours)
    listing=client.list_events(now.date(),end.date(),max_pages=45,ttl=0)
    if not listing.complete:ap.error('BSD schedule incomplete: unable to audit every fixture')
    report=evaluate(listing.events,V2History(history),client,now=now,
                    horizon_hours=args.horizon_hours,max_fixtures=args.max_fixtures)
    report['collection']={'bsd_total':listing.total_reported,
                          'bsd_retrieved':len(listing.events),
                          'bsd_api_requests':client.requests_made,
                          'bsd_quota_remaining':client.rate_limit_remaining}
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('BSD_V2_ALL_MARKETS_EXTERNAL',json.dumps({
        'coverage':report['coverage'],'overall':report['overall'],
        'by_source':{s:r['comparison']['n'] for s,r in report['by_source'].items()},
        'by_market':{k:r['comparison']['n'] for k,r in report['by_market'].items()},
        'collection':report['collection']},ensure_ascii=False))
if __name__=='__main__':main()
