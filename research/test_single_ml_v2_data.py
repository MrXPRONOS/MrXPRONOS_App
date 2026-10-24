import json,sys,tempfile,unittest
from datetime import date,datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_data import normalize,day_snapshot,build_archive
from single_ml_v2 import load_matches,FormState

K="2026-09-01T18:00:00Z"
def raw(sport=1,score=(2,0)):
    return {"id":"123","sportId":sport,"startTime":K,"statusGroup":4,
            "competitionDisplayName":"Test League","homeCompetitor":{"name":"A","score":score[0]},
            "awayCompetitor":{"name":"B","score":score[1]}}
class DataTests(unittest.TestCase):
    def test_sport_and_scores(self):
        ok,why=normalize(raw(),date(2026,9,1))
        self.assertEqual(ok["sportId"],1)
        self.assertIsNone(normalize(raw(3),date(2026,9,1))[0])
        self.assertIsNone(normalize(raw(None),date(2026,9,1))[0])
        self.assertIsNone(normalize(raw(1,(-1,2)),date(2026,9,1))[0])
    def test_snapshot_conflict(self):
        bad=raw();other=raw(score=(1,1))
        with self.assertRaises(ValueError):
            day_snapshot(date(2026,9,1),SimpleNamespace(ok=True,games=[bad,other],endpoint="mock"))
    def test_archive_fails_closed_and_resumes(self):
        with tempfile.TemporaryDirectory() as root:
            d=Path(root); calls=[]
            def fetch(a,b,**kw):
                calls.append(a)
                return SimpleNamespace(ok=True,games=[raw()] if a==date(2026,9,1) else [],endpoint="mock")
            a=build_archive(d/"days",date(2026,9,1),date(2026,9,2),d/"archive.json",d/"audit.json",max_days=1,fetcher=fetch)
            self.assertFalse(a["complete"])
            self.assertFalse((d/"archive.json").exists())
            a=build_archive(d/"days",date(2026,9,1),date(2026,9,2),d/"archive.json",d/"audit.json",fetcher=fetch)
            self.assertTrue(a["complete"]);self.assertEqual(len(calls),2)
            self.assertEqual(len(json.loads((d/"archive.json").read_text())),1)
if __name__=="__main__":unittest.main()
