"""Out-of-time comparison of independently fitted Dixon-Coles versus Poisson.

This is a *guardrail*, not a post-hoc tool for forcing a desired backtest.
Only the information available before each evaluation block is used to train.
The simplest model (Poisson) is preferred unless the paired improvement from
Dixon-Coles is supported by validation evidence and a practical gain threshold.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime,timezone
from math import isfinite,log
from typing import Sequence

import numpy as np

from .calibration import _date, _add_months, _eligible_from_train, data_signature
from .domain import Match, iso_date, utc_datetime
from .model import fit, p_score, ModelError


class SelectionError(ValueError):
    pass


def select_model(rows: Sequence[Match], *, eval_start: str, eval_end: str,
                 xi: float = 0.0065, min_games: int = 400,
                 min_team: int = 5, regularization: float = 0.15,
                 block_months: int = 1, min_folds: int = 4,
                 min_scored: int = 150, min_practical_gain: float = 0.005,
                 as_of: datetime | None = None, bootstrap_repeats: int = 2500) -> dict:
    """Paired mean log-loss, block bootstrap by month, same matches/conditions.

    A positive ``poisson_loss - dc_loss`` means Dixon-Coles is better.
    A cautious fallback to Poisson is used unless the 95% month-block
    bootstrap lower bound *and* mean gain exceed the practical threshold.

    No target from evaluation months participates in either model fit.
    The calibration is finalized before evaluation of any later holdout.
    """
    now=utc_datetime(as_of or datetime.now(timezone.utc))
    start,end=_date(eval_start,'eval_start'),_date(eval_end,'eval_end')
    if not start<end or end>datetime(now.year,now.month,1,tzinfo=timezone.utc):
        raise SelectionError('Évaluation limitée à des mois entièrement terminés.')
    if not (0<=xi<=0.3) or not isfinite(xi):raise SelectionError('xi invalide.')
    if not (0<=regularization<=10) or not isfinite(regularization):
        raise SelectionError('Régularisation invalide.')
    if not 1<=block_months<=6 or min_folds<2 or min_scored<1:
        raise SelectionError('Nombre de blocs ou de matchs invalide.')
    if not 0<=min_practical_gain<=0.1 or not isfinite(min_practical_gain):
        raise SelectionError('Seuil de gain pratique invalide.')
    if not 100<=bootstrap_repeats<=10000:
        raise SelectionError('Nombre de répétitions de bootstrap invalide.')
    if not 12<=min_games<=10000 or not 1<=min_team<=100:
        raise SelectionError('Seuils historiques invalides.')
    finished=sorted((m for m in rows if m.status=='FINISHED' and m.kickoff<end),
                    key=lambda m:(m.kickoff,m.id))
    if not finished or len({m.competition for m in finished})!=1:
        raise SelectionError('Une seule compétition réelle est nécessaire.')
    if any(m.source in ('demo','manual') or m.result_provenance in
           ('synthetic_demo','manual_entry','manual_correction') for m in finished):
        raise SelectionError('Données fictives ou résultats manuels interdits à la calibration réelle.')
    if len({m.id for m in finished})!=len(finished):
        raise SelectionError('Doublons de matchs dans la période historique.')
    # The immutable provenance signature includes only results available BEFORE
    # the end of the calibration window, never the final holdout observations.
    pre_end=finished
    prior=[m for m in finished if m.kickoff<start]
    if len(prior)<min_games:
        raise SelectionError('Historique insuffisant avant la première période évaluée.')
    fold_details=[]
    all_pairs=[]
    boundary=start
    while boundary<end:
        until=min(end,_add_months(boundary,block_months))
        history=[m for m in finished if m.kickoff<boundary]
        candidate=[m for m in finished if boundary<=m.kickoff<until]
        targets=_eligible_from_train(candidate,history,min_team)
        if len(history)>=min_games and targets:
            try:
                dc=fit(history,as_of=boundary,xi=xi,min_games=min_games,
                       regularization=regularization,maxiter=450)
                poisson=fit(history,as_of=boundary,xi=xi,min_games=min_games,
                            regularization=regularization,maxiter=450,rho_fixed=0.)
            except ModelError as exc:
                raise SelectionError(f'Entraînement impossible pour le bloc {boundary.date()}: {exc}') from exc
            diffs=[]; dc_losses=[]; poisson_losses=[]
            for target in targets:
                lx,ly=dc.expected_goals(target.home_id,target.away_id,
                                        neutral_venue=target.neutral_venue)
                px,py=poisson.expected_goals(target.home_id,target.away_id,
                                            neutral_venue=target.neutral_venue)
                p_dc=p_score(lx,ly,dc.rho,target.home_goals,target.away_goals)
                p_poisson=p_score(px,py,0.,target.home_goals,target.away_goals)
                if min(p_dc,p_poisson)<=0 or not all(map(isfinite,(p_dc,p_poisson))):
                    raise SelectionError('Probabilité invalide dans la comparaison.')
                l_dc=-log(p_dc);l_poi=-log(p_poisson)
                dc_losses.append(l_dc);poisson_losses.append(l_poi)
                diffs.append(l_poi-l_dc)
                all_pairs.append((l_dc,l_poi))
            fold_details.append({'start':iso_date(boundary), 'end_exclusive':iso_date(until),
                'n_scored':len(targets),'trained_before':iso_date(boundary),
                'latest_training_result':iso_date(history[-1].kickoff),
                'mean_dc_log_loss':float(np.mean(dc_losses)),
                'mean_poisson_log_loss':float(np.mean(poisson_losses)),
                'mean_gain_for_dc':float(np.mean(diffs)),
                'paired_gains':diffs})
        boundary=until
    if len(fold_details)<min_folds or len(all_pairs)<min_scored:
        raise SelectionError(f'Validation insuffisante : {len(fold_details)} blocs, {len(all_pairs)} matchs.')
    mean_dc=float(np.mean([x[0] for x in all_pairs]))
    mean_poi=float(np.mean([x[1] for x in all_pairs]))
    gain=mean_poi-mean_dc
    # Sample *whole months* with replacement. The within-month correlation of
    # multiple outcomes is not silently treated as independent observations.
    rng=np.random.default_rng(12082026)
    n_blocks=len(fold_details)
    blocks=[np.asarray(f['paired_gains'],dtype=float) for f in fold_details]
    boot=np.empty(bootstrap_repeats,dtype=float)
    for i in range(bootstrap_repeats):
        chosen=rng.integers(0,n_blocks,size=n_blocks)
        boot[i]=float(sum(np.sum(blocks[k]) for k in chosen)/
                      sum(len(blocks[k]) for k in chosen))
    lo,hi=map(float,np.quantile(boot,[0.025,0.975]))
    selected='dixon_coles' if gain>min_practical_gain and lo>0 else 'poisson'
    # Do not persist each of the 374 individual training-match scores by default.
    clean_folds=[{k:v for k,v in f.items() if k!='paired_gains'} for f in fold_details]
    return {'schema_version':1,'competition':finished[0].competition,
            'source_names':sorted(set(m.source for m in finished)),
            'source_signature_before_eval_end':data_signature(pre_end),
            'validation_start':eval_start,'validation_end_exclusive':eval_end,
            'generated_at':iso_date(now),'xi':xi,'regularization':regularization,
            'min_games':min_games,'min_team_games':min_team,
            'n_scored':len(all_pairs),'n_blocks':len(fold_details),
            'mean_dc_log_loss':mean_dc,'mean_poisson_log_loss':mean_poi,
            'mean_gain_for_dc':gain,'ci95_paired_gain_for_dc':[lo,hi],
            'bootstrap_unit':'monthly training/test block',
            'bootstrap_repeats':bootstrap_repeats,
            'min_practical_gain':min_practical_gain,
            'selected_model':selected,
            'decision':'Choisir Dixon-Coles seulement si son gain est statistiquement défendable et supérieur au seuil utile ; sinon, modèle Poisson réentraîné séparément.',
            'no_future_leakage':True,
            'folds':clean_folds,
            'note':'Règle de prudence calibrée hors échantillon. Aucun gain sur une période future n’est garanti.'}
