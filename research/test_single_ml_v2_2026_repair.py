"""Only retrospectively failed 2026 SportScore days may be retried."""
import sys,tempfile,unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_git import seal,atomic_bytes,open_sealed
from single_ml_v2_2024_repair import target_dates,repair,aad_for_year
class Response:
    status_code=200
    content=b'fake'
    def json(self):
        return {"matches":[{"time":"2026-10-23T15:00:00Z",
            "home":"A","away":"B","competition":"Cup",
            "home_score":1,"away_score":2,"status":"finished",
            "url":"/fixture/a-v-b"}],"count":1}
class S:
    def __init__(self):self.calls=0
    def get(self,*args,**kwargs):self.calls+=1;return Response()
class Repair2026Tests(unittest.TestCase):
    def test_exact_missing_day_october_and_separate_encryption(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=b'z'*32
            for month in range(1,11):
                doc={"schema":"bsd_sportscore_2026_private_verified_v1",
                     "month":month,"year":2026,
                     "audit":{"sportscore":{"failed_dates":
                         [{"date":"2026-10-23","reason":"TimeoutError"}] if month==10 else []}}}
                p=root/f"bsd_sportscore/2026/{month:02d}.enc"
                atomic_bytes(p,seal(doc,key,f"bsd-sportscore-2026-month:{month}"))
            self.assertEqual(target_dates(root=root,key=key,year=2026,
                through="2026-10-24"),["2026-10-23"])
            session=S()
            with mock.patch("single_ml_v2_2024_repair.time.sleep",return_value=None):
                audit,saved=repair(root=root,key=key,year=2026,
                        through="2026-10-24",session=session)
            self.assertTrue(saved)
            self.assertEqual(audit["recovered_dates"],1)
            self.assertEqual(audit["unresolved_dates"],[])
            self.assertEqual(session.calls,1)
            p=root/"bsd_sportscore/2026_repair.enc"
            obj=open_sealed(p.read_bytes(),key,aad_for_year(2026))
            self.assertEqual(obj["matches"][0]["date"],"2026-10-23")
            self.assertEqual(obj["matches"][0]["source"],"sportscore_2026")
if __name__=="__main__":unittest.main()
