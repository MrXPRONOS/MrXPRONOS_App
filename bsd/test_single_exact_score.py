"""Isolated tests for exactly ONE exact-score forecast, BSD chronology and archives."""
import json,sys,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cryptography.fernet import Fernet
sys.path.insert(0,str(Path(__file__).parent))
from bsd_v2_core import V2History
from exact_scores import matrix_for
from exact_scores_h2h import H2HIndex
from single_exact_score_engine import (
    forecast,score_choice,PARAMETERS,VERSION,train_dc,
    result_probabilities,direction_adjusted)
from single_exact_score_backtest import compare
from single_exact_score_prospective import (
    empty,read,save,digest,capture,settle,summary)

NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)
def fixture(i,date,home=10,away=20,score=None,finished=False):
    return {"id":i,"event_date":date.isoformat(),"home_team_id":home,"away_team_id":away,
            "home_score":score[0] if score else None,
            "away_score":score[1] if score else None,
            "status":"finished" if finished else "notstarted",
            "league_id":55}
def sample_history(add_future=False):
    games=[]
    for i in range(12):
        d=NOW-timedelta(days=155-11*i)
        games.append(fixture(100+i,d,10,40+i,score=(1,0),finished=True))
        games.append(fixture(200+i,d,50+i,20,score=(0,1),finished=True))
    if add_future:
        games.append(fixture(980,NOW+timedelta(days=2),10,20,score=(8,9),finished=True))
    return V2History(games)
class DummyDC:
    def predict(self,fixture,index,prior):
        return (.6,.25,.15)
class SingleExactScoreTests(unittest.TestCase):
    def test_returns_single_main_score_and_no_group_market(self):
        idx=sample_history();fixture_obj=fixture(990,NOW+timedelta(days=1))
        result,why=forecast(fixture_obj,idx,H2HIndex(idx),now=NOW,
                            dc_model=DummyDC(),compute_form=False)
        self.assertEqual(why,"ok")
        self.assertTrue(result["one_score_only"])
        self.assertEqual(len(result["score"]),2)
        self.assertEqual(result["model"],VERSION)
        self.assertTrue(0<result["estimated_score_probability"]<1)
        self.assertNotIn("groups",result)
        self.assertNotIn("top3",result)
        self.assertFalse(result["published"])
        self.assertEqual(result["ablation"]["under25_fusion"]["score"],result["score"])
    def test_no_predictions_after_kickoff_or_too_close(self):
        idx=sample_history()
        for d in (-3,0,20):
            e=fixture(888,NOW+timedelta(minutes=d))
            row,why=forecast(e,idx,H2HIndex(idx),now=NOW,compute_form=False)
            self.assertIsNone(row)
            self.assertEqual(why,"too_close_or_started")
    def test_exact_score_distribution_normalized_after_dc_direction(self):
        matrix=matrix_for(1.5,1.1)
        dc=direction_adjusted(matrix,(.58,.25,.17))
        self.assertAlmostEqual(sum(dc.values()),1.0,places=5)
        self.assertEqual(set(dc),set(matrix))
        self.assertAlmostEqual(result_probabilities(dc)["1"],.58,places=4)
        self.assertAlmostEqual(result_probabilities(dc)["X"],.25,places=4)
        with self.assertRaises(ValueError):
            direction_adjusted(matrix,(.8,.6,.2))
    def test_chronology_rejects_future_match_leakage(self):
        before=sample_history()
        after=sample_history(add_future=True)
        event=fixture(999,NOW+timedelta(days=1))
        a,_=forecast(event,before,H2HIndex(before),now=NOW,compute_form=False)
        b,_=forecast(event,after,H2HIndex(after),now=NOW,compute_form=False)
        self.assertEqual(a["score"],b["score"])
        self.assertEqual(a["estimated_score_probability"],b["estimated_score_probability"])
    def test_first_seen_forecast_is_immutable_after_settlement(self):
        index=sample_history();archive=empty()
        f=fixture(921,NOW+timedelta(days=1))
        self.assertEqual(capture(archive,[f],index,DummyDC(),NOW)["captured"],1)
        sha=archive["records"]["921"]["forecast_sha256"]
        self.assertEqual(capture(archive,[f],index,DummyDC(),NOW)["already_seen"],1)
        final=fixture(921,NOW+timedelta(days=1),score=(1,0),finished=True)
        self.assertEqual(settle(archive,[final],NOW+timedelta(days=1,hours=3)),{})
        self.assertEqual(settle(archive,[final],NOW+timedelta(days=1,hours=5)),{"settled":1})
        self.assertEqual(archive["records"]["921"]["forecast_sha256"],sha)
        self.assertIsInstance(archive["records"]["921"]["hit"],int)
        self.assertEqual(summary(archive,NOW)["settled"],1)
    def test_encrypted_archive_and_tampering_rejected(self):
        index=sample_history();archive=empty()
        f=fixture(922,NOW+timedelta(days=1))
        capture(archive,[f],index,DummyDC(),NOW)
        secret=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"single.enc.json"
            save(archive,path,secret)
            self.assertNotIn('"score"',path.read_text())
            self.assertEqual(read(path,secret),archive)
            archive["records"]["922"]["score"]=[9,9]
            with self.assertRaises(ValueError):save(archive,path,secret)
    def test_empty_backtest_no_false_accuracy(self):
        empty_report=compare([],year=2026,dc_model=DummyDC())
        self.assertEqual(empty_report["eligible"],0)
        self.assertIsNone(empty_report["variants"]["under25_fusion"]["top1_rate"])
        self.assertEqual(empty_report["variants"]["under25_fusion"]["matches"],0)
if __name__=="__main__":unittest.main()
