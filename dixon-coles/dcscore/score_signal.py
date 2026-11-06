"""Selective exact-score reporting: abstain, never fabricate an alternate modal score.

A 1-1 that is mathematically most probable must stay first in `top_scores`.
Only a separately calibrated *recommendation* may abstain when that mode
isn't sufficiently distinguishable or is weak by historical confidence rank.
This policy never changes the underlying probability distribution or log loss.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any

import numpy as np

from .calibration import _eligible_from_train, data_signature
from .domain import Match, iso_date, utc_datetime
from .model import fit, forecast, ModelError


class SignalCalibrationError(ValueError):
    pass


DEFAULT_CONFIDENCE_QUANTILE = 0.80  # only the historically top 20% modal probabilities
DEFAULT_MIN_GAP_PP = 1.0


def assess_score_signal(forecast_result: dict, policy: dict | None, *, model: str = 'dixon_coles') -> dict:
    """Report a standalone score only after *prior* calibration of confidence.

    `top_scores` remains unchanged for transparency. All 'abstain' cases
    retain exact-score probabilities and top three possible scores.
    """
    ranked = forecast_result.get('top_scores') or []
    if len(ranked) < 2:
        raise ValueError('Deux scores probabilisés sont requis.')
    if model not in ('dixon_coles', 'poisson'):
        raise ValueError('Mode de score invalide.')
    top = ranked[0]
    margin_pp = 100.0 * (float(ranked[0]['probability']) - float(ranked[1]['probability']))
    result = {
        'status': 'abstain',
        'recommended_score': None,
        'highest_probability_score': top['score'],
        'highest_probability': float(top['probability']),
        'gap_percentage_points': margin_pp,
        'top_three': [{'score': r['score'], 'probability': float(r['probability'])} for r in ranked[:3]],
        'policy_source': 'not_calibrated',
        'reason': 'Pas de validation chronologique du filtre de confiance pour cette compétition et ce modèle.',
    }
    if policy is None:
        return result
    thresholds = policy.get('models', {}).get(model)
    if not isinstance(thresholds, dict):
        return result
    p_min = float(thresholds['min_top_probability'])
    gap_min = float(thresholds['min_gap_percentage_points'])
    if not (0 < p_min < 1 and 0 <= gap_min <= 100 and isfinite(p_min) and isfinite(gap_min)):
        raise ValueError('Seuils historiques de signal invalides.')
    result.update({
        'min_top_probability': p_min,
        'min_gap_percentage_points': gap_min,
        'policy_source': 'historical_walk_forward',
        'validation_matches': policy.get('n_scored'),
        'confidence_quantile': policy.get('confidence_quantile'),
    })
    insufficient_prob = float(top['probability']) < p_min
    insufficient_gap = margin_pp < gap_min
    if insufficient_prob or insufficient_gap:
        reasons=[]
        if insufficient_prob:
            reasons.append('Le score le plus probable est peu convaincant au regard des matchs historiques.')
        if insufficient_gap:
            reasons.append('Le premier et le deuxième score sont trop proches.')
        result['reason'] = ' '.join(reasons) + ' Aucun score unique conseillé : garder le Top 3.'
        return result
    result['status'] = 'single_score'
    result['recommended_score'] = top['score']
    result['reason'] = 'Score distingué selon les seuils préalablement calibrés ; aucune certitude de résultat.'
    return result


def calibrate_score_signals(matches: list[Match], *, eval_start: str, eval_end: str,
                            as_of: datetime | None = None, xi: float = 0.0065,
                            min_games: int = 400, min_team: int = 5,
                            min_scored: int = 200, min_folds: int = 5,
                            confidence_quantile: float = DEFAULT_CONFIDENCE_QUANTILE,
                            min_gap_percentage_points: float = DEFAULT_MIN_GAP_PP,
                            regularization: float = 0.15, maxiter: int = 450) -> dict:
    """Quantile gate calibrated out of time using *only* previously completed seasons.

    The quantile is fixed *before* observing evaluated results. This is a
    selectivity/ranking policy, not an optimization of realized hit rate.
    The report includes realized hit rates to avoid implying an increase.
    """
    from .calibration import _add_months

    start = datetime.strptime(eval_start, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    end = datetime.strptime(eval_end, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    now = utc_datetime(as_of or datetime.now(timezone.utc))
    if not (start < end <= now):
        raise SignalCalibrationError('Valider seulement des mois historiques entièrement terminés.')
    if not (0.5 <= confidence_quantile <= 0.98):
        raise SignalCalibrationError('Quantile attendu entre 50 % et 98 %.')
    if not (0 <= min_gap_percentage_points <= 10):
        raise SignalCalibrationError('Écart minimum entre 0 et 10 points de probabilité.')
    if not (0 <= xi <= 0.3 and 0 <= regularization <= 10):
        raise SignalCalibrationError('Paramètres statistiques invalides.')
    finished = sorted((m for m in matches if m.status == 'FINISHED' and m.kickoff < end),
                      key=lambda m: (m.kickoff, m.id))
    if not finished or len({m.competition for m in finished}) != 1:
        raise SignalCalibrationError('Une seule compétition de matchs terminés est requise.')
    if any(m.source in ('demo','manual') or m.result_provenance in
           ('synthetic_demo','manual_entry','manual_correction') for m in finished):
        raise SignalCalibrationError('Les matchs fictifs ou les scores manuels sont exclus des calibrations réelles.')
    if len({m.id for m in finished}) != len(finished):
        raise SignalCalibrationError('Doublons de rencontres : annuler la calibration.')
    if sum(m.kickoff < start for m in finished) < min_games:
        raise SignalCalibrationError('Historique insuffisant avant la première période de validation.')
    samples = {'dixon_coles':[], 'poisson':[]}
    folds = []
    boundary = start
    while boundary < end:
        until = min(end, _add_months(boundary, 1))
        history = [m for m in finished if m.kickoff < boundary]
        candidates = [m for m in finished if boundary <= m.kickoff < until]
        eligible = _eligible_from_train(candidates, history, min_team)
        if len(history) >= min_games and eligible:
            try:
                models={
                    'dixon_coles':fit(history,as_of=boundary,xi=xi,regularization=regularization,
                                      min_games=min_games,maxiter=maxiter),
                    'poisson':fit(history,as_of=boundary,xi=xi,regularization=regularization,
                                  min_games=min_games,maxiter=maxiter,rho_fixed=0.),
                }
            except ModelError as exc:
                raise SignalCalibrationError(f'Impossible de calibrer le mois {boundary}: {exc}') from exc
            for m in eligible:
                for model_name, model in models.items():
                    pred = forecast(model,m.home_id,m.away_id,top_n=3,neutral_venue=m.neutral_venue)
                    samples[model_name].append({
                        'p':pred['top_scores'][0]['probability'],
                        'gap_pp':pred['score_top1_gap_percentage_points'],
                        'score':pred['top_scores'][0]['score'],
                        'actual':f'{m.home_goals}-{m.away_goals}',
                    })
            folds.append({
                'start':iso_date(boundary), 'end_exclusive':iso_date(until),
                'n_matches':len(eligible),
                'last_training_match':iso_date(history[-1].kickoff),
            })
        boundary = until
    if len(folds) < min_folds or len(samples['poisson']) < min_scored:
        raise SignalCalibrationError('Validation historique trop courte pour définir un seuil de recommandation.')
    model_rules={}
    for model_name, rows in samples.items():
        probs=np.asarray([r['p'] for r in rows])
        threshold=float(np.quantile(probs,confidence_quantile))
        accepted=[r for r in rows if r['p'] >= threshold and r['gap_pp'] >= min_gap_percentage_points]
        model_rules[model_name]={
            'min_top_probability':threshold,
            'min_gap_percentage_points':float(min_gap_percentage_points),
            'n_eligible':len(rows),
            'n_signals':len(accepted),
            'coverage':len(accepted)/len(rows),
            'top1_hit_rate_all':sum(r['score']==r['actual'] for r in rows)/len(rows),
            'top1_hit_rate_signals':sum(r['score']==r['actual'] for r in accepted)/len(accepted) if accepted else None,
            'one_one_mode_all':sum(r['score']=='1-1' for r in rows),
            'one_one_recommended':sum(r['score']=='1-1' for r in accepted),
        }
    return {
        'schema_version':1, 'competition':finished[0].competition,
        'source_names':sorted({m.source for m in finished}),
        'source_signature_before_eval_end':data_signature(finished),
        'validation_start':eval_start, 'validation_end_exclusive':eval_end,
        'generated_at':iso_date(now),
        'no_future_leakage':True,
        'n_scored':len(samples['poisson']), 'n_folds':len(folds),
        'confidence_quantile':float(confidence_quantile),
        'models':model_rules, 'folds':folds,
        'decision':'Filtre de confiance : uniquement le quintile supérieur des modes historiques et écart >= 1 point. Sinon aucune recommandation unique ; Top 3 inchangé.',
        'limitations':'Aucune amélioration de précision garantie. Le filtre diminue le nombre de recommandations, ne change pas les probabilités ni la log loss.',
    }
