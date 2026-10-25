import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_git import seal,open_sealed,atomic_bytes
from single_ml_v2_2024_repair import repair,target_dates,AAD
from single_ml_v2_bsd_sportscore_2024 import SCHEMA
class Response:
    status_code=200
    content=b'json'
    def json(self):
        return {"matches":[{"time":"2024-03-09T12:00:00Z",
             "home":"Team A","away":"Team B","competition":"Cup",
             "home_score":1,"away_score":0,"status":"finished",
             "url":"/fixture/a-b"}],"count":1}
class Session:
    def __init__(self):self.n=0
    def get(self,*args,**kwargs):self.n+=1;return Response()
class RepairTests(unittest.TestCase):
    def test_only_failed_2024_day_retried_with_encrypted_patch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=b'X'*32
            for m in range(1,13):
                original={"schema":SCHEMA,"year":2024,"month":m,"matches":[],
                    "audit":{"sportscore":{"failed_dates":
                      [{"date":"2024-03-09","reason":"Timeout"}] if m==3 else []}}}
                path=root/f"bsd_sportscore/2024/{m:02d}.enc"
                atomic_bytes(path,seal(original,key,"bsd-sportscore-2024-month:"+str(m)))
            self.assertEqual(target_dates(root=root,key=key),["2024-03-09"])
            sess=Session()
            with unittest.mock.patch("single_ml_v2_2024_repair.time.sleep",return_value=None):
                report,created=repair(root=root,key=key,session=sess)
            self.assertTrue(created)
            self.assertEqual(report["recovered_dates"],1)
            self.assertEqual(report["unresolved_dates"],[])
            self.assertEqual(sess.n,1)
            path=root/"bsd_sportscore/2024_repair.enc"
            self.assertNotIn(b"Team A",path.read_bytes())
            verified=open_sealed(path.read_bytes(),key,AAD)
            self.assertEqual(len(verified["matches"]),1)
            second,created=repair(root=root,key=key,session=sess)
            self.assertFalse(created)
            self.assertEqual(second["source_requests"],1)
if __name__=="__main__":
    from unittest import mock
    unittest.main()
