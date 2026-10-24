import sys,unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_bsd_sportscore_2024 import (norm,goals,parse_bsd,parse_sportscore,
    merge_with_openfootball,bsd_month,score_month)

class FakeResponse:
    status_code=200
    def __init__(self,value):self.data=value;self.content=b"test"
    def json(self):return self.data

class Session:
    def __init__(self,bsd,score):self.bsd=bsd;self.score=score;self.calls=0
    def get(self,url,*,params,**kw):
        self.calls+=1
        if "bzzoiro" in url:
            n=params["offset"];return FakeResponse({
                "count":len(self.bsd),"results":self.bsd[n:n+params["limit"]]})
        return FakeResponse({"count":len(self.score),"matches":self.score})

def bsd_fixture(day="2024-01-20",home="Home",away="Away",hg=1,ag=2):
    return {"id":112,"event_date":day+"T14:00:00+00:00",
       "home_team":{"id":12,"name":home},"away_team":{"id":14,"name":away},
       "home_team_id":12,"away_team_id":14,"league_id":10,
       "home_score":hg,"away_score":ag,"status":"finished"}
def sport_fixture(day="2024-01-20",home="Home",away="Away",hg=1,ag=2):
    return {"time":day+"T14:00:00Z","home":home,"away":away,
       "competition":"League 1","home_score":hg,"away_score":ag,
       "status":"finished","url":"/football/match/home-away"}
class MultiTests(unittest.TestCase):
    def test_strict_ft_scoring_and_identity(self):
        d=date(2024,1,20)
        m=parse_bsd(bsd_fixture(),d)
        self.assertEqual(m["source"],"bsd_v2_2024")
        self.assertEqual((m["home_score"],m["away_score"]),(1,2))
        self.assertEqual(m["source_home_team_id"],12)
        self.assertEqual(m["source_date_precision"],"utc_kickoff_verified")
        self.assertIsNone(parse_bsd(bsd_fixture(day="2024-01-19"),d))
        self.assertIsNone(parse_bsd(dict(bsd_fixture(),status="live"),d))
        self.assertIsNone(parse_sportscore(dict(sport_fixture(),status="live"),d))
        self.assertEqual(parse_sportscore(sport_fixture(),d)["home_score"],1)
    def test_dedup_and_no_conflicting_score(self):
        d=date(2024,1,20)
        b=parse_bsd(bsd_fixture(),d)
        s=parse_sportscore(sport_fixture(),d)
        existing=[{"date":"2024-01-20","home_team":"Home",
                   "away_team":"Away","home_score":1,"away_score":2}]
        merged,report=merge_with_openfootball([b],[s],existing)
        self.assertEqual(len(merged),1)
        self.assertEqual(report["bsd_already_openfootball_exact"],1)
        self.assertEqual(report["sportscore_confirmed_bsd"],1)
        mismatch=parse_sportscore(sport_fixture(hg=2,ag=2),d)
        _,q=merge_with_openfootball([b],[mismatch],existing)
        self.assertEqual(q["sportscore_conflicts_or_ambiguous"],1)
    def test_bsd_page_count_closed(self):
        events=[bsd_fixture()]
        session=Session(events,[])
        accepted,audit=bsd_month(session,1,"TEST",{"total":0})
        self.assertEqual(len(accepted),1)
        self.assertEqual(audit["reported"],1)
        self.assertEqual(audit["pages"],1)
    def test_200_cap_is_not_certified_complete(self):
        import unittest.mock as mock
        items=[dict(sport_fixture(home=f"Home {i}",away=f"Away {i}"),url=f"/fixture/{i}") for i in range(200)]
        # Every simulated day has at least 200 records, requiring incomplete status.
        session=Session([],items)
        with mock.patch("single_ml_v2_bsd_sportscore_2024.time.sleep",return_value=None):
            rows,audit=score_month(session,1,{"total":0})
        self.assertEqual(audit["days_at_200_cap_incomplete"],31)
        self.assertEqual(audit["days_failed"],0)
        self.assertTrue(audit["not_complete_if_at_cap"])
if __name__=="__main__":unittest.main()
