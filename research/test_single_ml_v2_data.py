import json,sys,tempfile,unittest
from datetime import date,datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
from single_ml_v2_data import normalize,day_snapshot,build_archive
from single_ml_v2_xg import enrich
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
    def test_xg_timestamp_and_ambiguity(self):
        row=normalize(raw(),date(2026,9,1))[0]
        stats={"source_name":"api_original","canonical_match_id":"abc",
               "home_team":"A","away_team":"B","event_date":K,
               "updated_at":"2026-09-01T20:15:00Z","minute":96,
               "stats_json":{"home":{"expected_goals":0},"away":{"expected_goals":1.8}}}
        before,_=enrich([row],[stats],asof=datetime(2026,9,1,20,0,tzinfo=timezone.utc))
        self.assertNotIn("home_xg",before[0])
        enriched,audit=enrich([row],[stats],asof=datetime(2026,9,2,tzinfo=timezone.utc))
        self.assertEqual(audit["enriched"],1)
        self.assertEqual(enriched[0]["home_xg"],0)
        self.assertEqual(enriched[0]["xg_quality"],"observed_late_match_90plus_provisional")
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"matches.json"
            path.write_text(json.dumps(enriched))
            m=load_matches(str(path),date(2026,9,2))[0]
            self.assertEqual(m.xgh,0.)
            self.assertEqual(m.xga,1.8)
            state=FormState()
            state.add(m)
            self.assertEqual(state.league_h[m.league].at(m.day)[5],0)
            state.add_xg(m,date(2026,9,2))
            self.assertGreater(state.league_h[m.league].at(date(2026,9,2))[5],0)
        conflict=dict(stats,canonical_match_id="another")
        ambiguous,report=enrich([row],[stats,conflict],asof=datetime(2026,9,2,tzinfo=timezone.utc))
        self.assertNotIn("home_xg",ambiguous[0])
        self.assertEqual(report["ambiguous_fixture"],1)
if __name__=="__main__":unittest.main()
