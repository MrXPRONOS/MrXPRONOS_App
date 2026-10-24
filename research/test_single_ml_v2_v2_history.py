import json,sys,tempfile,unittest
from datetime import date,datetime,timezone
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_v2_history import v2_fixture,collect,VERSION
from single_ml_v2_git import day_data,path_for,load_manifest
UTC=timezone.utc
DAY=date(2026,9,20)
def evt(sport=1,status="finished",home=2,away=1):
    return {"id":991,
       "startTimestamp":int(datetime(2026,9,20,13,tzinfo=UTC).timestamp()),
       "homeTeam":{"id":13,"name":"Home","sport":{"id":sport}},
       "awayTeam":{"id":25,"name":"Away","sport":{"id":sport}},
       "tournament":{"name":"Test league","id":5,"category":{"sport":{"id":sport}}},
       "homeScore":{"current":3,"normaltime":home},
       "awayScore":{"current":2,"normaltime":away},
       "status":{"type":status}}
class V2Tests(unittest.TestCase):
    def test_certified_normal_and_provider_namespace(self):
        m=v2_fixture(evt(),DAY)
        self.assertEqual(m["id"],"v2-991")
        self.assertEqual((m["home_score"],m["away_score"]),(2,1))
        self.assertEqual(m["source_home_team_id"],13)
        self.assertEqual(m["sportId"],1)
        fallback=evt()
        fallback["homeScore"]["normaltime"]=None
        fallback["awayScore"]["normaltime"]=None
        self.assertEqual(v2_fixture(fallback,DAY)["home_score"],3)
    def test_strict_verified_no_synthetic(self):
        self.assertIsNone(v2_fixture(evt(status="inprogress"),DAY))
        self.assertIsNone(v2_fixture(evt(sport=3),DAY))
        missing_score=evt(home=None)
        missing_score["homeScore"]["current"]=None
        self.assertIsNone(v2_fixture(missing_score,DAY))
        x=evt();x["id"]=None
        self.assertIsNone(v2_fixture(x,DAY))
    def test_one_day_encrypted_and_global_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            key=b"k"*32;calls=[]
            def fetch(day,*,token):
                calls.append(day)
                return [evt(),evt(status="inprogress")]
            result=collect(DAY,DAY,key=key,token="DUMMY",root=temp,limit=1,fetcher=fetch)
            self.assertEqual(result["status"],"COMPLETE")
            self.assertEqual(result["new_days_saved"],1)
            self.assertEqual(len(calls),1)
            path=path_for(DAY,temp)
            self.assertNotIn(b"Test league",path.read_bytes())
            record=day_data(path,key,DAY)
            self.assertEqual(record["certified_football_count"],1)
            self.assertEqual(load_manifest(key,temp)["days"],1)
            result2=collect(DAY,DAY,key=key,token="DUMMY",root=temp,limit=1,fetcher=fetch)
            self.assertEqual(result2["new_days_saved"],0)
            self.assertEqual(len(calls),1)
    def test_invalid_v2_day_fails_without_fabricating_file(self):
        with tempfile.TemporaryDirectory() as temp:
            status=collect(DAY,DAY,key=b"A"*32,token="DUMMY",
                  root=temp,limit=1,fetcher=lambda day,*,token:[])
            self.assertEqual(status["new_days_saved"],0)
            self.assertEqual(status["missing_window_days"],1)
            self.assertFalse(path_for(DAY,temp).exists())
if __name__=="__main__":unittest.main()
