"""Research-only daily capacity counterfactual on a specified historical BSD match date.

Never writes to the public feed or ledger. The native model is fitted on
2024-25 only; a completed historical fixture is treated as not-started and
its goals are hidden when evaluated at kickoff - one second.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

from bsd_archive import MATCHES_FILE,_read_json
from bsd_v2_core import (
 V2History,estimate_goals,score_matrix,fit_rho_2024,fixture_datetime,
 predict_v2,classify_quality_category,markets_from_matrix,outcome_scores,
)
from bsd_v2_btts import fit_btts_model
from bsd_v2_over_under import fit_total_model
from bsd_v2_double_chance import fit_model
from bsd_v2_policies import fit_policy
from bsd_v2_publication_policy import eligible_model_choice
from bsd_v2_market_expansion import candidates,half_time_share,outcome
from bsd_v2_all_markets_backtest import ExperimentalCalibrator
from bsd_v2_published_paired_backtest import annual_market_training

RESEARCH_NEW_KEYS={"HOME_OVER_05","AWAY_OVER_05","HOME_UNDER_15",
                   "AWAY_UNDER_15","AH_HOME_PLUS_15","AH_AWAY_PLUS_15"}
# DNB requires refund-aware calibration; HT only if observed period scores and a proven model.
NOT_YET_APPROVED={"DNB_HOME","DNB_AWAY","HT_UNDER_15"}

def fvalid(row):
 return isinstance(row,dict) and row.get('id') is not None and row.get('event_date') is not None

def read_site_snapshot(day):
 """Retrieve what the public feed actually contained before date rollover."""
 try:
  result=subprocess.run(["git","rev-list","-1","--before="+(day+timedelta(days=1)).isoformat()+"T00:00:00+00:00","HEAD","--","data.json"],
      capture_output=True,text=True,check=True,timeout=10)
  sha=result.stdout.strip()
  if not sha:return {"available":False,"reason":"no_commit_before_end_of_day"}
  proc=subprocess.run(["git","show",sha+":data.json"],capture_output=True,text=True,check=True,timeout=30)
  content=json.loads(proc.stdout)
  matches=[m for m in content.get('matches',[]) if str(m.get('event_date','')).startswith(day.isoformat())]
  return {"available":True,"commit":sha,"generated_at":content.get('generated_at'),
          "site_match_count":len(matches),"keys":dict(Counter((m.get('prediction') or {}).get('selection_key') for m in matches)),
          "match_ids":[str(m.get('source_event_id') or str(m.get('id','')).removeprefix('bsd:')) for m in matches]}
 except (OSError,ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
  return {"available":False,"reason":type(exc).__name__}

def fetch_fixtures(day,archive):
 matching=[m for m in archive if fvalid(m) and str(m['event_date']).startswith(day.isoformat())]
 info={"archive_candidates":len(matching),"api_attempted":False,"api_complete":False,"api_total":None}
 if not os.getenv('BSD_API_KEY'):
  return matching,info
 info["api_attempted"]=True
 try:
  from bsd_api import BSDClient
  client=BSDClient(max_requests=45)
  page=client.list_events(day,day,max_pages=40,ttl=0)
  info.update(api_complete=bool(page.complete),api_total=page.total_reported,api_fetched=len(page.events))
  if not page.complete:
   info['api_issue']="incomplete_pagination"
   return matching,info
  return page.events,info
 except (Exception,) as exc:
  info['api_issue']=type(exc).__name__+":"+str(exc)[:150]
  return matching,info

def quality_market_2025(index,rho,calibration,ht_share,*,max_validation=2500):
 stats={}
 fixtures=[event for _,event in index.global_games if fixture_datetime(event).year==2025 and fixture_datetime(event).month>=9]
 fixtures.sort(key=lambda e:(e['event_date'],str(e['id'])))
 if len(fixtures)>max_validation:
  fixtures=[fixtures[int(i*len(fixtures)/max_validation)] for i in range(max_validation)]
 from bsd_v2_market_expansion import outcome,first_half_scores
 for e in fixtures:
  feat,why=estimate_goals(e,index)
  if feat is None:continue
  mat=score_matrix(feat['home'],feat['away'],rho)
  for c in candidates(mat,home_xg=feat['home'],away_xg=feat['away'],halftime_share=ht_share):
   if c.key not in RESEARCH_NEW_KEYS:continue
   p=calibration.score(c.key,c.probability)
   actual=outcome(c.key,e['home_score'],e['away_score'],half_time=first_half_scores(e))
   row=stats.setdefault(c.key,{"n":0,"w":0,"pred":0.})
   row['n']+=1;row['w']+=int(actual);row['pred']+=p
 return {k:{"samples":v['n'],"hits":v['w'],
            "optimism_gap":round(v['pred']/v['n']-v['w']/v['n'],4),
            "passes": v['n']>=30 and v['pred']/v['n']-v['w']/v['n']<=.08}
         for k,v in stats.items() if v['n']}

def main():
 pa=argparse.ArgumentParser()
 pa.add_argument('--date',default='2026-11-01')
 pa.add_argument('--output',default='bsd/nov1_added_market_simulation.json')
 args=pa.parse_args()
 day=date.fromisoformat(args.date)
 archive=_read_json(MATCHES_FILE,None)
 if not isinstance(archive,list) or not archive:pa.error('restore encrypted archive first')
 data,source=fetch_fixtures(day,archive)
 archived_by_id={}
 for archived in archive:
  if not fvalid(archived):continue
  try:
   if fixture_datetime(archived).date()==day:
    archived_by_id[str(archived['id'])]=archived
  except (ValueError,TypeError,OverflowError):continue
 day_rows={}
 for m in data:
  if not fvalid(m):continue
  try:
   if fixture_datetime(m).date()!=day:continue
  except (ValueError,TypeError,OverflowError):continue
  day_rows[str(m['id'])]=m
 index=V2History(archive)
 rho,rho_info=fit_rho_2024(index)
 totals,totals_info=fit_total_model(index,rho=rho)
 btts,btts_info=fit_btts_model(index,rho=rho)
 dc,dc_info=fit_model(index,rho=rho)
 cal,policy,quality=fit_policy(index,rho=rho,total_model=totals,btts_model=btts,dc_model=dc)
 ht_share,ht_fit=half_time_share([e for _,e in index.global_games if fixture_datetime(e).year==2024])
 new_cal,new_training=annual_market_training(index,rho,ht_share)
 validation=quality_market_2025(index,rho,new_cal,ht_share)
 ledger=_read_json(Path('bsd/publication_ledger.json'),{})
 ledger_day=[e for e in ledger.get('entries',[]) if str(e.get('event_date','')).startswith(day.isoformat())]
 snapshot=read_site_snapshot(day)
 counted=Counter()
 new_by_key=Counter(); old_by_key=Counter()
 examples=[]; oldexamples=[]
 selection_results=[]; settlement_counts=Counter()
 for fixture in sorted(day_rows.values(),key=lambda x:(x['event_date'],str(x['id']))):
  counted['total_fixtures']+=1
  f=dict(fixture,status='notstarted',home_score=None,away_score=None)
  at=fixture_datetime(f)
  choice,reason=predict_v2(f,index,calibration=cal,rho=rho,clock=at-timedelta(seconds=1),
      quality_policy=policy,btts_model=btts,total_model=totals,dc_model=dc,
      excluded_keys={'12','UNDER_45'},
      selection_conservative_minimums={"OVER_15":.85})
  if choice is not None and eligible_model_choice(choice):
   counted['baseline_old_eligible']+=1
   old_by_key[choice['prediction']['key']]+=1
   if len(oldexamples)<8:oldexamples.append({"id":fixture['id'],"match":str(fixture.get('home_team'))+' / '+str(fixture.get('away_team')),"key":choice['prediction']['key']})
   continue
  if choice is not None:counted['old_model_below_publication_gate']+=1
  else:counted['old_model_not_qualified']+=1
  feat,why=estimate_goals(f,index)
  if feat is None:
   counted['new_no_features']+=1;continue
  bad=policy.check_fixture(feat)
  if bad:counted['new_fails_fixture_quality']+=1;continue
  mat=score_matrix(feat['home'],feat['away'],rho)
  selections=[]
  for c in candidates(mat,home_xg=feat['home'],away_xg=feat['away'],halftime_share=ht_share):
   if c.key in NOT_YET_APPROVED:
    counted['skipped_unvalidated_'+c.key]+=1
    continue
   v=validation.get(c.key)
   if not v or not v['passes']:
    counted['skipped_failed_2025_validation']+=1
    continue
   p=new_cal.score(c.key,c.probability)
   if not .79<=p<=1:continue
   family_penalty=.010 if c.family=='asian_handicap' else .014
   uncertainty=family_penalty+(0.018 if feat['league_samples']<30 else 0)+(0.018 if min(feat['home_recent_matches'],feat['away_recent_matches'])<8 else 0)
   conservative=max(0.,p-uncertainty)
   cat=classify_quality_category(conservative,feat)
   if cat not in ('pro','vip'):continue
   selections.append((conservative,p,c.key,cat))
  if selections:
   selections.sort(reverse=True)
   conservative,p,key,cat=selections[0]
   counted['additional_model_eligible']+=1
   new_by_key[key]+=1
   current_scores=outcome_scores(fixture)
   archived=archived_by_id.get(str(fixture['id']))
   archived_scores=outcome_scores(archived) if archived is not None else None
   score_source=None
   if current_scores is not None and archived_scores is not None and current_scores!=archived_scores:
    settlement_counts['conflicting_api_archive_scores']+=1
    final_scores=None
   elif current_scores is not None:
    final_scores=current_scores
    score_source='bsd_api_finished'
   elif archived_scores is not None:
    final_scores=archived_scores
    score_source='bsd_archive_finished'
   else:final_scores=None
   observed_win=None
   if final_scores is not None:
    observed_win=outcome(key,final_scores[0],final_scores[1])
    settlement_counts['settled']+=1
    settlement_counts['won' if observed_win==1 else 'lost']+=1
    settlement_counts['market_'+key+'_settled']+=1
    settlement_counts['market_'+key+('_won' if observed_win==1 else '_lost')]+=1
   else:
    settlement_counts['unsettled_or_score_conflict']+=1
    settlement_counts['market_'+key+'_unsettled']+=1
   selection_results.append({'id':str(fixture['id']),
     'kickoff':fixture['event_date'],'home':fixture.get('home_team'),'away':fixture.get('away_team'),
     'market':key,'probability':round(p,6),'conservative_probability':round(conservative,6),
     'status':'win' if observed_win==1 else 'loss' if observed_win==0 else 'unsettled',
     'score':list(final_scores) if final_scores is not None else None,'score_source':score_source})
   if len(examples)<35:examples.append({'id':fixture['id'],'date':fixture['event_date'],
      'home':fixture.get('home_team'),'away':fixture.get('away_team'),
      'market':key,'probability':round(p,4),'conservative':round(conservative,4),
      'category':cat,'prior_model_reason':reason})
  else:counted['new_none_qualified']+=1
 def ratio(wins,total):
  return round(wins/total,6) if total else None
 summary={'selected':len(selection_results),
          'settled':settlement_counts['settled'],
          'won':settlement_counts['won'],
          'lost':settlement_counts['lost'],
          'unsettled':settlement_counts['unsettled_or_score_conflict'],
          'observed_win_rate':ratio(settlement_counts['won'],settlement_counts['settled']),
          'selected_fixture_win_rate':ratio(settlement_counts['won'],len(selection_results)),
          'mean_predicted_probability_on_settled':ratio(
           sum(v['probability'] for v in selection_results if v['status']!='unsettled'),
           settlement_counts['settled']),
          'by_market':{
           k:{'selected':new_by_key[k],
              'settled':settlement_counts['market_'+k+'_settled'],
              'won':settlement_counts['market_'+k+'_won'],
              'lost':settlement_counts['market_'+k+'_lost'],
              'unsettled':settlement_counts['market_'+k+'_unsettled'],
              'win_rate':ratio(settlement_counts['market_'+k+'_won'],
                               settlement_counts['market_'+k+'_settled'])}
           for k in sorted(new_by_key)}}
 assert len(selection_results)==counted['additional_model_eligible']
 assert len(selection_results)==sum(new_by_key.values())
 assert summary['settled']+summary['unsettled']==len(selection_results)
 assert summary['won']+summary['lost']==summary['settled']
 result={'date':day.isoformat(),'simulation':'research, no-odds, before-kickoff no published claims',
  'source':source,'archive_history_count':len(index.global_games),
  'snapshot_site':snapshot,
  'first_observed_ledger_count':len(ledger_day),
  'first_observed_ledger_sources':dict(Counter((x.get('original_pick') or {}).get('odds_source') for x in ledger_day)),
  'counts':dict(counted),'baseline_market_counts':dict(old_by_key),
  'added_market_counts':dict(new_by_key),'added_examples':examples,
  'actual_outcomes':summary,'selected_fixture_outcomes':selection_results,
  'old_examples':oldexamples,
  'new_validation':validation,'new_training_games':new_training,'ht_model':ht_fit,
  'interpretation':[
    'New capacity estimate NOT equal to actual published site count: existing price/market-quote policy remains necessary.',
    'Only one primary selection per fixture; a new market on an already eligible fixture is not an additional match.',
    'No DNB or HT new picks until separately calibrated and verified.',
    'If API incomplete or unavailable, archive date coverage may be partial.',
    'First-observed ledger is not a full registry of all eligible unselected fixtures.',
    'Only historic 2024-25 data used for calibrator; historic match scores hidden from fixture predictions.',
   ]}
 output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('BSD_NOV1_ADDITIONAL_CAPACITY',json.dumps({'source':source,'counts':dict(counted),
   'existing_snapshot':snapshot.get('site_match_count'),'ledger':len(ledger_day),
   'new_markets':dict(new_by_key),'realized':summary,'validation':validation},ensure_ascii=False))

if __name__=='__main__': main()
