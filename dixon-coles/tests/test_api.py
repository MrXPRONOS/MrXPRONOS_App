from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient

from dcscore.api import create_app


def test_health_and_static(teststore):
    with TestClient(create_app(teststore)) as c:
        r=c.get('/')
        assert r.status_code==200
        assert 'Dixon-Coles' in r.text
        assert c.get('/assets/app.js').status_code==200
        h=c.get('/api/health').json()
        assert h['ok']


def test_api_demo_predict_history_and_backtest(teststore):
    with TestClient(create_app(teststore)) as c:
        d=c.post('/api/demo').json()
        assert d['synthetic']
        ls=c.get('/api/competitions').json()
        assert ls[0]['finished']>=200
        fixtures=c.get('/api/matches',params={'competition':'demo:SIM'}).json()
        assert len(fixtures)>=1
        p=c.post('/api/predict',json={'match_id':'demo:tomorrow'}).json()
        assert 'top_scores' in p
        assert p['training']['matches']>=200
        history=c.get('/api/predictions').json()
        assert history[0]['prediction']['match_id']=='demo:tomorrow'
        bt=c.post('/api/backtest',json={'competition':'demo:SIM','n_samples':3}).json()
        assert bt['n_evaluated']==3


def test_manual_fixture_and_csv_upload(teststore):
    with TestClient(create_app(teststore)) as c:
        upload=b'date,home_team,away_team,home_goals,away_goals,competition\n2026-01-01,A,B,1,0,ZZ\n2026-01-02,B,A,0,0,ZZ\n'
        r=c.post('/api/import-csv',files={'file':('mini.csv',upload,'text/csv')})
        assert r.status_code==200,r.text
        teams=c.get('/api/teams',params={'competition':'csv:ZZ'}).json()
        kickoff=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
        res=c.post('/api/fixtures/manual',json={'competition':'csv:ZZ',
                  'home_id':teams[0]['team_id'],'away_id':teams[1]['team_id'],
                  'kickoff':kickoff})
        assert res.status_code==200,res.text
        assert res.json()['status']=='SCHEDULED'
        assert res.json()['competition']=='csv:ZZ'
        bad=c.post('/api/predict',json={'match_id':res.json()['id']})
        assert bad.status_code==400
        assert 'insuffisant' in bad.text.lower()


def test_manual_result_after_kickoff(teststore):
    from dcscore.domain import Match
    previous=datetime.now(timezone.utc)-timedelta(hours=2)
    m=Match(id='manual:test',competition='csv:ZZ',kickoff=previous,
            home_id='a',away_id='b',home_name='A',away_name='B',source='manual')
    teststore.upsert_matches([m])
    with TestClient(create_app(teststore)) as c:
        r=c.post('/api/fixtures/manual/result',json={'match_id':'manual:test','home_goals':1,'away_goals':2})
        assert r.status_code==200
        assert r.json()['status']=='FINISHED'
        assert r.json()['away_goals']==2
        assert c.post('/api/fixtures/manual/result',json={'match_id':'manual:test','home_goals':1,'away_goals':2}).status_code==400
        assert c.get('/api/matches',params={'competition':'csv:ZZ','upcoming':False}).json()[0]['home_goals']==1
