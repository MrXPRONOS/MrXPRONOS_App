"""Offline tests use synthetic data; the GitHub workflow separately runs REAL CC0 data."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from dcscore.calibration import (CalibrationError, evaluate_xi, tune_xi,
                                 validate_candidates, holdout_evaluation)
from dcscore.domain import Match
from dcscore.model import fit
from dcscore.openfootball import parse_openfootball_season, download_openfootball_season
from dcscore.service import predict


def month_anchor(dt):
    return dt.strftime('%Y-%m-01')


def test_never_calibrate_demo_games(demo_store):
    rows=demo_store.matches('demo:SIM',finished=True)
    with pytest.raises(CalibrationError,match='fictives'):
        evaluate_xi(rows=rows,eval_start='2026-01-01',eval_end='2026-06-01',
                    min_games=12,min_scored=1,min_folds=1)


def test_candidate_validation():
    with pytest.raises(CalibrationError,match='référence'):
        validate_candidates((0.0,0.001))
    with pytest.raises(CalibrationError,match='distinctes'):
        validate_candidates((0.0065,0.0065))
    with pytest.raises(CalibrationError,match='invalides'):
        validate_candidates((0.0065,float('nan')))


def test_xi_calibration_saved_and_auto_prediction(demo_store,teststore):
    # Renamed, artificial fixture is only a unit-test substitute for imported
    # CSV; this test does NOT claim validation on actual football results.
    originals=demo_store.matches('demo:SIM',finished=True)
    rows=[replace(m,id='csv:test:'+m.id,competition='csv:UNIT',source='csv')
          for m in originals]
    teststore.upsert_matches(rows)
    starts=month_anchor(rows[108].kickoff)
    ends=month_anchor(rows[-10].kickoff)
    report=tune_xi(teststore,'csv:UNIT',eval_start=starts,eval_end=ends,
                   candidates=(0.,0.0065,0.016),block_months=2,min_games=80,
                   min_team=4,min_folds=2,min_scored=25,maxiter=350)
    assert report['n_scored']>=25
    assert report['selected_xi'] in (0.,0.0065,0.016)
    assert report['selected_mean_log_loss']<=report['historical_mean_log_loss']+1e-12
    assert all(x['n_scored']==report['n_scored'] for x in report['candidate_results'])
    assert all(f['latest_training_match'] < f['train_before'] for f in report['folds'])
    assert teststore.latest_xi_calibration('csv:UNIT')['selected_xi']==report['selected_xi']
    tomorrow=datetime.now(timezone.utc)+timedelta(days=2)
    f=Match(id='manual:test',competition='csv:UNIT',kickoff=tomorrow,
            home_id=rows[0].home_id,away_id=rows[0].away_id,
            home_name=rows[0].home_name,away_name=rows[0].away_name,source='manual')
    teststore.upsert_matches([f])
    p=predict(teststore,'manual:test',save=False)
    assert p['xi_source']=='optimized_real_data'
    assert p['xi_per_half_week']==report['selected_xi']
    assert p['xi_calibration']['validation_matches']==report['n_scored']
    override=predict(teststore,'manual:test',save=False,xi=0.002)
    assert override['xi_source']=='manual_override'
    assert override['xi_per_half_week']==0.002


def test_validation_must_be_complete_month_and_chronological(demo_store):
    rows=[replace(m,competition='csv:UNIT',source='csv')
          for m in demo_store.matches('demo:SIM',finished=True)]
    with pytest.raises(CalibrationError,match='premier jour'):
        evaluate_xi(rows=rows,eval_start='2026-01-02',eval_end='2026-05-01',
                    min_games=12,min_scored=1,min_folds=1)
    with pytest.raises(CalibrationError,match='mois entièrement terminés'):
        evaluate_xi(rows=rows,eval_start='2026-01-01',eval_end='2027-01-01',
                    min_games=12,min_scored=1,min_folds=1)


def _public_payload():
    return {'name':'English Premier League 2024/25','matches':[
        {'date':'2024-08-16','time':'20:00','team1':'Manchester United FC','team2':'Fulham FC','score':{'ft':[1,0]}},
        {'date':'2025-05-25','time':'16:00','team1':'Fulham FC','team2':'Manchester United FC','score':{'ft':[2,2]}},
        {'date':'2025-05-26','time':'16:00','team1':'Fulham FC','team2':'Leeds United FC','score':[0,0]},
        {'date':'2025-05-27','time':'16:00','team1':'Manchester United FC','team2':'Leeds United FC'},
        {'date':'2027-05-26','time':'16:00','team1':'Manchester United FC','team2':'Leeds United FC','score':{'ft':[1,1]}},
    ]}


def test_public_domain_source_parsed_timezone_and_future_gate():
    d=parse_openfootball_season(_public_payload(),'2024-25',
       as_of=datetime(2026,11,6,tzinfo=timezone.utc))
    assert len(d)==4  # Future result cannot enter history.
    assert sum(m.status=='FINISHED' for m in d)==3
    assert any(m.status=="FINISHED" and m.home_goals==m.away_goals==0 for m in d)
    assert d[0].source=='openfootball/football.json'
    assert d[0].competition=='of:ENG-PL'
    assert d[0].kickoff.isoformat()=='2024-08-16T19:00:00+00:00' # BST
    assert d[0].home_id==d[1].away_id
    assert d[3].status=='SCHEDULED'


def test_download_source_sha256_and_parse(monkeypatch):
    import hashlib
    encoded=json.dumps(_public_payload()).encode()
    class FakeResponse:
        status_code=200
        content=encoded
    class FakeSession:
        def get(self,url,**kwargs):
            assert '2024-25/en.1.json' in url
            assert kwargs['timeout']==30
            return FakeResponse()
    items,meta=download_openfootball_season('2024-25',session=FakeSession(),
       as_of=datetime(2026,11,6,tzinfo=timezone.utc))
    assert len(items)==4
    assert meta['sha256']==hashlib.sha256(encoded).hexdigest()
    assert meta['license']=='CC0-1.0'


def test_api_xi_report_and_admin_gate(teststore,monkeypatch):
    from fastapi.testclient import TestClient
    from starlette.requests import Request
    from fastapi import HTTPException
    from dcscore.api import create_app, _require_local_or_token
    with TestClient(create_app(teststore)) as c:
        resp=c.get('/api/xi/calibration',params={'competition':'of:ENG-PL'})
        assert resp.status_code==200
        assert resp.json()['available'] is True
        assert resp.json()['calibration']['selected_xi']==0.0065
        resp=c.post('/api/xi/calibrate',json={'competition':'of:ENG-PL'})
        assert resp.status_code==400
    remote=Request({'type':'http','http_version':'1.1','method':'POST',
                    'path':'/api/xi/calibrate','headers':[],'client':('8.8.8.8',12345)})
    with pytest.raises(HTTPException) as exc:
        _require_local_or_token(remote)
    assert exc.value.status_code==401
    monkeypatch.setenv('DCSCORE_ADMIN_TOKEN','dummy-password')
    remote_ok=Request({'type':'http','http_version':'1.1','method':'POST',
                       'path':'/api/xi/calibrate',
                       'headers':[(b'x-dcscore-admin-token',b'dummy-password')],
                       'client':('8.8.8.8',12345)})
    _require_local_or_token(remote_ok)
