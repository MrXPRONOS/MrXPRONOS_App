"""Unit and integration tests for a no-hindsight model-choice guardrail."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone

import numpy as np
import pytest

from dcscore.domain import Match
from dcscore.model_selection import select_model,SelectionError
from dcscore.service import predict,backtest
from dcscore.store import Store


def pseudo_results() -> list[Match]:
    """Synthetic numbers for tests only; never used as real calibration."""
    rng=np.random.default_rng(20261106)
    start=datetime(2024,1,3,tzinfo=timezone.utc)
    results=[]
    # Six teams with balanced fixtures across multiple months.
    for day in range(590):
        if day%3:
            continue
        home=(day//3)%6
        away=(home+1+(day//3)%5)%6
        if away==home:away=(home+1)%6
        date=start+timedelta(days=day)
        results.append(Match(id=f'valid-{day}',competition='csv:VALID',kickoff=date,
            home_id=f'club-{home}',away_id=f'club-{away}',home_name=f'Club {home}',away_name=f'Club {away}',
            home_goals=int(rng.poisson(1.25)),away_goals=int(rng.poisson(1.05)),
            status='FINISHED',source='csv',season='2024/25'))
    return results


def test_score_rank_uncertainty_and_rho_effect(demo_store):
    result=backtest(demo_store,'demo:SIM',n_samples=10)
    assert result['n_evaluated']==10
    assert 'mean_poisson_same_intensities_log_loss' in result
    assert all('poisson_best_score' in m for m in result['detailed'])
    # The true separately trained Poisson should NOT be mislabeled as the
    # same-intensity baseline, since different rates were optimized.
    diffs=[abs(m['poisson_same_intensities_log_loss']-m['poisson_independent_log_loss'])
           for m in result['detailed']]
    assert max(diffs)>1e-6
    assert result['dc_top1_score_1_1_count']>=0


def test_selection_requires_completed_data_and_excludes_future():
    source=pseudo_results()
    with pytest.raises(SelectionError,match='mois entièrement terminés'):
        select_model(source,eval_start='2025-01-01',eval_end='2027-01-01')
    with pytest.raises(SelectionError,match='fictives'):
        select_model([replace(m,source='demo') for m in source],
                     eval_start='2025-01-01',eval_end='2025-08-01',min_games=50,
                     min_scored=5,min_folds=2,bootstrap_repeats=100)


def test_selection_is_based_only_on_past_validation():
    rows=pseudo_results()
    result=select_model(rows,eval_start='2025-01-01',eval_end='2025-08-01',
                        min_games=90,min_team=3,min_folds=4,min_scored=45,
                        bootstrap_repeats=250,as_of=datetime(2026,11,6,tzinfo=timezone.utc))
    assert result['selected_model'] in ('poisson','dixon_coles')
    assert result['n_scored']>=45
    assert result['n_blocks']>=4
    assert result['no_future_leakage']
    assert all(x['latest_training_result']<x['start'] for x in result['folds'])
    assert all(x['end_exclusive']<='2025-08-01T00:00:00Z' for x in result['folds'])
    assert result['ci95_paired_gain_for_dc'][0] <= result['ci95_paired_gain_for_dc'][1]


def test_store_persists_guardrail_and_auto_predict(demo_store):
    # Regression of the plumbing (test fixture, not an empirical calibration).
    fixture=demo_store.get_match('demo:tomorrow')
    r={'competition':'demo:SIM','n_scored':101,'selected_model':'poisson',
       'no_future_leakage':True,'source_signature_before_eval_end':'testsignature',
       'validation_start':'2024-01-01','validation_end_exclusive':'2024-10-01',
       'mean_dc_log_loss':2.9,'mean_poisson_log_loss':2.8,
       'ci95_paired_gain_for_dc':[-0.02,0.01],'decision':'conservative fallback'}
    ident=demo_store.save_model_selection(r)
    assert ident>=1
    assert demo_store.latest_model_selection('demo:SIM')['selected_model']=='poisson'
    result=predict(demo_store,fixture.id,save=False)
    assert result['model_selected']=='poisson'
    assert result['rho']==0.
    assert result['model_selection_calibration']['validation_n']==101
    assert result['score_1_1_probability']==pytest.approx(result['score_1_1_without_rho'])
    assert result['score_top1_gap_percentage_points']>=0
    forced=predict(demo_store,fixture.id,model_mode='dixon_coles',save=False)
    assert forced['model_selected']=='dixon_coles'
    assert forced['model_selection_calibration'] is None


def test_heldout_outcomes_cannot_change_selection():
    original=pseudo_results()
    args=dict(eval_start='2025-01-01',eval_end='2025-08-01',min_games=90,
        min_team=3,min_folds=4,min_scored=45,bootstrap_repeats=150,
        as_of=datetime(2026,11,6,tzinfo=timezone.utc))
    one=select_model(original,**args)
    altered=[replace(m,home_goals=m.home_goals+3) if m.kickoff>=datetime(2025,8,1,tzinfo=timezone.utc)
             else m for m in original]
    two=select_model(altered,**args)
    assert one['selected_model']==two['selected_model']
    assert one['mean_dc_log_loss']==two['mean_dc_log_loss']
    assert one['mean_poisson_log_loss']==two['mean_poisson_log_loss']
    assert one['source_signature_before_eval_end']==two['source_signature_before_eval_end']


def test_model_choice_api_endpoint_and_override(demo_store):
    from fastapi.testclient import TestClient
    from dcscore.api import create_app
    with TestClient(create_app(demo_store)) as client:
        unselected=client.get('/api/model-selection?competition=demo:SIM')
        assert unselected.status_code==200
        assert unselected.json()['available'] is False
        mode=client.post('/api/predict',json={'match_id':'demo:tomorrow','model_mode':'poisson'})
        assert mode.status_code==200
        assert mode.json()['model_selected']=='poisson'
        assert mode.json()['rho']==0
        bad=client.post('/api/predict',json={'match_id':'demo:tomorrow','model_mode':'secret_model'})
        assert bad.status_code==422


def test_packaged_real_selection_is_available_and_older_than_october(tmp_path):
    db=Store(str(tmp_path/'calib.sqlite'))
    r=db.latest_model_selection('of:ENG-PL')
    assert r is not None
    assert r['competition']=='of:ENG-PL' and r['n_scored']==374
    assert r['validation_end_exclusive']=='2026-06-01'
    assert r['source_names']==['openfootball/football.json']
    assert r['selected_model']=='poisson'
    assert r['ci95_paired_gain_for_dc'][0]<0<r['ci95_paired_gain_for_dc'][1]
