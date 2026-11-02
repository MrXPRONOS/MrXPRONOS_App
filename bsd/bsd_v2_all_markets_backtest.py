"""All BSD V2 old/new market full-history, point-in-time and ledger consistency research."""
import argparse,json
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta
from bsd_archive import MATCHES_FILE,_read_json
from bsd_v2_core import V2History,estimate_goals,score_matrix,markets_from_matrix,fit_rho_2024,fixture_datetime,outcome_scores
from bsd_v2_over_under import fit_total_model,adjust_candidates
from bsd_v2_btts import fit_btts_model,btts_candidates
from bsd_v2_double_chance import fit_model,adjust_candidates as adjust_dc
from bsd_v2_policies import fit_policy
from bsd_markets import realized
from bsd_v2_market_expansion import ALL_KEYS,candidates,outcome,half_time_share,first_half_scores

def metrics(rows):
 n=len(rows);w=sum(y for p,y in rows);mean=sum(p for p,y in rows)/n if n else None
 return {'n':n,'wins':w,'losses':n-w,'rate':round(w/n,5) if n else None,
         'mean_probability':round(mean,5) if n else None,
         'brier':round(sum((p-y)**2 for p,y in rows)/n,6) if n else None}

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--max-matches',type=int,default=0)
 ap.add_argument('--output',default='bsd/v2_all_markets_backtest_report.json')
 ap.add_argument('--ledger',default='bsd/publication_ledger.json')
 args=ap.parse_args()
 if args.max_matches<0:ap.error('max-matches must be >=0')
 history=_read_json(MATCHES_FILE,None)
 if not isinstance(history,list) or not history:ap.error('Restore encrypted BSD archive first (BSD_HISTORY_KEY)')
 index=V2History(history)
 rho,rho_info=fit_rho_2024(index)
 tm,tm_info=fit_total_model(index,rho=rho)
 bm,bm_info=fit_btts_model(index,rho=rho)
 dm,dm_info=fit_model(index,rho=rho)
 cal,policy,policy_info=fit_policy(index,rho=rho,total_model=tm,btts_model=bm,dc_model=dm)
 ht_ratio,ht_info=half_time_share([e for _,e in index.global_games if fixture_datetime(e).year==2024])
 ledger=_read_json(Path(args.ledger),{})
 entries={str(e.get('source_event_id') or str(e.get('key','')).split('|')[0]):e
          for e in ledger.get('entries',[]) if e.get('settlement',{}).get('status')=='finished'}
 result={'version':'bsd-v2-all-markets-research-1','archive_finished':len(index.global_games),
         'protocol':'2024 training; 2025 calibration; 2026 time-held-out test',
         'full_history':args.max_matches==0,
         'training':{'rho':rho_info,'totals':tm_info,'btts':bm_info,
                     'double_chance':dm_info,'calibration':policy_info,'halftime':ht_info},
         'years':{},'ledger_reconciliation':{},'notes':[
           '2024 and 2025 rates are in-sample diagnostic only; 2026 is held-out.',
           'No historic pre-match independent odds for all markets: ROI cannot be calculated.',
           'No invented bookmaker odds, and no backfilled halftime scores.',
           'DNB draws are refunds, excluded from win/loss denominator.',
           'The published ledger records chosen markets only, not every market on every game.',
           'Replayed historic model and exact production frozen forecast are not identical.']}
 recon=Counter()
 for year in (2024,2025,2026):
  games=sorted((e for _,e in index.global_games if fixture_datetime(e).year==year),
               key=lambda e:(e['event_date'],str(e['id'])))
  if args.max_matches:games=games[:args.max_matches]
  stats=defaultdict(list);push=Counter();missing=Counter();excluded=Counter()
  for e in games:
   feat,why=estimate_goals(e,index)
   if feat is None:excluded[why]+=1;continue
   h,a=outcome_scores(e)
   matrix=score_matrix(feat['home'],feat['away'],rho)
   old=markets_from_matrix(matrix)
   old=adjust_candidates(e,index,old,tm)
   old=btts_candidates(e,index,old,bm)
   old=adjust_dc(e,index,old,dm,getattr(cal,'outcome_calibration',None))
   for c in old:
    if c.family in ('result','double_chance') and getattr(cal,'outcome_calibration',None) is not None:
     p=c.probability
    else:p=cal.score(c)[1]
    stats[c.key].append((p,realized(c,h,a)))
   for c in candidates(matrix,home_xg=feat['home'],away_xg=feat['away'],halftime_share=ht_ratio):
    y=outcome(c.key,h,a,half_time=first_half_scores(e))
    if y is None or c.probability is None:missing[c.key]+=1;continue
    if y==-1:push[c.key]+=1;continue
    p=c.probability/(1-c.refund_probability) if c.family=='dnb' else c.probability
    stats[c.key].append((p,y))
   if year==2026 and str(e['id']) in entries:
    ref=entries[str(e['id'])]
    settle=ref.get('settlement') or {}
    recon['matched_ids']+=1
    if settle.get('home_score')!=h or settle.get('away_score')!=a:
     recon['score_mismatch']+=1
    else:
     recon['score_agrees']+=1
     key=(ref.get('original_pick') or {}).get('selection_key')
     primary=next((c for c in old if c.key==key),None)
     if primary:
      recon['rechecked_settlement']+=1
      if bool(realized(primary,h,a))==settle.get('primary_won'):
       recon['settlement_agrees']+=1
      else:recon['settlement_disagrees']+=1
     else:recon['unknown_original_key']+=1
  result['years'][str(year)]={'listed_finished':len(games),'eligible':len(games)-sum(excluded.values()),
   'excluded':dict(excluded),'markets':{
    key:{**metrics(stats[key]),'refunds':push[key],'missing_outcomes_or_probabilities':missing[key],
         'status':'holdout' if year==2026 else 'in_sample'}
    for key in sorted(set(stats)|set(ALL_KEYS))}}
 result['ledger_reconciliation']=dict(recon)
 p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('BSD_ALL_MARKETS_BACKTEST',json.dumps({'years':{k:v['eligible'] for k,v in result['years'].items()},
   'ledger':dict(recon)},ensure_ascii=False))
if __name__=='__main__':main()
