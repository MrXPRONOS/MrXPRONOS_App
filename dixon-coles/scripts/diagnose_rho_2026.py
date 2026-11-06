"""Audit out-of-time du lien rho/1-1, sans ajuster sur octobre 2026."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import math
from pathlib import Path

from dcscore.openfootball import download_openfootball_season, _team_name_id
from dcscore.model import fit, forecast, p_score, tau
from dcscore.domain import Match
from dcscore.calibration import _eligible_from_train
from backtest_october_2026 import october_matches

YEARS=('2021-22','2022-23','2023-24','2024-25','2025-26','2026-27')
CUT=datetime(2026,10,1,tzinfo=timezone.utc)
XI=0.0065
Q=(0.0,0.25,0.5,0.75,1.0)
W=(0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0)

def score_rows(dc,poi,rows):
    result=[]
    for m in rows:
        lam,mu=dc.expected_goals(m.home_id,m.away_id)
        lp,mp=poi.expected_goals(m.home_id,m.away_id)
        pfull=p_score(lam,mu,dc.rho,m.home_goals,m.away_goals)
        ppoi=p_score(lp,mp,0.0,m.home_goals,m.away_goals)
        pbase=p_score(lam,mu,0.0,m.home_goals,m.away_goals)
        ps={str(q):p_score(lam,mu,q*dc.rho,m.home_goals,m.away_goals) for q in Q}
        pw={str(w):w*pfull+(1-w)*ppoi for w in W}
        p11=p_score(lam,mu,dc.rho,1,1)
        p11_zero=p_score(lam,mu,0.,1,1)
        full=forecast(dc,m.home_id,m.away_id,top_n=1)
        zero_mode=max(((i,j,p_score(lam,mu,0.,i,j)) for i in range(5) for j in range(5)),key=lambda t:t[2]);
        result.append(dict(date=m.kickoff.date().isoformat(),match=f'{m.home_name} - {m.away_name}',score=f'{m.home_goals}-{m.away_goals}',rho=dc.rho,lam=lam,mu=mu,full=pfull,poisson=ppoi,poisson_dc_means=pbase,rho_scaled=ps,blend=pw,actual_11=int(m.home_goals==1 and m.away_goals==1),p11=p11,p11_zero=p11_zero,top1=full['top_scores'][0]['score'],top1_zero=f'{zero_mode[0]}-{zero_mode[1]}'))
    return result

def scores(rs, key):return sum(-math.log(max(r[key],1e-300)) for r in rs)/len(rs)

def main():
    ar=argparse.ArgumentParser();ar.add_argument('--csv',required=True);ar.add_argument('--output',required=True)
    args=ar.parse_args()
    hist=[];teamnames=set()
    for season in YEARS:
        rows,meta=download_openfootball_season(season,as_of=CUT)
        finished=[m for m in rows if m.status=='FINISHED' and m.kickoff<CUT]
        hist.extend(finished)
        if season=='2026-27':teamnames={m.home_name for m in finished}|{m.away_name for m in finished}
        print('SOURCE',season,len(finished),flush=True)
    hist.sort(key=lambda m:(m.kickoff,m.id));outcome,_=october_matches(Path(args.csv),teamnames)
    validation=[];blocks=[]
    for y,m in [(2025,i) for i in range(8,13)]+[(2026,i) for i in range(1,6)]:
        b=datetime(y,m,1,tzinfo=timezone.utc)
        e=datetime(y+1,1,1,tzinfo=timezone.utc) if m==12 else datetime(y,m+1,1,tzinfo=timezone.utc)
        previous=[x for x in hist if x.kickoff<b]
        targets=_eligible_from_train([x for x in hist if b<=x.kickoff<e],previous,5)
        if len(previous)<500 or not targets:continue
        dc=fit(previous,as_of=b,xi=XI,min_games=500,maxiter=450)
        poi=fit(previous,as_of=b,xi=XI,min_games=500,maxiter=450,rho_fixed=0.)
        validation+=score_rows(dc,poi,targets)
        blocks.append({'date':b.date().isoformat(),'n':len(targets),'rho':dc.rho,'gamma':dc.gamma})
        print('VAL',b.date(),len(targets),'rho',round(dc.rho,5),flush=True)
    assert len(validation)>250
    c_q=[{'rho_scale':q,'logloss':sum(-math.log(r['rho_scaled'][str(q)]) for r in validation)/len(validation)} for q in Q]
    c_w=[{'dc_weight':w,'logloss':sum(-math.log(r['blend'][str(w)]) for r in validation)/len(validation)} for w in W]
    chosen_q=min(c_q,key=lambda z:(z['logloss'],z['rho_scale']))['rho_scale']
    chosen_w=min(c_w,key=lambda z:(z['logloss'],z['dc_weight']))['dc_weight']
    dc=fit(hist,as_of=CUT,xi=XI,min_games=500,maxiter=450)
    poi=fit(hist,as_of=CUT,xi=XI,min_games=500,maxiter=450,rho_fixed=0.)
    october=score_rows(dc,poi,outcome)
    out={
      'training_n':len(hist),'validation_n':len(validation),'validation_months':blocks,
      'october_n':len(october), 'october_rho':dc.rho,'october_gamma':dc.gamma,
      'validation_dc_logloss':scores(validation,'full'),'validation_poisson_logloss':scores(validation,'poisson'),
      'validation_poisson_dc_means_logloss':scores(validation,'poisson_dc_means'),
      'rho_scale_candidates':c_q,'blend_candidates':c_w,
      'chosen_rho_scale_before_october':chosen_q,'chosen_blend_weight_before_october':chosen_w,
      'october_dc_logloss':scores(october,'full'),'october_poisson_logloss':scores(october,'poisson'),
      'october_poisson_dc_means_logloss':scores(october,'poisson_dc_means'),
      'october_scaled_rho_logloss':sum(-math.log(r['rho_scaled'][str(chosen_q)]) for r in october)/len(october),
      'october_blend_logloss':sum(-math.log(r['blend'][str(chosen_w)]) for r in october)/len(october),
      'october_top1_11_dc':sum(r['top1']=='1-1' for r in october),
      'october_top1_11_rho0':sum(r['top1_zero']=='1-1' for r in october),
      'october_actual_11':sum(r['actual_11'] for r in october),
      'october_expected_11_dc':sum(r['p11'] for r in october),
      'october_expected_11_rho0':sum(r['p11_zero'] for r in october),
      'october_p11_boost_percent':100*(sum(r['p11'] for r in october)/sum(r['p11_zero'] for r in october)-1),
      'october_match_diagnostics':october,
    }
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for k in ('training_n','validation_n','october_n','october_rho','october_gamma','validation_dc_logloss','validation_poisson_logloss','chosen_rho_scale_before_october','chosen_blend_weight_before_october','october_dc_logloss','october_poisson_logloss','october_scaled_rho_logloss','october_blend_logloss','october_top1_11_dc','october_top1_11_rho0','october_actual_11','october_expected_11_dc','october_expected_11_rho0','october_p11_boost_percent'):
        print('AUDIT',k,out[k],flush=True)
    print('CANDIDATE_RHO',c_q,flush=True)
    print('CANDIDATE_BLEND',c_w,flush=True)

if __name__=='__main__': main()
