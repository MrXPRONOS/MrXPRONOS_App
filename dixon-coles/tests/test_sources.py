from datetime import timezone
import pytest
from dcscore.sources import parse_csv, parse_fd_matches, SourceError,download_fd_season


def test_utf8_csv():
    data='date,home_team,away_team,home_goals,away_goals,competition\n2026-01-01,Équipe A,Équipe B,0,1,PL\n2026-01-04,Équipe B,Équipe A,,,PL\n'.encode()
    matches=parse_csv(data)
    assert len(matches)==2
    assert matches[0].status=='FINISHED'
    assert matches[0].home_goals==0
    assert matches[0].competition=='csv:PL'
    assert matches[0].kickoff.tzinfo==timezone.utc
    assert matches[1].status=='SCHEDULED'


def test_common_football_csv_columns():
    body=b'Date;HomeTeam;AwayTeam;FTHG;FTAG;Div\n12/09/2024;Alpha;Beta;2;2;E0\n'
    m=parse_csv(body)[0]
    assert (m.home_goals,m.away_goals)==(2,2)
    assert m.competition=='csv:E0'


def test_csv_rejects_partial_score_and_duplicate():
    with pytest.raises(SourceError,match='Ligne 2'):
        parse_csv(b'date,home_team,away_team,home_goals,away_goals\n2026-01-01,A,B,1,\n')
    body=b'date,home_team,away_team,home_goals,away_goals\n2026-01-01,A,B,1,0\n2026-01-01,A,B,1,0\n'
    with pytest.raises(SourceError,match='dupliqu'):
        parse_csv(body)


def test_csv_no_timezone_guess():
    with pytest.raises(SourceError,match='Ligne 2'):
        parse_csv(b'date,home_team,away_team,home_goals,away_goals\n2026-01-01T18:00:00,A,B,1,0\n')


def sample_fd():
    return {"matches":[
        {"id":10,"status":"FINISHED","utcDate":"2026-01-02T17:00:00Z",
         "homeTeam":{"id":100,"name":"Home"},"awayTeam":{"id":200,"name":"Away"},
         "score":{"fullTime":{"home":0,"away":3}},"season":{"startDate":"2025-08-01"}},
        {"id":11,"status":"SCHEDULED","utcDate":"2026-12-02T17:00:00Z",
         "homeTeam":{"id":100,"name":"Home"},"awayTeam":{"id":200,"name":"Away"},
         "score":{"fullTime":{"home":None,"away":None}}},
        {"id":12,"status":"FINISHED","utcDate":"2026-01-03T17:00:00Z",
         "homeTeam":{"id":100,"name":"Home"},"awayTeam":{"id":200,"name":"Away"},
         "score":{"fullTime":{"home":None,"away":None}}}
    ]}


def test_parse_provider():
    arr=parse_fd_matches(sample_fd(),'PL')
    assert len(arr)==2
    assert arr[0].id=='fd:10'
    assert arr[0].home_id=='fd:100'
    assert arr[0].home_goals==0
    assert arr[1].status=='SCHEDULED'


class FakeResponse:
    status_code=200
    def json(self):return sample_fd()

class FakeSession:
    def get(self,endpoint,headers,params,timeout):
        assert endpoint.endswith('/v4/competitions/PL/matches')
        assert headers['X-Auth-Token']=='test-token'
        assert params['season']==2025
        return FakeResponse()


def test_api_is_mockable_without_real_network():
    arr=download_fd_season('PL',2025,token='test-token',session=FakeSession())
    assert len(arr)==2


def test_api_without_key(monkeypatch):
    monkeypatch.delenv('FOOTBALL_DATA_TOKEN',raising=False)
    with pytest.raises(SourceError,match='Clé API'):
        download_fd_season('PL',2025)


def test_stable_csv_ids_are_scoped_by_competition():
    a=parse_csv(b'date,home_team,away_team,home_goals,away_goals,competition,match_id\n2026-01-01,A,B,1,0,PL,10\n')[0]
    b=parse_csv(b'date,home_team,away_team,home_goals,away_goals,competition,match_id\n2026-01-01,A,B,1,0,BL1,10\n')[0]
    assert a.id!=b.id


def test_csv_stable_team_ids_survive_rename():
    payload=("date,home_team,away_team,home_goals,away_goals,competition,home_id,away_id\n"
             "2025-01-01,Team Alpha,Team Beta,0,0,ZZ,101,102\n"
             "2025-02-01,Alpha FC,Team Beta,1,0,ZZ,101,102\n")
    a,b=parse_csv(payload.encode())
    assert a.home_id==b.home_id
