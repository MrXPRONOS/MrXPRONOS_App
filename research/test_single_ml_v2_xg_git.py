import json,sys,tempfile,unittest
from datetime import date,datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import single_ml_v2_xg as xg
import single_ml_v2 as ml
from single_ml_v2_xg_resolve import reconcile, scheduled_events

UTC=timezone.utc
KICK="2026-09-10T16:00:00Z"
MATCH={"id":"123456","sportId":1,"is_finished":True,"status_group":4,
       "start_time":KICK,"home_team":"Home FC","away_team":"Away FC",
       "home_score":2,"away_score":1,"competition":"League"}
EVENT={"id":999999,"homeTeam":{"name":"Home FC"},"awayTeam":{"name":"Away FC"},
       "homeScore":{"current":2},"awayScore":{"current":1},
       "startTimestamp":int(datetime.fromisoformat(KICK.replace("Z","+00:00")).timestamp())}

def statistics(home="0.0",away="2.35",period="ALL"):
    return {"success":True,"matchId":999999,"data":{"statistics":[
        {"period":period,"groups":[{"groupName":"Match overview",
         "statisticsItems":[{"key":"expectedGoals","name":"Expected goals",
                             "home":home,"away":away}]}]}]}}

class FakeClient:
    def __init__(self,stats,event=None):
        self.stats=stats
        self.event=event or EVENT
        self.used=0
        self.limit=15
    def get(self,path):
        self.used+=1
        if path.startswith("/schedule/"):
            return {"success":True,"events":[self.event]}
        if path.endswith("/statistics"):return self.stats
        return {"data":{"event":self.event}}

class XGTests(unittest.TestCase):
    def setUp(self):
        self.key=b"k"*32
        self.now=datetime(2026,10,24,10,tzinfo=UTC)
    def test_documented_all_period_and_zero(self):
        self.assertEqual(xg.extract_xg(statistics()),(0.0,2.35))
        self.assertIsNone(xg.extract_xg(statistics(period="1ST")))
        self.assertIsNone(xg.extract_xg({"data":{"statistics":[]}}))
        mirror=statistics()
        item=mirror["data"]["statistics"][0]["groups"][0]["statisticsItems"][0]
        item.pop("home");item.pop("away")
        item["homeValue"]=0;item["awayValue"]=1.1
        self.assertEqual(xg.extract_xg(mirror),(0.,1.1))
    def test_conflict_detected(self):
        d=statistics()
        d["data"]["statistics"][0]["groups"].append({"statisticsItems":[
          {"key":"expectedGoals","home":2,"away":2}]})
        with self.assertRaises(ValueError):xg.extract_xg(d)
    def test_v1_v2_different_ids_and_ambiguous_schedule(self):
        self.assertEqual(reconcile(MATCH,[EVENT]),("999999",None))
        self.assertEqual(reconcile(MATCH,[EVENT,dict(EVENT,id=999998)])[1],
                         "ambiguous_fixture")
        self.assertIsNone(reconcile(MATCH,[dict(EVENT,homeTeam={"name":"Wrong"})])[0])
    def test_real_capture_not_backdated(self):
        c=FakeClient(statistics())
        record=xg.fetch_observation(c,MATCH,now=self.now)
        self.assertEqual(record["status"],"measured")
        self.assertEqual(record["provider_match_id"],"999999")
        self.assertEqual(record["xg_usable_after"],self.now.isoformat())
        self.assertEqual(c.used,3)
    def test_reject_unmatched_detail(self):
        class Mismatch(FakeClient):
            def get(self,path):
                if path.endswith("/statistics"):return statistics()
                if path.startswith("/match/"):return {"event":dict(EVENT,awayTeam={"name":"Other"})}
                return super().get(path)
        self.assertEqual(xg.fetch_observation(Mismatch(statistics()),MATCH,now=self.now)["status"],"identity_unverified")
    def test_ciphertext_overlay_and_model(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            record={"match_id":MATCH["id"],"kickoff":KICK,"home_team":"Home FC",
                    "away_team":"Away FC","status":"measured","home_xg":0.0,
                    "away_xg":1.2,"xg_source":xg.PROVIDER,"xg_quality":xg.QUALITY,
                    "xg_usable_after":self.now.isoformat(),"provider_match_id":"999999"}
            self.assertTrue(xg.write_record(record,self.key,root))
            self.assertFalse(xg.write_record(record,self.key,root))
            p=xg.record_path(MATCH["id"],self.key,root)
            self.assertNotIn(b"Home FC",p.read_bytes())
            enriched,a=xg.enrich_from_encrypted([MATCH],self.key,root=root)
            self.assertEqual(a["measured"],1)
            self.assertEqual(enriched[0]["home_xg"],0.)
            data=root/"matches.json";data.write_text(json.dumps(enriched))
            loaded=ml.load_matches(str(data),date(2026,10,24))
            self.assertEqual(loaded[0].xgh,0.)
            self.assertEqual(loaded[0].xg_available,self.now)
            data.write_text(json.dumps([dict(enriched[0],xg_quality="fake")]))
            self.assertIsNone(ml.load_matches(str(data),date(2026,10,24))[0].xgh)
    def test_missing_never_fabricated(self):
        with tempfile.TemporaryDirectory() as root:
            rows,report=xg.enrich_from_encrypted([MATCH],self.key,root=root)
            self.assertEqual(report["missing"],1)
            self.assertNotIn("home_xg",rows[0])
if __name__=="__main__":unittest.main()
