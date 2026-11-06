"""Calibrate selective exact-score display on 2025/26, audit October 2026.

Not an ex-ante 2026 production track record: this policy was designed AFTER
October. Source results and historical model fits are nonetheless leakage-free.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from dcscore.openfootball import download_openfootball_season
from dcscore.score_signal import assess_score_signal, calibrate_score_signals
from dcscore.model import fit, forecast, p_score
from backtest_october_2026 import october_matches

OCT = datetime(2026,10,1,tzinfo=timezone.utc)
SEASONS=('2021-22','2022-23','2023-24','2024-25','2025-26','2026-27')


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--csv',required=True)
    parser.add_argument('--calibration-out',required=True)
    parser.add_argument('--holdout-out',required=True)
    args=parser.parse_args(argv)
    historical=[]
    active_names=set()
    sources=[]
    for season in SEASONS:
        rows,meta=download_openfootball_season(season,as_of=OCT)
        historical.extend(m for m in rows if m.status=='FINISHED' and m.kickoff<OCT)
        sources.append(meta)
        if season=='2026-27':
            active_names={m.home_name for m in rows}|{m.away_name for m in rows}
        print('SOURCE',season, 'HIST',sum(m.status=='FINISHED' for m in rows),flush=True)
    historical.sort(key=lambda m:(m.kickoff,m.id))
    calibration=calibrate_score_signals(historical,eval_start='2025-08-01',
        eval_end='2026-06-01',as_of=datetime.now(timezone.utc),
        xi=0.0065,min_games=500,min_team=5,min_scored=300,min_folds=8,
        confidence_quantile=0.80,min_gap_percentage_points=1.0,regularization=0.15)
    if calibration['n_scored']!=374 or calibration['n_folds']!=10:
        raise RuntimeError('La validation réelle n\'a pas été reproduite exactement.')
    target,csv_hash=october_matches(Path(args.csv),active_names)
    if len(target)!=38 or any(m.kickoff<OCT for m in target):
        raise RuntimeError('Période de test corrompue.')
    if any(m.kickoff>=OCT for m in historical):
        raise RuntimeError('Fuite temporelle depuis octobre vers la formation.')
    models={
        'dixon_coles':fit(historical,as_of=OCT,xi=0.0065,min_games=500,maxiter=450),
        'poisson':fit(historical,as_of=OCT,xi=0.0065,min_games=500,maxiter=450,rho_fixed=0.),
    }
    detail=[]
    for match in target:
        d={'date':match.kickoff.date().isoformat(),
           'match':f'{match.home_name} - {match.away_name}',
           'actual':f'{match.home_goals}-{match.away_goals}'}
        for name,model in models.items():
            prediction=forecast(model,match.home_id,match.away_id,top_n=5)
            signal=assess_score_signal(prediction,calibration,model=name)
            # This is a reporting decision, not a change in probability of the actual score.
            lam,mu=model.expected_goals(match.home_id,match.away_id)
            d[name]={
                'mode_score':prediction['top_scores'][0]['score'],
                'mode_probability':prediction['top_scores'][0]['probability'],
                'gap_pp':prediction['score_top1_gap_percentage_points'],
                'signal_status':signal['status'],
                'recommended_score':signal['recommended_score'],
                'top_three':[x['score'] for x in prediction['top_scores'][:3]],
                'top1_hit':prediction['top_scores'][0]['score']==d['actual'],
                'signal_hit':signal['recommended_score']==d['actual'] if signal['recommended_score'] else None,
                'log_loss':-__import__('math').log(max(1e-300,p_score(lam,mu,model.rho,match.home_goals,match.away_goals))),
            }
        detail.append(d)
    summary={}
    for name in models:
        reports=[r[name] for r in detail]
        accepted=[r for r in reports if r['signal_status']=='single_score']
        summary[name]={
            'mode_1_1_count':sum(r['mode_score']=='1-1' for r in reports),
            'single_score_recommendations':len(accepted),
            'abstentions':len(reports)-len(accepted),
            'recommended_1_1_count':sum(r['recommended_score']=='1-1' for r in accepted),
            'mode_top1_hits':sum(r['top1_hit'] for r in reports),
            'single_score_hits':sum(r['signal_hit'] for r in accepted),
            'conditional_hit_rate':(sum(r['signal_hit'] for r in accepted)/len(accepted)) if accepted else None,
            'mean_log_loss':sum(r['log_loss'] for r in reports)/len(reports),
        }
    report={
        'schema_version':1,'period_start':'2026-10-01','period_end_exclusive':'2026-11-01',
        'n_october':len(target),'training_matches':len(historical),
        'calibration_validation_end':'2026-06-01',
        'posthoc_disclaimer':'Le filtre a été imaginé après octobre ; ces chiffres sont un audit rétrospectif, pas des paris annoncés avant matchs.',
        'probabilities_unchanged':True,
        'training_sources':sources,'october_csv_sha256':csv_hash,
        'summary':summary,'details':detail,
    }
    for path,output in ((args.calibration_out,calibration),(args.holdout_out,report)):
        dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for name,m in summary.items():
        print('MODEL',name, 'mode11',m['mode_1_1_count'],
              'signals',m['single_score_recommendations'],
              'recommended11',m['recommended_1_1_count'],
              'selected_hits',m['single_score_hits'],
              'all_hits',m['mode_top1_hits'], 'loss',round(m['mean_log_loss'],6),flush=True)
        print('THRESHOLD',name,calibration['models'][name]['min_top_probability'],
              'VALIDATION_SIGNALS',calibration['models'][name]['n_signals'],
              'VALIDATION_TOP1_ALL',calibration['models'][name]['top1_hit_rate_all'],
              'VALIDATION_TOP1_SELECTED',calibration['models'][name]['top1_hit_rate_signals'],flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
