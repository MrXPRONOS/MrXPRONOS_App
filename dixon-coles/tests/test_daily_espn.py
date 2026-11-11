"""Offline validation of the ESPN adapter. No live requests in CI unit tests."""
from datetime import datetime, timezone, date
from dcscore.daily_espn import ESPNProvider, parse_event, _score
from dcscore.logo_policy import valid_logo_url

NOW = datetime(2026, 11, 9, 15, tzinfo=timezone.utc)


def event(*, completed=False, moment='2026-11-10T19:00:00Z', gh='0', ga='2'):
    return {'id':'12345','date':moment,
        'status':{'type':{'completed': completed, 'name':'STATUS_FINAL' if completed else 'STATUS_SCHEDULED'}},
        'competitions':[{'competitors':[
            {'homeAway':'home','team':{'id':'100','displayName':'Chelsea','logo':'https://a.espncdn.com/i/teamlogos/soccer/500/100.png'},'score':gh},
            {'homeAway':'away','team':{'id':'200','displayName':'Bayern Munich','logo':'https://a.espncdn.com/i/teamlogos/soccer/500/200.png'},'score':ga}
        ]}]}


def test_future_fixture_is_real_and_crest_is_passed():
    m, f = parse_event(event(), 'uefa.wchampions', now=NOW)
    assert m is None
    assert f.home_name == 'Chelsea' and f.away_name == 'Bayern Munich'
    assert f.home_id.startswith('espn:uefa.wchampions:')
    assert valid_logo_url(f.home_logo_url)
    assert f.source_verified is True


def test_completed_scores_no_future_leakage_including_zero():
    m, f = parse_event(event(completed=True, moment='2026-11-08T20:00:00Z'), 'uefa.wchampions', now=NOW)
    assert f is None and m.status == 'FINISHED'
    assert (m.home_goals,m.away_goals)==(0,2)
    assert m.result_provenance == 'provider_reported'
    m, f = parse_event(event(completed=True), 'uefa.wchampions', now=NOW)
    assert m is None and f is None
    m, f = parse_event(event(moment='2026-11-08T20:00:00Z'), 'uefa.wchampions', now=NOW)
    assert m is None and f is None


def test_never_interpret_missing_or_unfinished_score_as_final():
    x = event(completed=True, moment='2026-11-08T20:00:00Z',gh=None)
    assert parse_event(x,'eng.trophy',now=NOW)==(None,None)
    assert _score('0')==0 and _score('bad') is None


def test_discover_only_target_date_and_keep_completed_history():
    class Response:
        status_code=200
        content=b'{}'
        def __init__(self,items):self.items=items
        def json(self):return {'events':self.items}
    class Session:
        def get(self,url,*,params,headers,timeout):
            k=params['dates']
            if k=='20261110':return Response([event()])
            if k=='2026':return Response([event(completed=True,moment='2026-10-27T20:00:00Z')])
            return Response([])
    p=ESPNProvider(session=Session(),leagues=['uefa.wchampions'])
    games,warns=p.discover(date(2026,11,10),NOW)
    assert len(games)==1 and not warns
    history,problems=p.history(games[0],NOW)
    assert len(history)==1 and not problems
    assert len(p.history(games[0],NOW)[0])==1


def test_esports_domains_and_bad_urls_not_accepted():
    assert valid_logo_url('https://a.espncdn.com/i/teamlogos/soccer/500/500.png')
    assert not valid_logo_url('http://a.espncdn.com/i/teamlogos/soccer/500/500.png')
    assert not valid_logo_url('https://evil.espncdn.com/i/teamlogos/soccer/500/500.png')


def test_large_but_bounded_yearly_scoreboard_is_accepted_for_laliga():
    class LargeResponse:
        status_code = 200
        content = b"x" * 4_750_000
        def json(self):
            return {"events": []}
    class Session:
        def get(self, url, **kwargs):
            assert kwargs["params"]["dates"] == "2026"
            return LargeResponse()
    provider = ESPNProvider(session=Session(), leagues=["esp.1"])
    assert provider._fetch("esp.1", "2026") == []


def test_oversized_espn_json_is_rejected_without_hiding_reason():
    import pytest
    from dcscore.daily_sources import DailySourceError
    class HugeResponse:
        status_code = 200
        content = b"x" * 8_100_000
        def json(self):
            raise AssertionError("Never parse oversized JSON")
    class Session:
        def get(self, url, **kwargs):
            return HugeResponse()
    provider = ESPNProvider(session=Session(), leagues=["esp.1"])
    with pytest.raises(DailySourceError, match="trop volumineuse"):
        provider._fetch("esp.1", "2026")
