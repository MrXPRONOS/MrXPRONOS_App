import unittest
from datetime import datetime,timezone
from scripts.football_authorized_h2h_collector import collect

NOW=datetime(2026,10,14,9,tzinfo=timezone.utc)
RIGHTS={"sportscore":{"approved":True,"historical_model_use":True,
                      "commercial_product":True,"attribution_compliant":True,
                      "legal_basis":"Synthetic-only test authorization, not actual commercial rights"}}

def fixture(**extra):
    row={"home_team":"Arsenal","away_team":"Chelsea",
         "kickoff_utc":"2026-10-15T18:00:00Z",
         "status":"prematch","sources":{"espn":{"id":"E1"}},
         "league_labels":["Premier League"],"league_verified":True,
         "ambiguous_match":False,"league_conflict":False,"scores_conflict":False}
    row.update(extra)
    return row

def matches(session,home,away,limit):
    return [{"source":"sportscore","provider_event_id":"h2h1",
             "home_team":"Arsenal","away_team":"Chelsea",
             "event_date":"2026-08-01T19:00:00Z","state":"post",
             "league":"Premier League",
             "home_score":1,"away_score":0},
            {"source":"sportscore","provider_event_id":"h2h2",
             "home_team":"Chelsea","away_team":"Arsenal",
             "event_date":"2026-03-01T19:00:00Z","state":"post",
             "league":"Premier League",
             "home_score":0,"away_score":0}]

class FakeSession:
    total=0

class AuthorizedH2HTests(unittest.TestCase):
    def test_denied_rights_causes_zero_calls(self):
        fired=[]
        def forbidden(*args,**kwargs):
            fired.append(True)
            raise AssertionError("Must not call")
        snapshots,report=collect([fixture()],{},now=NOW,session=FakeSession(),fetcher=forbidden)
        self.assertEqual(snapshots,[])
        self.assertEqual(report["requests"],0)
        self.assertEqual(fired,[])

    def test_approved_fetch_records_keep_zero_score_and_provider(self):
        snapshots,report=collect([fixture()],RIGHTS,now=NOW,
                                 session=FakeSession(),fetcher=matches)
        self.assertEqual(report["pairs_attempted"],1)
        self.assertEqual(report["raw_h2h_rows_with_scores"],2)
        self.assertEqual(snapshots[0]["provider"],"sportscore")
        self.assertEqual(snapshots[0]["rows"][1]["home_score"],0)
        self.assertFalse(report["production_published"])

    def test_finished_bsd_or_ambiguous_fixtures_not_queried(self):
        fired=[]
        def callback(*args,**kwargs):
            fired.append(True)
            return []
        cases=[fixture(status="not_prematch"),fixture(ambiguous_match=True),
               fixture(sources={"bsd":{"id":"A"},"espn":{"id":"B"}}),
               fixture(kickoff_utc="2026-10-14T08:00:00Z")]
        snapshots,report=collect(cases,RIGHTS,now=NOW,
                                 session=FakeSession(),fetcher=callback)
        self.assertEqual(fired,[])
        self.assertEqual(report["pairs_attempted"],0)

    def test_pair_deduplication(self):
        fired=[]
        def callback(*args,**kwargs):
            fired.append(True)
            return matches(*args,**kwargs)
        snapshots,report=collect([fixture(),fixture()],
                                 RIGHTS,now=NOW,session=FakeSession(),fetcher=callback)
        self.assertEqual(report["pairs_attempted"],1)
        self.assertEqual(len(fired),1)

if __name__=="__main__":
    unittest.main()
