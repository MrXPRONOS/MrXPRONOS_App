"""Regression tests: no forced alternatives, selective display, historical calibration."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from dcscore.domain import Match
from dcscore.score_signal import assess_score_signal, calibrate_score_signals, SignalCalibrationError
from dcscore.service import predict


def sample_forecast(score='1-1', p=0.12, runner=0.113):
    return {'top_scores': [
        {'score':score, 'home':1,'away':1,'probability':p},
        {'score':'2-1','home':2,'away':1,'probability':runner},
        {'score':'1-0','home':1,'away':0,'probability':0.09},
    ]}


def policy():
    return {'competition':'demo:SIM', 'validation_start':'2024-01-01',
            'validation_end_exclusive':'2025-07-01',
            'generated_at':'2025-07-02T00:00:00Z','n_scored':180,
            'confidence_quantile':0.80,'models':{
                'poisson': {'min_top_probability':0.15,'min_gap_percentage_points':1.0},
                'dixon_coles': {'min_top_probability':0.155,'min_gap_percentage_points':1.0},
            }}


def test_repetitive_1_1_is_not_falsely_replaced():
    original=sample_forecast()
    before=[dict(x) for x in original['top_scores']]
    decision=assess_score_signal(original,policy(),model='poisson')
    assert decision['status']=='abstain'
    assert decision['recommended_score'] is None
    assert decision['highest_probability_score']=='1-1'
    assert decision['top_three'][0]['score']=='1-1'
    assert original['top_scores']==before  # probabilities and mathematical mode never changed


def test_high_confidence_candidate_is_permitted_even_for_1_1():
    decision=assess_score_signal(sample_forecast(p=0.18,runner=0.155),policy(),model='poisson')
    assert decision['status']=='single_score'
    assert decision['recommended_score']=='1-1'
    assert decision['highest_probability']==0.18


def test_ambiguity_margin_rejects_even_high_probability():
    decision=assess_score_signal(sample_forecast(p=0.18,runner=0.177),policy(),model='poisson')
    assert decision['status']=='abstain'
    assert decision['recommended_score'] is None
    assert decision['gap_percentage_points']==pytest.approx(0.3)


def test_unknown_competition_abstains_without_invented_threshold():
    decision=assess_score_signal(sample_forecast(p=0.22,runner=0.12),None,model='poisson')
    assert decision['status']=='abstain'
    assert decision['policy_source']=='not_calibrated'


def test_sqlite_policy_migration_and_predict(demo_store):
    match=demo_store.get_match('demo:tomorrow')
    pred=predict(demo_store,match.id,save=True)
    assert pred['exact_score_signal']['status']=='abstain'
    assert pred['top_scores'][0]['score']==pred['exact_score_signal']['highest_probability_score']
    r=policy()
    r.update({'source_signature_before_eval_end':'fake_test_only','no_future_leakage':True})
    ident=demo_store.save_score_signal_calibration(r)
    assert ident>=1
    saved=demo_store.latest_score_signal_calibration('demo:SIM')
    assert saved['models']==r['models']
    pred=predict(demo_store,match.id,save=False)
    assert pred['exact_score_signal']['policy_source']=='historical_walk_forward'
    rows=demo_store.predictions()
    assert rows and rows[0]['recommended_score'] is None
    assert rows[0]['signal_correct'] is None


def test_future_policy_is_rejected(demo_store):
    r=policy()
    r.update({'source_signature_before_eval_end':'fake_test_only','no_future_leakage':True,
              'validation_end_exclusive':'2099-06-01'})
    demo_store.save_score_signal_calibration(r)
    with pytest.raises(ValueError,match='futur'):
        predict(demo_store,'demo:tomorrow',save=False)


def pseudo_results() -> list[Match]:
    rng=np.random.default_rng(20261106)
    start=datetime(2024,1,3,tzinfo=timezone.utc)
    result=[]
    for step in range(198):
        home=step%6; away=(home+1+(step//6)%5)%6
        dt=start+timedelta(days=step*3)
        result.append(Match(id=f'pseudoselect-{step}',competition='csv:TEST',kickoff=dt,
            home_id=f'club-{home}',away_id=f'club-{away}',
            home_name=f'Club {home}',away_name=f'Club {away}',
            home_goals=int(rng.poisson(1.45)),away_goals=int(rng.poisson(1.10)),
            status='FINISHED',source='csv',season='2024/25'))
    return result


def test_real_calibration_filters_future_and_fictitious_outcomes():
    rows=pseudo_results()
    kwargs=dict(eval_start='2025-01-01',eval_end='2025-08-01',
        as_of=datetime(2026,11,6,tzinfo=timezone.utc),min_games=90,
        min_team=3,min_scored=45,min_folds=3,maxiter=250)
    report=calibrate_score_signals(rows,**kwargs)
    assert report['n_scored']>=45 and report['n_folds']>=3
    assert report['no_future_leakage'] is True
    assert all(f['last_training_match']<f['start'] for f in report['folds'])
    assert all(f['end_exclusive']<='2025-08-01T00:00:00Z' for f in report['folds'])
    assert all(0 < report['models'][m]['min_top_probability'] < 1 for m in ('poisson','dixon_coles'))
    assert all(report['models'][m]['n_signals']<=report['models'][m]['n_eligible'] for m in ('poisson','dixon_coles'))
    # changing matches AFTER the window never changes the pre-window policy.
    altered=[replace(m,home_goals=m.home_goals+2) if m.kickoff>=datetime(2025,8,1,tzinfo=timezone.utc)
             else m for m in rows]
    second=calibrate_score_signals(altered,**kwargs)
    assert report['models']==second['models']
    assert report['source_signature_before_eval_end']==second['source_signature_before_eval_end']
    with pytest.raises(SignalCalibrationError,match='fictifs'):
        calibrate_score_signals([replace(m,source='demo') for m in rows],**kwargs)


def test_calibration_api_requires_real_data(demo_store):
    from fastapi.testclient import TestClient
    from dcscore.api import create_app
    with TestClient(create_app(demo_store)) as client:
        resp=client.get('/api/score-signal/calibration?competition=demo:SIM')
        assert resp.status_code==200 and resp.json()['available'] is False
        bad=client.post('/api/score-signal/calibrate',json={
            'competition':'demo:SIM','eval_start':'2025-01-01','eval_end':'2025-08-01'})
        assert bad.status_code==400


def test_validated_real_threshold_is_packaged_and_from_before_october(tmp_path):
    from dcscore.store import Store
    r=Store(str(tmp_path/'fresh.sqlite')).latest_score_signal_calibration('of:ENG-PL')
    assert r is not None
    assert r['validation_start']=='2025-08-01'
    assert r['validation_end_exclusive']=='2026-06-01'
    assert r['n_scored']==374
    assert r['no_future_leakage']
    assert r['models']['poisson']['min_top_probability']==pytest.approx(0.12747374667029648)
    assert r['models']['dixon_coles']['min_top_probability']==pytest.approx(0.13063660854654618)
    assert r['source_names']==['openfootball/football.json']
