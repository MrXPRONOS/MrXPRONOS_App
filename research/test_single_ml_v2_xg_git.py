import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
import single_ml_v2_xg as xg
import single_ml_v2 as ml
from single_ml_v2_git import open_sealed

UTC=timezone.utc
KICK="2026-09-10T16:00:00Z"
MATCH={"id":"123456","sportId":1,"is_finished":True,"status_group":4,
       "start_time":KICK,"home_team":"Home FC","away_team":"Away FC",
       "home_score":2,"away_score":1,"competition":"League"}
EVENT={"id":123456,"homeTeam":{"name":"Home FC"},"awayTeam":{"name":"Away FC"},
       "startTimestamp":1789056000}
# Correct UTC timestamp reconstructed from explicit kickoff to avoid hidden
# timezone assumptions in test fixtures.
EVENT["startTimestamp"]=int(datetime.fromisoformat(KICK.replace("Z","+00:00")).timestamp())


class FakeClient:
    def __init__(self,statistics,event=None):
        self.statistics=statistics;self.event=event;self.used=0;self.limit=8
    def get(self,path):
        self.used+=1
        if path.endswith("/statistics"):return self.statistics
        return {"data":{"event":self.event}} if self.event is not None else None


class XGTests(unittest.TestCase):
    def setUp(self):
        self.key=b"k"*32
        self.now=datetime(2026,10,24,10,tzinfo=UTC)
    def test_real_totals_and_zero(self):
        source={"data":{"statistics":{"expectedGoals":{"home":0,"away":"2.35"}}}}
        self.assertEqual(xg.extract_xg(source),(0.0,2.35))
        self.assertIsNone(xg.extract_xg({"data":{"statistics":{"shotsOnGoal":{"home":4,"away":5}}}}))
    def test_contradictions_and_periods(self):
        self.assertIsNone(xg.extract_xg({"data":{"periods":[{"period":"FIRST_HALF",
           "expectedGoals":{"home":1,"away":2}}]}}))
        with self.assertRaises(ValueError):
            xg.extract_xg({"data":{"expectedGoals":{"home":1,"away":2},
                     "statistics":{"expectedGoals":{"home":4,"away":4}}}})
    def test_identity_rejects_wrong_id_or_clubs(self):
        self.assertTrue(xg.require_matching_identity(EVENT,MATCH))
        with self.assertRaises(ValueError):
            xg.require_matching_identity({**EVENT,"homeTeam":{"name":"Other"}} ,MATCH)
        with self.assertRaises(ValueError):
            xg.require_matching_identity({**EVENT,"id":99},MATCH)
    def test_asof_is_observed_not_backdated(self):
        client=FakeClient({"data":{"statistics":{"expectedGoals":{"home":1.4,"away":0.9}}}},EVENT)
        result=xg.fetch_observation(client,MATCH,now=self.now)
        self.assertEqual(result["status"],"measured")
        self.assertEqual(result["xg_usable_after"],self.now.isoformat())
        self.assertEqual(client.used,2)
    def test_encrypted_research_overlay_and_ml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            record={"match_id":MATCH["id"],"kickoff":KICK,"home_team":"Home FC",
                    "away_team":"Away FC","status":"measured","home_xg":0.0,
                    "away_xg":1.2,"xg_source":xg.PROVIDER,"xg_quality":xg.QUALITY,
                    "xg_usable_after":self.now.isoformat()}
            self.assertTrue(xg.write_record(record,self.key,root))
            self.assertFalse(xg.write_record(record,self.key,root))
            path=xg.record_path(MATCH["id"],self.key,root)
            self.assertTrue(path.exists())
            self.assertNotIn(b"Home FC",path.read_bytes())
            enriched,report=xg.enrich_from_encrypted([MATCH],self.key,root=root)
            self.assertEqual(report["measured"],1)
            self.assertEqual(enriched[0]["home_xg"],0.0)
            import json
            archive=root/"matches.json"
            archive.write_text(json.dumps(enriched))
            matches=ml.load_matches(str(archive),date(2026,10,24))
            self.assertEqual(len(matches),1)
            self.assertEqual(matches[0].xgh,0.0)
            self.assertEqual(matches[0].xg_available,self.now)
            self.assertGreater(matches[0].xg_available.date(),matches[0].day)
            # Unverified fields cannot enter ML.
            unverified=dict(enriched[0],xg_quality="unknown")
            archive.write_text(json.dumps([unverified]))
            self.assertIsNone(ml.load_matches(str(archive),date(2026,10,24))[0].xgh)
    def test_missing_data_never_fabricated(self):
        with tempfile.TemporaryDirectory() as tmp:
            enriched,status=xg.enrich_from_encrypted([MATCH],self.key,root=tmp)
            self.assertEqual(status["missing"],1)
            self.assertNotIn("home_xg",enriched[0])


if __name__=="__main__":
    unittest.main()
