"""Retrospective coverage must not expose the final score to V5 selection."""
from datetime import date, datetime, timezone

from dcscore.backtest_two_pass_v5 import RetrospectiveESPN
from dcscore.daily_espn import CANDIDATES


def test_retrospective_extra_fixture_truth_is_separate_and_not_visible():
    kickoff="2026-10-10T18:00:00Z"
    event={
        "id":"888123","date":kickoff,
        "status":{"type":{"completed":True,"name":"STATUS_FINAL"}},
        "competitions":[{"competitors":[
            {"homeAway":"home","score":"5",
             "team":{"id":"5001","displayName":"North Club",
                     "logo":"https://a.espncdn.com/i/teamlogos/soccer/500/5001.png"}},
            {"homeAway":"away","score":"0",
             "team":{"id":"5002","displayName":"South Club",
                     "logo":"https://a.espncdn.com/i/teamlogos/soccer/500/5002.png"}},
        ]}],
    }
    class Response:
        status_code=200
        content=b'{}'
        def __init__(self,items):self.items=items
        def json(self):return {"events":self.items}
    class Session:
        def get(self,url,*,params,headers,timeout):
            return Response([event] if '/eng.2/' in url and
                            params["dates"]=="20261010" else [])
    provider=RetrospectiveESPN(session=Session())
    provider.fallback_leagues=("eng.2",)
    fixtures,errors=provider.discover_more(
        date(2026,10,10),datetime(2026,10,9,20,tzinfo=timezone.utc))
    assert errors==[] and len(fixtures)==1
    assert fixtures[0].source_verified and fixtures[0].id.endswith("888123")
    assert provider.truth[fixtures[0].id]==(5,0)
    assert fixtures[0].competition=="ES:ENG.2"
    assert 'eng.2' in CANDIDATES
    assert 'eng.2' in provider._secondary_enabled
