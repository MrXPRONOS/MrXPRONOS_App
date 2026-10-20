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
from single_exact_score_research import audit,rank,prematch_context
from single_exact_score_distributions import candidates,bivariate,negative_binomial
from single_exact_score_advanced import train_advanced,advanced_prediction,historic_measured_xg
from single_exact_score_context import enrich_lineups,hydrate_history_xg,lineup_context
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
    def test_research_score_breakdown_selection_no_outcome_leak(self):
        rows=[]
        for i in range(5):
            base={"score":[1,1],"probability":.15+i*.01,"margin":.02}
            dc={"score":[1,0],"probability":.20+i*.01,"margin":.04}
            rows.append({"id":str(i),"kickoff":f"2026-05-02T1{i}:00:00+00:00",
                "actual":[1,0] if i%2==0 else [0,0],
                "total_expected_goals":2.4,
                "quality":{"home_recent_matches":10,"away_recent_matches":10},
                "context":{"available":False,"reason":"missing"},
                "variants":{"original":base,"under25_fusion":base,"optional_dc_fusion":dc}})
        before=rank(rows[0])
        rows[0]["actual"]=[8,5]
        self.assertEqual(rank(rows[0]),before)
        d=audit(rows)["research_diagnostics"]
        self.assertTrue(d["label_blind_ranking"])
        self.assertEqual(d["models"]["under25_fusion"]["selection"]["daily_top_three"]["baskets"],1)
        self.assertEqual(sum(v["matches"] for v in d["models"]["under25_fusion"]["scores"]["predicted"].values()),5)
        self.assertEqual(d["paired"]["under_vs_conditional_dc"]["net_b_minus_a"],2)
    def test_distribution_variants_are_normalized(self):
        for matrix in candidates(1.7,1.1).values():
            self.assertAlmostEqual(sum(matrix.values()),1.,places=8)
        with self.assertRaises(ValueError):bivariate(1.,1.,shared=1.)
        with self.assertRaises(ValueError):negative_binomial(1.,1.,dispersion=-1.)
    def test_context_rejects_future_observations(self):
        kickoff=NOW+timedelta(hours=5)
        e={"prematch_context":{"observed_at_utc":(NOW-timedelta(hours=1)).isoformat(),
                               "home_absences":2,"source":"source before game"}}
        self.assertTrue(prematch_context(e,NOW,kickoff)["available"])
        e["prematch_context"]["observed_at_utc"]=(NOW+timedelta(hours=1)).isoformat()
        self.assertFalse(prematch_context(e,NOW,kickoff)["available"])
        self.assertFalse(prematch_context({"prematch_context":{"home_absences":2}},NOW,kickoff)["available"])
    def test_advanced_2024_only_training_and_future_leakage(self):
        early=sample_history()
        late=sample_history(add_future=True)
        m1=train_advanced(early)
        m2=train_advanced(late)
        self.assertEqual(m1.info(),m2.info())
        self.assertEqual(m1.diagnostic["eligible_2024"],0)
        game=fixture(999,NOW+timedelta(days=1))
        a,_=forecast(game,early,H2HIndex(early),now=NOW,compute_form=False,advanced_model=m1)
        b,_=forecast(game,late,H2HIndex(late),now=NOW,compute_form=False,advanced_model=m2)
        self.assertEqual(a["advanced_research"]["choice"],b["advanced_research"]["choice"])
        self.assertEqual(a["score"],b["score"])
        self.assertEqual(len(a["advanced_research"]["choice"]["score"]),2)
    def test_only_measured_historical_xg(self):
        old=fixture(700,NOW-timedelta(days=8),score=(2,0),finished=True)
        old.update({"home_xg_live":1.56,"away_xg_live":.72,"xg_estimated":True})
        self.assertIsNone(historic_measured_xg(old))
        old["xg_estimated"]=False
        self.assertEqual(historic_measured_xg(old),(1.56,.72))
    def test_bsd_lineup_context_and_no_lookahead(self):
        valid={"lineup_status":"predicted","unavailable_players":{"home":[1,2],"away":[3]}}
        d=lineup_context(valid,NOW)
        self.assertEqual(d["home_absences"],2)
        self.assertEqual(d["away_absences"],1)
        self.assertIsNone(lineup_context({"lineup_status":"unavailable"},NOW))
        class StubClient:
            requests_made=0
            max_requests=10
            def get_json(self,path,ttl=0):
                self.requests_made+=1
                if path.endswith("/lineups/"):return valid
                return {"stats":{"home":{"xg":{"actual":1.2,"estimated":False}},
                                 "away":{"xg":{"actual":.9,"estimated":False}}}}
        game=fixture(721,NOW+timedelta(days=1))
        cl=StubClient()
        info=enrich_lineups([game],cl,NOW,max_lookups=1)
        self.assertEqual(info["found"],1)
        self.assertTrue(prematch_context(game,NOW,NOW+timedelta(days=1))["available"])
        earlier=sample_history()
        updated=hydrate_history_xg(earlier,[game],cl,NOW,max_lookups=2)
        self.assertLessEqual(updated["attempts"],2)
    def test_goal_rates_learn_without_forced_result(self):
        from single_exact_score_advanced import goal_fit,adjusted
        flat={"home":1.,"away":1.}
        rows=[{"base":flat,"feat":(1.,0.,0.,0.,0.),"truth":(2,0)}
              for _ in range(120)]
        w=goal_fit(rows,epochs=150)
        h,a=adjusted(flat,(1.,0.,0.,0.,0.),w)
        self.assertGreater(h,1.)
        self.assertLess(a,1.)
    def test_score_bias_probability_conserved(self):
        from single_exact_score_advanced import bias_matrix,SCORES
        m=matrix_for(1.4,1.2)
        factors=tuple(.72 if score==(1,1) else 1. for score in SCORES)
        corrected=bias_matrix(m,factors,1.)
        self.assertAlmostEqual(sum(corrected.values()),1.,places=10)
        self.assertLess(corrected[(1,1)],m[(1,1)])
        self.assertEqual(m,bias_matrix(m,factors,0.))
    def test_reliability_learner_fits_independent_labels(self):
        from single_exact_score_advanced import fit_logistic,sigmoid,dot
        samples=[((1.,-.6,0.,0.,0.),0) for _ in range(100)]
        samples += [((1.,-.15,0.,0.,0.),1) for _ in range(100)]
        weights=fit_logistic(samples,epochs=200)
        a=sigmoid(dot(weights,(1.,-.6,0.,0.,0.)))
        b=sigmoid(dot(weights,(1.,-.15,0.,0.,0.)))
        self.assertLess(a,b)
    def test_historical_xg_never_reads_future_fixture_result(self):
        from single_exact_score_advanced import features
        start=sample_history()
        with_future=sample_history(add_future=True)
        match=fixture(992,NOW+timedelta(days=1))
        expected={"home":1.2,"away":1.3,"home_venue_matches":4,"away_venue_matches":4}
        first,_=features(match,start,expected)
        second,_=features(match,with_future,expected)
        self.assertEqual(first,second)
    def test_empty_backtest_no_false_accuracy(self):
        empty_report=compare([],year=2026,dc_model=DummyDC())
        self.assertEqual(empty_report["eligible"],0)
        self.assertIsNone(empty_report["variants"]["under25_fusion"]["top1_rate"])
        self.assertEqual(empty_report["variants"]["under25_fusion"]["matches"],0)
if __name__=="__main__":unittest.main()
