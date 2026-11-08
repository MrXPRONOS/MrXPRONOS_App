from __future__ import annotations
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json

import pytest

from dcscore.daily_rank import RankedFixture,rank_fixtures,diverse_ranked,importance
from dcscore.daily_sources import (_open_result,_open_kickoff,DailySourceError,
                                   FootballDataProvider,OpenFootballProvider,HttpClient)
from dcscore.daily_pipeline import run_daily,save_outputs
from dcscore.daily import resolve_day
from dcscore.domain import Match

NOW=datetime(2026,11,8,17,25,tzinfo=timezone.utc)
TARGET=date(2026,11,9)
TEAMS=['Liverpool FC','Arsenal FC','Chelsea FC','Manchester United FC','Manchester City FC','Tottenham Hotspur FC']

def fixture(i=0,league='PL',verified=True,home=None,away=None,stage='REGULAR_SEASON'):
    return RankedFixture(id=f'{league}:{i}',competition=league,competition_name='Premier League',
        kickoff=NOW+timedelta(days=1,hours=i%4),home_id=home or TEAMS[i%6],
        away_id=away or TEAMS[(i+2)%6],home_name=home or TEAMS[i%6],
        away_name=away or TEAMS[(i+2)%6],stage=stage,
        source='football-data.org' if verified else 'openfootball/football.json',
        source_verified=verified,
        home_logo_url='https://crests.football-data.org/57.png',
        away_logo_url='https://crests.football-data.org/61.png')

def training(n=126,days_old=1):
    rows=[]
    for k in range(n):
        home=TEAMS[k%6];away=TEAMS[(k%6+1+k//6%4)%6]
        if home==away:away=TEAMS[(k+1)%6]
        rows.append(Match(id=f'dummy:{k}',competition='fd:PL',
            kickoff=NOW-timedelta(days=(n-k)+days_old),home_id=home,away_id=away,
            home_name=home,away_name=away,status='FINISHED',
            home_goals=(k*3)%4,away_goals=(k*7+1)%3,source='csv'))
    return rows

class DummyProvider:
    def __init__(self,fixtures,rows=None,verified=True):
        self.fixtures=fixtures
        self.rows=training() if rows is None else rows
        self.source_verified=verified
        self.name='test-dummy'
        self.history_calls=[]
    def discover(self,day,now):
        assert day==TARGET
        return self.fixtures,[]
    def history(self,fixture,now):
        assert now==NOW
        self.history_calls.append(fixture.competition)
        return self.rows,[]

def test_final_and_big_club_ranking():
    plain=importance(fixture(1,home='Club X',away='Club Y'))
    derby=importance(fixture(2,home='Real Madrid CF',away='FC Barcelona',stage='FINAL',league='PD'))
    assert derby.importance>plain.importance+225
    assert 'derby_reconnu=75' in derby.importance_reasons
    assert 'tour_final=225' in derby.importance_reasons
    assert rank_fixtures([plain,derby])[0].id==derby.id

def test_diversity_does_not_lose_ranking_when_few_leagues():
    fixtures=[fixture(i) for i in range(8)]
    picked=diverse_ranked(fixtures,limit=6,max_per_league=2)
    assert len(picked)==6
    assert len({x.id for x in picked})==6

def test_complete_ten_with_stable_scores_and_separate_source(tmp_path):
    f=[fixture(i) for i in range(12)]
    provider=DummyProvider(f)
    report=run_daily(provider,day=TARGET,as_of=NOW,limit=10)
    assert report['status']=='READY'
    assert report['selected_count']==10
    assert report['ready_for_video'] is True
    assert report['eligible_count']==12
    assert len(provider.history_calls)==1, 'Fit history fetched once per competition'
    assert len({x['id'] for x in report['selected']})==10
    for item in report['selected']:
        assert item['training_matches']==126
        assert 0<item['forecast']['most_likely_probability']<1
        assert len(item['forecast']['top_5'])==5
        assert item['forecast']['top_5'][0]['probability']>=item['forecast']['top_5'][1]['probability']
        assert item['forecast']['recommendation_status']=='NOT_CALIBRATED_FOR_LEAGUE'
        assert 0.99999<sum(item['forecast']['outcomes_1x2'].values())<1.00001
    full=tmp_path/'full.json';vid=tmp_path/'video.json'
    save_outputs(report,full,vid)
    d=json.loads(vid.read_text())
    assert d['ready_for_video'] and len(d['clips'])==10
    assert d['video_not_generated'] is True and d['publishing_not_configured'] is True
    assert all('certitude' in clip['narration_fr'] for clip in d['clips'])

def test_fallback_cannot_publish_uncorroborated_fixture():
    f=[fixture(i,verified=False) for i in range(11)]
    report=run_daily(DummyProvider(f,verified=False),day=TARGET,as_of=NOW,limit=10)
    assert report['selected_count']==10
    assert report['status']=='PARTIAL'
    assert report['ready_for_video'] is False
    assert 'non confirmée' in ' '.join(report['reasons_not_ready'])

def test_below_ten_no_invented_matches():
    report=run_daily(DummyProvider([fixture(i) for i in range(3)]),day=TARGET,as_of=NOW)
    assert report['selected_count']==3
    assert report['status']=='PARTIAL'
    assert len(report['video_payload']['clips'])==3


def test_stale_history_excluded():
    report=run_daily(DummyProvider([fixture(1)],training(days_old=60)),day=TARGET,as_of=NOW)
    assert report['selected_count']==0
    assert report['status']=='NO_ELIGIBLE_MATCHES'
    assert report['rejected'][0]['reason'].startswith('resultats_perimes')


def test_unseen_team_cannot_be_scored():
    f=[fixture(0,home='Totally Unknown FC')]
    report=run_daily(DummyProvider(f),day=TARGET,as_of=NOW)
    assert report['selected_count']==0
    assert report['rejected'][0]['reason'].startswith('equipe_historique_insuffisant')


def test_only_prematch_and_no_past_days():
    with pytest.raises(ValueError):
        run_daily(DummyProvider([]),day=date(2026,11,7),as_of=NOW)
    with pytest.raises(ValueError):
        run_daily(DummyProvider([]),day=date(2026,12,1),as_of=NOW)


def test_open_result_genuine_zero_zero():
    assert _open_result({'score':[0,0]})==(0,0)
    assert _open_result({'score':{'ft':[0,0]}})==(0,0)
    assert _open_result({'score':{}}) is None
    assert _open_result({'score':[]}) is None
    assert _open_result({'score':{'ft':[-1,2]}}) is None


def test_lome_local_date_handling():
    assert resolve_day('tomorrow',NOW)==TARGET
    assert resolve_day('today',NOW)==NOW.date()
    with pytest.raises(ValueError):resolve_day('bad-date',NOW)

class MockResponse:
    status_code=200
    headers={}
    content=b'{"matches":[]}'
    def json(self):return {'matches':[]}
class MockSession:
    def __init__(self):self.calls=[]
    def get(self,url,**kw):
        self.calls.append((url,kw))
        return MockResponse()

def test_no_token_must_not_use_official_provider(monkeypatch):
    monkeypatch.delenv('FOOTBALL_DATA_TOKEN',raising=False)
    with pytest.raises(DailySourceError,match='manquant'):
        FootballDataProvider()

def test_official_api_request_uses_authenticated_header_and_strict_day():
    session=MockSession()
    client=HttpClient(session=session,min_api_spacing=0)
    provider=FootballDataProvider(token='TEST_NON_SECRET',http=client)
    fixtures,warnings=provider.discover(TARGET,NOW)
    assert fixtures==[] and warnings==[]
    url,kwargs=session.calls[0]
    assert url.endswith('/matches')
    assert kwargs['params']['dateFrom']=='2026-11-08'
    assert kwargs['headers']['X-Auth-Token']=='TEST_NON_SECRET'


def test_openfootball_future_fixture_without_time_not_invented():
    assert _open_kickoff({'date':'2026-11-09'},'Europe/London') is None
    assert _open_kickoff({'date':'2026-11-09','time':'15:00'},'Europe/London') is not None

def test_final_neutrality_unknown_requires_human_check():
    f=[fixture(i,stage='FINAL') for i in range(10)]
    provider=DummyProvider(f)
    r=run_daily(provider,day=TARGET,as_of=NOW,limit=10)
    assert r['selected_count']==10
    assert r['ready_for_video'] is False
    assert any('terrain neutre' in s.lower() for s in r['reasons_not_ready'])
    assert all(x['forecast']['venue_sensitivity'] is not None for x in r['selected'])


def test_ten_matches_without_real_crests_must_not_generate_video():
    from dataclasses import replace
    rows=[replace(fixture(i),home_logo_url=None) for i in range(10)]
    result=run_daily(DummyProvider(rows),day=TARGET,as_of=NOW,limit=10)
    assert result['selected_count']==10
    assert result['ready_for_video'] is False
    assert result['status']=='PARTIAL'
    assert 'Logos' in ' '.join(result['reasons_not_ready'])
    assert all(c['home_logo_url'] is None for c in result['video_payload']['clips'])


def test_provider_forwards_two_real_crest_urls():
    from dcscore.daily_sources import FootballDataProvider
    payload={'matches':[{'id':100,'status':'TIMED','utcDate':'2026-11-09T16:00:00Z',
               'homeTeam':{'id':57,'name':'Arsenal FC','crest':'https://crests.football-data.org/57.png'},
               'awayTeam':{'id':61,'name':'Chelsea FC','crest':'https://crests.football-data.org/61.png'},
               'competition':{'code':'PL','name':'Premier League'},'stage':'REGULAR_SEASON'}]}
    class Mock:
        def get_json(self,*args,**kwargs):return payload
    matches,_=FootballDataProvider(token='TEST',http=Mock()).discover(TARGET,NOW)
    assert len(matches)==1
    assert matches[0].home_logo_url=='https://crests.football-data.org/57.png'
    assert matches[0].away_logo_url=='https://crests.football-data.org/61.png'
