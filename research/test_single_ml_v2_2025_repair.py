import sys,tempfile,unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_git import seal,open_sealed,atomic_bytes
from single_ml_v2_2024_repair import repair,target_dates,aad_for_year
class FakeResponse:
    status_code=200
    content=b"json"
    def json(self):
        return {"matches":[{"time":"2025-02-12T13:00:00Z",
            "home":"A","away":"B","competition":"Cup",
            "home_score":2,"away_score":2,"status":"finished",
            "url":"/cup/a-vs-b"}],"count":1}
class FakeSession:
    def get(self,*args,**kwargs):return FakeResponse()
class Tests(unittest.TestCase):
    def test_only_failed_2025_days_and_year_specific_cipher(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);key=b"b"*32
            for month in range(1,13):
                doc={"schema":"bsd_sportscore_2025_private_verified_v1",
                     "year":2025,"month":month,"matches":[],
                     "audit":{"sportscore":{"failed_dates":
                         [{"date":"2025-02-12"}] if month==2 else []}}}
                path=root/f"bsd_sportscore/2025/{month:02d}.enc"
                atomic_bytes(path,seal(doc,key,"bsd-sportscore-2025-month:"+str(month)))
            self.assertEqual(target_dates(root=root,key=key,year=2025),["2025-02-12"])
            with mock.patch("single_ml_v2_2024_repair.time.sleep",return_value=None):
                audit,new=repair(root=root,key=key,year=2025,session=FakeSession())
            self.assertTrue(new)
            self.assertEqual(audit["recovered_dates"],1)
            self.assertFalse(audit["unresolved_dates"])
            p=root/"bsd_sportscore/2025_repair.enc"
            self.assertNotIn(b'"home_team":"A"',p.read_bytes())
            obj=open_sealed(p.read_bytes(),key,aad_for_year(2025))
            self.assertEqual(obj["year"],2025)
            self.assertEqual(obj["matches"][0]["source"],"sportscore_2025")
if __name__=="__main__":unittest.main()
