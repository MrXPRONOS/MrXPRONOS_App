from datetime import datetime, timezone, date, timedelta
from dataclasses import replace

import pytest

from dcscore.daily_sources import (
    OpenLigaDBProvider, CompositeProvider, _ol_kickoff, _ol_final_score,
    _ol_stage, DailySourceError, OPENLIGA_ROOT,
)
from dcscore.daily_rank import RankedFixture, importance

NOW=datetime(2026,11,8,17,0,tzinfo=timezone.utc)
TOMORROW=date(2026,11,9)

def match(mid,when='2026-11-09T18:30:00Z',finished=False,results=None,group='13. Spieltag'):
    return {'matchID':mid,'matchDateTimeUTC':when,'matchIsFinished':finished,
            'team1':{'teamId':1,'teamName':'FC Bayern München'},
            'team2':{'teamId':2,'teamName':'Borussia Dortmund'},
            'matchResults':results if results is not None else [],
            'group':{'groupName':group}}

class FakeHttp:
    def __init__(self,payload):
        self.payload=payload;self.calls=[]
    def get_json(self,url,**kwargs):
        self.calls.append((url,kwargs))
        assert kwargs.get('expect_list') is True
        return self.payload.get(url, [])


def test_openligadb_timestamp_timezone_and_never_fabricate():
    assert _ol_kickoff(match(1))==datetime(2026,11,9,18,30,tzinfo=timezone.utc)
    row=match(1);row['matchDateTimeUTC']=None;row['matchDateTime']='2026-11-09T19:30:00'
    assert _ol_kickoff(row)==datetime(2026,11,9,18,30,tzinfo=timezone.utc)
    row['matchDateTime']=None
    assert _ol_kickoff(row) is None


def test_openligadb_final_result_only_not_half_time_or_penalty():
    results=[
        {'resultTypeID':1,'resultName':'Halbzeit', 'pointsTeam1':0,'pointsTeam2':0},
        {'resultTypeID':2,'resultName':'Endergebnis','pointsTeam1':2,'pointsTeam2':1},
        {'resultTypeID':3,'resultName':'Elfmeterschießen','pointsTeam1':5,'pointsTeam2':4},
    ]
    assert _ol_final_score(match(10,finished=True,results=results))==(2,1)
    assert _ol_final_score(match(10,finished=False,results=results)) is None
    assert _ol_final_score(match(10,finished=True,results=[results[0]])) is None
    assert _ol_final_score(match(10,finished=True,results=[{'resultTypeID':2,'pointsTeam1':-1,'pointsTeam2':2}])) is None


def test_openliga_stages_are_not_confused():
    assert _ol_stage({'groupName':'Achtelfinale'})=='LAST_16'
    assert _ol_stage({'groupName':'Viertelfinale'})=='QUARTER_FINALS'
    assert _ol_stage({'groupName':'Halbfinale'})=='SEMI_FINALS'
    assert _ol_stage({'groupName':'Finale'})=='FINAL'
    assert _ol_stage({'groupName':'15. Spieltag'})=='REGULAR_SEASON'


def test_openliga_discovery_history_ids_separated_and_cached():
    root=f'{OPENLIGA_ROOT}/getmatchdata/bl1'
    data={
      f'{root}/2026':[match(1),match(2,'2026-11-08T11:00:00Z',True,
                                  [{'resultTypeID':2,'pointsTeam1':1,'pointsTeam2':0}])],
      f'{root}/2025':[match(3,'2025-12-10T12:00:00Z',True,
                                  [{'resultTypeID':2,'pointsTeam1':0,'pointsTeam2':0}])],
    }
    http=FakeHttp(data)
    provider=OpenLigaDBProvider(http=http,seasons_back=2,leagues=('bl1',))
    fixtures,warnings=provider.discover(TOMORROW,NOW)
    assert len(fixtures)==1 and not warnings
    f=fixtures[0]
    assert f.source=='openligadb.de' and f.competition=='OL:BL1'
    assert f.home_id=='ol:1' and f.away_id=='ol:2'
    assert not f.source_verified
    assert importance(f).importance>=117
    history,notes=provider.history(f,NOW)
    assert len(history)==2 and notes==[]
    assert history[0].home_goals==0 and history[0].away_goals==0
    assert all(m.competition=='OL:BL1' and m.status=='FINISHED' for m in history)
    assert provider.history(f,NOW)[0]==history
    assert len(http.calls)==2


def test_composite_prefers_fd_for_same_competition_without_crossmixing():
    def fixture(source,competition,id):
        return RankedFixture(id=id,competition=competition,competition_name='Bundesliga',
        kickoff=NOW+timedelta(days=1),home_id=id+'h',away_id=id+'a',
        home_name='Bayern',away_name='Dortmund',stage='REGULAR_SEASON',
        source=source,source_verified=source=='football-data.org')
    class Source:
        def __init__(self,name,fixtures):self.name=name;self.fixtures=fixtures;self.used=[]
        def discover(self,day,now):return self.fixtures,[]
        def history(self,f,now):self.used.append(f.id);return [],[]
    ol=Source('openligadb.de',[fixture('openligadb.de','OL:BL1','ol:12'),fixture('openligadb.de','OL:BL2','ol:13')])
    fd=Source('football-data.org',[fixture('football-data.org','BL1','fd:99')])
    of=Source('openfootball/football.json',[fixture('openfootball/football.json','of:de.1','of:44')])
    multi=CompositeProvider([of,ol,fd])
    matches,errors=multi.discover(TOMORROW,NOW)
    assert not errors
    assert {m.id for m in matches}=={'fd:99','ol:13'}
    assert multi.discovery_counts=={'football-data.org':1,'openligadb.de':2,'openfootball/football.json':1}
    for m in matches:multi.history(m,NOW)
    assert fd.used==['fd:99'] and ol.used==['ol:13'] and of.used==[]


def test_composite_survives_one_provider_failure():
    class Bad:
        name='bad'
        def discover(self,*args):raise DailySourceError('provider unavailable')
    class Good:
        name='openligadb.de'
        def discover(self,*args):return [],[]
    fixtures,errors=CompositeProvider([Bad(),Good()]).discover(TOMORROW,NOW)
    assert fixtures==[] and errors==['bad: provider unavailable']


def test_composite_names_unique_and_no_provider():
    with pytest.raises(ValueError):CompositeProvider([])
    with pytest.raises(ValueError):CompositeProvider([type('A',(),{'name':'dup'})(),type('B',(),{'name':'dup'})()])


def test_auto_source_selection_without_secret(monkeypatch):
    from dcscore import daily
    monkeypatch.delenv('FOOTBALL_DATA_TOKEN',raising=False)
    monkeypatch.setattr(daily,'OpenLigaDBProvider',lambda: type('OpenLiga',(),{'name':'ol','discover':lambda *a:([],[]),'history':lambda *a:([],[])})())
    monkeypatch.setattr(daily,'OpenFootballProvider',lambda: type('OpenF',(),{'name':'of','discover':lambda *a:([],[]),'history':lambda *a:([],[])})())
    # Directly verify constructed composite via injected pipeline, without network.
    used=[]
    def run(provider,**kw):
        used.extend(x.name for x in provider.providers)
        return {'status':'NO_ELIGIBLE_MATCHES','date_local_africa_lome':'2026-11-09',
                'count_before_quality_checks':0, 'source_discovery_counts':{}, 'reasons_not_ready':[],
                'selected_count':0,'required_count':10,'source_mode':provider.name,
                'ready_for_video':False,'warnings':[],'video_payload':{},'selected':[]}
    monkeypatch.setattr(daily,'run_daily',run)
    from pathlib import Path
    monkeypatch.setattr(daily,'save_outputs',lambda *args:None)
    assert daily.main(['--day','tomorrow'])==0
    assert used==['ol','of']


def test_zero_fixtures_has_explicit_reason_and_diagnostics():
    from dcscore.daily_pipeline import run_daily
    class Empty:
        name='empty'
        source_verified=False
        discovery_counts={'some_source':0}
        def discover(self,*a):return [],[]
    result=run_daily(Empty(),day=TOMORROW,as_of=NOW)
    assert result['status']=='NO_ELIGIBLE_MATCHES'
    assert not result['ready_for_video']
    assert 'Aucune rencontre' in ' '.join(result['reasons_not_ready'])
    assert result['source_discovery_counts']=={'some_source':0}
