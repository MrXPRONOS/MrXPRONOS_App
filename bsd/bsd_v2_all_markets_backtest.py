"""All BSD V2 old/new market full-history, point-in-time and ledger consistency research."""
import argparse,json
from pathlib import Path
from collections import defaultdict,Counter
from datetime import timedelta
from math import sqrt
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
 chosen=[(p,y) for p,y in rows if p>=.79]
 cn=len(chosen);cw=sum(y for p,y in chosen)
 def wilson(wins,count):
  if not count:return None
  z=1.95996398454;p=wins/count;den=1+z*z/count
  center=(p+z*z/(2*count))/den
  half=z*sqrt((p*(1-p)+z*z/(4*count))/count)/den
  return [round(center-half,5),round(center+half,5)]
 return {'n':n,'wins':w,'losses':n-w,'rate':round(w/n,5) if n else None,
         'mean_probability':round(mean,5) if n else None,
         'calibration_gap':round(mean-w/n,5) if n else None,
         'brier':round(sum((p-y)**2 for p,y in rows)/n,6) if n else None,
         'wilson95':wilson(w,n),
         'predicted_at_least_79pct':{'n':cn,'wins':cw,'rate':round(cw/cn,5) if cn else None,
                                      'wilson95':wilson(cw,cn)}}

class ExperimentalCalibrator:
 """2025 Jan-Aug market-by-bin shrinkage; no 2026 model fitting."""
 def __init__(self,strength=75):
  self.bins=defaultdict(lambda:[0,0]);self.strength=strength
 @staticmethod
 def bucket(p):return min(19,int(p*20))
 def observe(self,key,p,y):
  if p is None or y not in (0,1) or key.startswith('DNB_'):return
  val=self.bins[(key,self.bucket(p))];val[0]+=1;val[1]+=y
 def score(self,key,p):
  if p is None or key.startswith('DNB_'):return p
  n,w=self.bins.get((key,self.bucket(p)),(0,0))
  return (self.strength*p+w)/(self.strength+n)
 def sizes(self):
  out=Counter()
  for (key,_),(n,_) in self.bins.items():out[key]+=n
  return dict(out)

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
 experiment=ExperimentalCalibrator()
 new_train=0
 for _,e in index.global_games:
  dt=fixture_datetime(e)
  if dt.year!=2025 or dt.month>8:continue
  feat,why=estimate_goals(e,index)
  if feat is None:continue
  matrix=score_matrix(feat['home'],feat['away'],rho)
  scored=outcome_scores(e)
  for option in candidates(matrix,home_xg=feat['home'],away_xg=feat['away'],halftime_share=ht_ratio):
   y=outcome(option.key,*scored,half_time=first_half_scores(e))
   experiment.observe(option.key,option.probability,y)
  new_train+=1
 ledger=_read_json(Path(args.ledger),{})
 entries={str(e.get('source_event_id') or str(e.get('key','')).split('|')[0]):e
          for e in ledger.get('entries',[]) if e.get('settlement',{}).get('status')=='finished'}
 result={'version':'bsd-v2-all-markets-research-1','archive_finished':len(index.global_games),
         'protocol':'2024 training; 2025 calibration; 2026 time-held-out test',
         'full_history':args.max_matches==0,
         'training':{'rho':rho_info,'totals':tm_info,'btts':bm_info,
                     'double_chance':dm_info,'calibration':policy_info,'halftime':ht_info,'new_market_training_samples':new_train,'new_market_calibration_samples':experiment.sizes()},
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
    calibrated=experiment.score(c.key,c.probability)
    p=calibrated/(1-c.refund_probability) if c.family=='dnb' else calibrated
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
     archived_p=(ref.get('original_pick') or {}).get('confidence')
     if primary is not None and isinstance(archived_p,(float,int)):
      current_p=primary.probability if primary.family in ('result','double_chance') else cal.score(primary)[1]
      recon['replay_probability_comparisons']+=1
      recon['replay_absolute_probability_difference_sum']+=abs(current_p-float(archived_p))
  result['years'][str(year)]={'listed_finished':len(games),'eligible':len(games)-sum(excluded.values()),'sampling':'complete' if not args.max_matches else 'truncated',
   'excluded':dict(excluded),'markets':{
    key:{**metrics(stats[key]),'refunds':push[key],'missing_outcomes_or_probabilities':missing[key],
         'status':'holdout' if year==2026 else 'in_sample'}
    for key in sorted(set(stats)|set(ALL_KEYS))}}
 if recon['replay_probability_comparisons']:
  recon['replay_probability_mean_absolute_error']=round(recon['replay_absolute_probability_difference_sum']/recon['replay_probability_comparisons'],5)
 result['ledger_reconciliation']=dict(recon)
 p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print('BSD_ALL_MARKETS_BACKTEST',json.dumps({'years':{k:v['eligible'] for k,v in result['years'].items()},
   'ledger':dict(recon)},ensure_ascii=False))
if __name__=='__main__':main()
