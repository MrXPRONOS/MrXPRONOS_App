from dataclasses import replace
from datetime import datetime,timezone,timedelta

import numpy as np
import pytest
from scipy.stats import poisson

from dcscore.model import ModelError, tau, p_score, one_x_two, fit, forecast
from dcscore.service import predict, backtest, ServiceError
from dcscore.domain import Match


def test_tau_all_four_cells():
    lam,mu,rho=1.65,0.76,-0.1
    assert tau(0,0,lam,mu,rho)==pytest.approx(1-lam*mu*rho)
    assert tau(0,1,lam,mu,rho)==pytest.approx(1+lam*rho)
    assert tau(1,0,lam,mu,rho)==pytest.approx(1+mu*rho)
    assert tau(1,1,lam,mu,rho)==pytest.approx(1-rho)
    assert tau(2,1,lam,mu,rho)==1.0


def test_probability_normalization_and_marginals():
    lam,mu,rho=1.65,0.76,-0.1
    matrix=np.array([[p_score(lam,mu,rho,i,j) for j in range(18)] for i in range(18)])
    assert matrix.sum()==pytest.approx(1,abs=1e-11)
    assert matrix.sum(axis=1)==pytest.approx(poisson.pmf(np.arange(18),lam),abs=1e-11)
    assert matrix.sum(axis=0)==pytest.approx(poisson.pmf(np.arange(18),mu),abs=1e-11)
    probabilities=one_x_two(lam,mu,rho)
    assert sum(probabilities.values())==pytest.approx(1,abs=1e-12)
    assert probabilities['home']==pytest.approx(sum(matrix[i,j] for i in range(18) for j in range(i)),abs=1e-11)
    assert probabilities['draw']==pytest.approx(np.trace(matrix),abs=1e-11)
    assert probabilities['away']==pytest.approx(sum(matrix[i,j] for j in range(18) for i in range(j)),abs=1e-11)


def test_rho_zero_equals_independent_poisson():
    assert p_score(1.2,1.1,0,1,1)==pytest.approx(poisson.pmf(1,1.2)*poisson.pmf(1,1.1))


def test_invalid_rho_rejected():
    with pytest.raises(ModelError,match='rho'):
        p_score(8,8,0.3,0,0)


def test_train_attack_normalization_and_forecast(demo_store):
    rows=demo_store.matches('demo:SIM',finished=True)
    now=datetime.now(timezone.utc)
    model=fit(rows,as_of=now)
    assert model.n_games>=200
    assert np.mean(list(model.alpha.values()))==pytest.approx(1,abs=1e-11)
    assert model.gamma>0
    assert -1<model.rho<1
    f=forecast(model,'demo:0','demo:1')
    assert f['top_scores'][0]['probability']>=f['top_scores'][1]['probability']
    assert f['probability_uncovered']<1e-6
    assert sum(f['one_x_two'].values())==pytest.approx(1,abs=1e-11)


def test_prediction_persistence(demo_store):
    p=predict(demo_store,'demo:tomorrow')
    assert p['match_id']=='demo:tomorrow'
    assert p['mode'].startswith('DEMO')
    assert p['prediction_id']
    saved=demo_store.predictions()
    assert saved[0]['actual_score'] is None
    assert saved[0]['correct'] is None


def test_strict_pre_match_only(demo_store):
    past=demo_store.matches('demo:SIM',finished=True)[-1]
    with pytest.raises(ServiceError,match='terminé'):
        predict(demo_store,past.id)
    future=demo_store.get_match('demo:tomorrow')
    with pytest.raises(ServiceError,match='déjà débuté'):
        predict(demo_store,future.id,now=future.kickoff+timedelta(minutes=2))


def test_no_future_training_leak(demo_store):
    upcoming=demo_store.get_match('demo:tomorrow')
    now=datetime.now(timezone.utc)
    fake=Match(id='demo:futurefinished',competition='demo:SIM',
               kickoff=now+timedelta(days=60),home_id='demo:0',away_id='demo:1',
               home_name='Club Fictif A',away_name='Club Fictif B',
               home_goals=10,away_goals=0,status='FINISHED',source='demo')
    count0=len(demo_store.matches('demo:SIM',before=now,finished=True))
    demo_store.upsert_matches([fake])
    count1=len(demo_store.matches('demo:SIM',before=now,finished=True))
    assert count0==count1
    p=predict(demo_store,upcoming.id,save=False)
    assert p['training']['matches']==count0


def test_backtest_strict_chronology(demo_store):
    report=backtest(demo_store,'demo:SIM',n_samples=4)
    assert report['n_evaluated']==4
    assert 0<=report['top1_hit_rate']<=1
    assert 0<=report['top3_hit_rate']<=1
    assert all(m['training_matches']>=80 for m in report['detailed'])
    assert all(m['dc_log_loss']>=0 for m in report['detailed'])


def test_insufficient_history(teststore):
    with pytest.raises(ModelError,match='Historique insuffisant'):
        fit([],as_of=datetime.now(timezone.utc))


def test_disconnected_clubs_are_rejected():
    t=datetime.now(timezone.utc)-timedelta(days=100)
    games=[]
    for i in range(12):
        pair=(('A','B') if i%2==0 else ('C','D'))
        games.append(Match(id=f'group:{i}',competition='csv:XX',kickoff=t+timedelta(days=i),
                           home_id=pair[0],away_id=pair[1],home_name=pair[0],away_name=pair[1],
                           home_goals=1,away_goals=0,status='FINISHED',source='csv'))
    with pytest.raises(ModelError,match='sans adversaires communs'):
        fit(games,as_of=datetime.now(timezone.utc),min_games=12)


def test_calendar_day_is_excluded_from_backtest(demo_store):
    r=backtest(demo_store,'demo:SIM',n_samples=3)
    for item in r['detailed']:
        cutoff=datetime.fromisoformat(item['kickoff'].replace('Z','+00:00')).date()
        used=[m for m in demo_store.matches('demo:SIM',finished=True) if m.kickoff.date()<cutoff]
        assert len(used)==item['training_matches']
