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
from single_exact_score_xg_history import empty as xg_empty,read as xg_read,save as xg_save,add as xg_add,apply as xg_apply
from single_exact_score_top3 import empty as top3_empty,read as top3_read,save as top3_save,select_groups,settle_groups,report as top3_report,verify as verify_top3
from single_exact_score_research import RANK_VERSION
from single_exact_score_context_model import learn as learn_absence,adjust as apply_absence,source_features as absence_features
from single_exact_score_context_observations import (
    empty as obs_empty,read as obs_read,save as obs_save,
    capture as obs_capture,valid as obs_valid)
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
        self.assertIsNone(historic_measured_xg(old,as_of=NOW))
        old["xg_available_at_utc"]=(NOW-timedelta(days=1)).isoformat()
        self.assertEqual(historic_measured_xg(old,as_of=NOW),(1.56,.72))
        self.assertIsNone(historic_measured_xg(old,as_of=NOW-timedelta(days=2)))
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
        info=enrich_lineups([game],cl,NOW,max_lookups=1,clock=lambda:NOW)
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
    def test_encrypted_measured_xg_cache_roundtrip_and_chronology(self):
        history=sample_history()
        old=history.global_games[-1][1]
        one={"home_xg":1.4,"away_xg":.8,
             "kickoff_utc":old["event_date"],
             "captured_at_utc":(NOW-timedelta(days=1)).isoformat(),
             "home_team_id":old["home_team_id"],"away_team_id":old["away_team_id"]}
        old_time=datetime.fromisoformat(old["event_date"])
        one["captured_at_utc"]=(old_time+timedelta(hours=6)).isoformat()
        doc=xg_empty()
        self.assertEqual(xg_add(doc,{str(old["id"]):one}),1)
        self.assertEqual(xg_add(doc,{str(old["id"]):one}),0)
        self.assertEqual(xg_apply(history,doc,NOW),1)
        self.assertEqual(old["home_xg_live"],1.4)
        self.assertEqual(old["xg_available_at_utc"],one["captured_at_utc"])
        key=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"xg.enc.json"
            xg_save(doc,path,key)
            self.assertNotIn('"home_xg"',path.read_text())
            self.assertEqual(xg_read(path,key),doc)
        invalid={**one,"captured_at_utc":(old_time+timedelta(hours=2)).isoformat()}
        self.assertEqual(xg_add(xg_empty(),{"bad":invalid}),0)
    def test_capture_rechecks_live_clock_for_each_forecast(self):
        archive=empty();index=sample_history()
        e=fixture(994,NOW+timedelta(hours=2))
        result=capture(archive,[e],index,DummyDC(),NOW,clock=lambda:NOW+timedelta(hours=1,minutes=45))
        self.assertEqual(result.get("too_close_or_started"),1)
        self.assertEqual(len(archive["records"]),0)
        ok=capture(archive,[e],index,DummyDC(),NOW,clock=lambda:NOW+timedelta(minutes=2))
        self.assertEqual(ok["captured"],1)
        self.assertEqual(archive["records"][str(e["id"])]["captured_at"],(NOW+timedelta(minutes=2)).isoformat())
    def test_zero_advanced_correction_matches_baseline_matrix(self):
        from single_exact_score_advanced import adjusted,matrix as advanced_matrix
        from exact_scores_under25 import Under25Model,reweight_scores
        from single_exact_score_advanced import bias_matrix
        event=fixture(997,NOW+timedelta(days=1))
        index=sample_history()
        base={"home":3.4,"away":1.15,"home_venue_matches":3,"away_venue_matches":3}
        weights=tuple(tuple(0. for _ in range(5)) for _ in range(2))
        h,a=adjusted(base,(1.,0.,0.,0.,0.),weights,0.)
        self.assertAlmostEqual(h,3.74,places=9)
        raw=matrix_for(base["home"],base["away"],scale_home=1.10)
        specialized=Under25Model(1.,.85,.62).predict(event,index,raw)
        original=reweight_scores(raw,specialized["probability"])
        candidate,*_=advanced_matrix(event,index,base,weights,0.)
        for score in raw:
            self.assertAlmostEqual(original[score],candidate[score],places=10)
        self.assertEqual(candidate,bias_matrix(candidate,(1.,)*8,0.))
    def test_rank_does_not_count_redundant_same_score_variants(self):
        from single_exact_score_research import rank,RANK_VERSION
        x={"score":[1,1],"probability":.17,"margin":.012}
        y={"score":[1,0],"probability":.18,"margin":.013}
        case={"quality":{"home_recent_matches":10,"away_recent_matches":10},
            "variants":{"original":x,"under25_fusion":x,
                        "optional_dc_fusion":y,"advanced_2024":x}}
        before=rank(case)
        case["variants"]["advanced_2024"]=dict(x)
        self.assertAlmostEqual(rank(case),before)
        self.assertIn("independent",RANK_VERSION)
    def test_top3_first_seen_immutable_and_settlement(self):
        ledger={"records":{}}
        for i in range(5):
            kickoff=NOW+timedelta(hours=6+i)
            key=str(9001+i)
            ledger["records"][key]={"id":key,"status":"pending",
                "score":[1,0],"selection_rank":.20+i*.01,
                "rank_version":RANK_VERSION,
                "kickoff":kickoff.isoformat(),"captured_at":NOW.isoformat(),
                "estimated_probability":.18,
                "forecast_sha256":"fixture_"+key}
        archive=top3_empty()
        created=select_groups(archive,ledger,NOW)
        self.assertEqual(created["created"],1)
        frozen=archive["records"][NOW.date().isoformat()]["digest"]
        self.assertEqual(len(archive["records"][NOW.date().isoformat()]["picks"]),3)
        ledger["records"]["9001"]["selection_rank"]=.99
        self.assertEqual(select_groups(archive,ledger,NOW)["already_seen"],1)
        self.assertEqual(archive["records"][NOW.date().isoformat()]["digest"],frozen)
        for j,pick in enumerate(archive["records"][NOW.date().isoformat()]["picks"]):
            row=ledger["records"][pick["id"]]
            row["status"]="settled"
            row["actual_score"]=[1,0] if j==0 else [0,1]
        self.assertEqual(settle_groups(archive,ledger,NOW+timedelta(days=1))["settled"],1)
        self.assertEqual(top3_report(archive)["baskets_with_at_least_one_hit"],1)
        key=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"top3.enc.json"
            top3_save(archive,file,key)
            self.assertEqual(top3_read(file,key),archive)
            self.assertNotIn("fixture_900",file.read_text())
    def test_top3_never_includes_started_or_unsorted_fixture(self):
        ledger={"records":{}}
        for i in range(3):
            key=str(i)
            ledger["records"][key]={"id":key,"status":"pending",
                "score":[1,1],"selection_rank":.25,
                "rank_version":RANK_VERSION,
                "kickoff":(NOW+timedelta(minutes=35+i)).isoformat(),
                "captured_at":NOW.isoformat(),"forecast_sha256":key}
        group=top3_empty()
        self.assertEqual(select_groups(group,ledger,NOW+timedelta(minutes=6))["created"],0)
        self.assertFalse(group["records"])
    def test_model_fingerprint_stable_and_changes_with_coefficients(self):
        from single_exact_score_advanced import train_advanced,AdvancedModel
        model=train_advanced(sample_history())
        self.assertEqual(model.fingerprint(),model.info()["model_fingerprint_sha256"])
        changed=AdvancedModel(model.goal_weights,model.goal_strength,
            model.bias_weights,model.bias_strength,model.reliability_weights,
            .25,model.diagnostic)
        self.assertNotEqual(model.fingerprint(),changed.fingerprint())
    def test_missing_or_unvalidated_absences_have_no_effect(self):
        h,a,used=apply_absence(1.4,1.1,{"available":False},None)
        self.assertEqual((h,a,used),(1.4,1.1,False))
        disabled={"active":False,"weights":((-.2,0.),(0.,-.3))}
        ctx={"available":True,"source":"bsd-v2-events-lineups",
             "values":{"home_absences":10,"away_absences":5,
                       "lineup_status":"confirmed"}}
        self.assertEqual(apply_absence(1.4,1.1,ctx,disabled),(1.4,1.1,False))
        self.assertEqual(absence_features(ctx),(1.,.5))
        active={"active":True,"weights":((-.2,0.),(0.,-.3))}
        self.assertTrue(apply_absence(1.4,1.1,ctx,active)[2])
        self.assertLess(apply_absence(1.4,1.1,ctx,active)[0],1.4)
    def test_absences_trained_only_on_settled_prematch_snapshots(self):
        archive={"records":{}}
        for i in range(300):
            capture_at=NOW-timedelta(days=400-i)
            kickoff_at=capture_at+timedelta(hours=4)
            archive["records"][str(i)]={
                "status":"settled","captured_at":capture_at.isoformat(),
                "kickoff":kickoff_at.isoformat(),
                "settled_at":(kickoff_at+timedelta(hours=8)).isoformat(),
                "actual_score":[0,0],
                "advanced_research":{"expected_goals":{"home":2.,"away":2.},
                    "context":{"available":True,"source":"bsd-v2-events-lineups",
                        "observed_at_utc":capture_at.isoformat(),
                        "values":{"lineup_status":"confirmed",
                            "home_absences":10,"away_absences":10}}}}
        model=learn_absence(archive,NOW)
        self.assertEqual(model["diagnostic"]["eligible"],300)
        self.assertTrue(model["active"])
        # Any pending or future-settled row cannot influence training.
        archive["records"]["late"]={**archive["records"]["0"],
            "settled_at":(NOW+timedelta(hours=10)).isoformat()}
        self.assertEqual(learn_absence(archive,NOW)["diagnostic"]["eligible"],300)
    def test_top3_refuses_forecast_digest_mismatch_in_settlement(self):
        x={"records":{}}
        for i in range(3):
            name=str(9500+i)
            x["records"][name]={"id":name,"status":"pending",
                 "score":[0,1],"kickoff":(NOW+timedelta(hours=4+i)).isoformat(),
                 "captured_at":NOW.isoformat(),"selection_rank":.20+i*.01,
                 "rank_version":RANK_VERSION,"forecast_sha256":"hash"+name}
        basket=top3_empty()
        self.assertEqual(select_groups(basket,x,NOW)["created"],1)
        for rec in x["records"].values():
            rec["status"]="settled"
            rec["actual_score"]=[0,1]
        x["records"]["9500"]["forecast_sha256"]="tampered"
        self.assertEqual(settle_groups(basket,x,NOW+timedelta(days=2))["settled"],0)
        self.assertEqual(top3_report(basket)["settled_baskets"],0)
    def test_end_to_end_three_distinct_match_snapshot_then_results(self):
        index=sample_history()
        fixtures=[fixture(9800+i,NOW+timedelta(hours=4+i))
                  for i in range(3)]
        match_ledger=empty()
        counters=capture(match_ledger,fixtures,index,DummyDC(),NOW,
                         clock=lambda:NOW)
        self.assertEqual(counters.get("captured"),3)
        self.assertEqual(len(match_ledger["records"]),3)
        self.assertEqual(len({record["id"] for record in match_ledger["records"].values()}),3)
        basket=top3_empty()
        self.assertEqual(select_groups(basket,match_ledger,NOW)["created"],1)
        day=NOW.date().isoformat()
        digest=basket["records"][day]["digest"]
        original_scores={row["id"]:row["score"][:] for row in
                         match_ledger["records"].values()}
        complete=[fixture(int(key),datetime.fromisoformat(
                  match_ledger["records"][key]["kickoff"]),
                  score=tuple(original_scores[key]),finished=True)
                  for key in original_scores]
        result=settle(match_ledger,complete,NOW+timedelta(days=1))
        self.assertEqual(result.get("settled"),3)
        self.assertEqual(settle_groups(basket,match_ledger,
                                      NOW+timedelta(days=1))["settled"],1)
        self.assertEqual(basket["records"][day]["digest"],digest)
        self.assertEqual(basket["records"][day]["hits"],3)
        self.assertEqual(top3_report(basket)["winning_basket_rate"],1.)
    def test_long_calculation_is_blocked_by_second_deadline_check(self):
        index=sample_history()
        e=fixture(9912,NOW+timedelta(hours=2))
        readings=iter((NOW,NOW+timedelta(hours=1,minutes=45)))
        archive=empty()
        result=capture(archive,[e],index,DummyDC(),NOW,clock=lambda:next(readings))
        self.assertEqual(result.get("too_close_after_compute"),1)
        self.assertEqual(len(archive["records"]),0)
    def test_context_fetch_timestamp_is_actual_response_time(self):
        game=fixture(9914,NOW+timedelta(hours=2))
        class DummyResponse:
            requests_made=0
            max_requests=20
            def get_json(self,path,ttl=0):
                self.requests_made+=1
                return {"lineup_status":"confirmed",
                        "unavailable_players":{"home":[1],"away":[2]}}
        stats=enrich_lineups([game],DummyResponse(),NOW,max_lookups=1,
                  clock=lambda:NOW+timedelta(hours=1,minutes=40))
        self.assertEqual(stats["found"],0)
        self.assertNotIn("prematch_context",game)
    def test_bsd_verified_lineup_replaces_unverified_payload(self):
        now=NOW
        upcoming=fixture(99877,NOW+timedelta(days=1))
        upcoming["prematch_context"]={
            "source":"fake-source","observed_at_utc":(NOW+timedelta(days=2)).isoformat(),
            "home_absences":25}
        class Source:
            requests_made=0
            max_requests=4
            def get_json(self, path, ttl=0):
                self.requests_made+=1
                return {"lineup_status":"confirmed",
                        "unavailable_players":{"home":[1],"away":[2]}}
        status=enrich_lineups([upcoming],Source(),now,clock=lambda:now)
        self.assertEqual(status["found"],1)
        got=upcoming["prematch_context"]
        self.assertEqual(got["source"],"bsd-v2-events-lineups")
        self.assertEqual(got["observed_at_utc"],now.isoformat())
        self.assertEqual(got["home_absences"],1)
    def test_absence_training_excludes_own_adjusted_predictions(self):
        record={
            "status":"settled",
            "captured_at":(NOW-timedelta(days=3)).isoformat(),
            "kickoff":(NOW-timedelta(days=3)+timedelta(hours=4)).isoformat(),
            "settled_at":(NOW-timedelta(days=2)).isoformat(),
            "actual_score":[1,1],
            "advanced_research":{
                "context_model_applied":True,
                "expected_goals":{"home":.5,"away":.5},
                "context":{"available":True,"source":"bsd-v2-events-lineups",
                    "observed_at_utc":(NOW-timedelta(days=3)).isoformat(),
                    "values":{"lineup_status":"confirmed","home_absences":2,
                              "away_absences":2}}}}
        self.assertEqual(learn_absence({"records":{"1":record}},NOW)
                         ["diagnostic"]["eligible"],0)
        record["advanced_research"]["rest_and_xg"]={
            "context_free_expected_goals":{"home":1.5,"away":1.2}}
        self.assertEqual(learn_absence({"records":{"1":record}},NOW)
                         ["diagnostic"]["eligible"],1)
    def test_top3_uses_pre_match_legacy_probabilities_without_rewriting(self):
        ledger={"records":{}}
        for i in range(4):
            rec={"id":str(22201+i),"status":"pending",
                "score":[1,1],"estimated_probability":.14+i*.01,
                "score_margin":.012,"captured_at":NOW.isoformat(),
                "kickoff":(NOW+timedelta(hours=5+i)).isoformat(),
                "forecast_sha256":"old_immutable_"+str(i)}
            ledger["records"][rec["id"]]=rec
        immutable_copy=json.loads(json.dumps(ledger))
        group=top3_empty()
        self.assertEqual(select_groups(group,ledger,NOW)["created"],1)
        self.assertEqual(ledger,immutable_copy)
        chosen=group["records"][NOW.date().isoformat()]["picks"]
        self.assertEqual(len(chosen),3)
        self.assertTrue(all(v["rank_provenance"]==
            "legacy-first-seen-probability-margin-v1" for v in chosen))
        self.assertEqual(set(v["id"] for v in chosen),
                         {"22202","22203","22204"})
    def test_encrypted_lineup_sidecar_from_existing_first_seen_score(self):
        index=sample_history()
        event=fixture(99888,NOW+timedelta(hours=8))
        archive=empty()
        self.assertEqual(capture(archive,[event],index,DummyDC(),NOW,
                                 advanced_model=train_advanced(index),
                                 clock=lambda:NOW)["captured"],1)
        score=archive["records"][str(event["id"])]["score"][:]
        baseline_sha=archive["records"][str(event["id"])]["forecast_sha256"]
        class LineupClient:
            requests_made=0
            max_requests=15
            def get_json(self,path,ttl=0):
                self.requests_made+=1
                return {"lineup_status":"confirmed",
                        "unavailable_players":{"home":[1,2],"away":[3]}}
        obs=obs_empty()
        stats=obs_capture(obs,[event],archive,LineupClient(),NOW,
                          clock=lambda:NOW,max_lookups=3)
        self.assertEqual(stats["captured"],1)
        self.assertEqual(len(obs["records"]),1)
        evidence=obs["records"][str(event["id"])]
        self.assertTrue(obs_valid(evidence))
        self.assertEqual(archive["records"][str(event["id"])]["score"],score)
        self.assertEqual(archive["records"][str(event["id"])]["forecast_sha256"],baseline_sha)
        finished=fixture(event["id"],NOW+timedelta(hours=8),
                        score=tuple(score),finished=True)
        self.assertEqual(settle(archive,[finished],NOW+timedelta(days=1))["settled"],1)
        learned=learn_absence(archive,NOW+timedelta(days=1),obs)
        self.assertEqual(learned["diagnostic"]["eligible"],1)
        # An older immutable forecast with no advanced xG baseline must not
        # secretly enter training using an invented expected-goal baseline.
        legacy=json.loads(json.dumps(archive))
        legacy["records"][str(event["id"])]["advanced_research"]=None
        self.assertEqual(learn_absence(legacy,NOW+timedelta(days=1),obs)
                         ["diagnostic"]["eligible"],0)
        obs["records"][str(event["id"])]["forecast_digest"]="WRONG"
        self.assertEqual(learn_absence(archive,NOW+timedelta(days=1),obs)
                         ["diagnostic"]["eligible"],0)
        obs["records"][str(event["id"])]["forecast_digest"]=baseline_sha
        secret=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as t:
            fn=Path(t)/"lineups.enc.json"
            obs_save(obs,fn,secret)
            self.assertEqual(obs_read(fn,secret),obs)
            self.assertNotIn("confirmed",fn.read_text())
    def test_top3_integrity_checks_real_first_seen_scores(self):
        ledger={"records":{}}
        for i in range(3):
            key=str(72000+i)
            ledger["records"][key]={"id":key,"status":"pending",
                "score":[1,0],"selection_rank":.2+i*.01,
                "rank_version":RANK_VERSION,
                "captured_at":NOW.isoformat(),
                "kickoff":(NOW+timedelta(hours=3+i)).isoformat(),
                "forecast_sha256":"firstseen_"+key}
        frozen=top3_empty()
        self.assertEqual(select_groups(frozen,ledger,NOW)["created"],1)
        self.assertEqual(verify_top3(frozen,ledger,NOW)["verified_baskets"],1)
        self.assertEqual(top3_report(frozen,NOW)["pending_baskets"],1)
        self.assertEqual(top3_report(frozen,NOW+timedelta(days=2))
                         ["overdue_unsettled_baskets"],1)
        ledger["records"]["72002"]["score"]=[0,2]
        with self.assertRaises(ValueError):
            verify_top3(frozen,ledger,NOW)
    def test_top3_settlement_monitoring_histogram(self):
        ledger={"records":{}}
        for i in range(3):
            key=str(72100+i)
            ledger["records"][key]={"id":key,"status":"pending",
                "score":[0,1],"selection_rank":.2+i*.01,
                "rank_version":RANK_VERSION,
                "captured_at":NOW.isoformat(),
                "kickoff":(NOW+timedelta(hours=3+i)).isoformat(),
                "forecast_sha256":"firstseen_"+key}
        group=top3_empty()
        select_groups(group,ledger,NOW)
        self.assertEqual(settle_groups(group,ledger,NOW)["pending"],1)
        for i,match in enumerate(ledger["records"].values()):
            match["status"]="settled"
            match["actual_score"]=[0,1] if i<2 else [2,0]
        self.assertEqual(settle_groups(group,ledger,NOW+timedelta(days=1))
                         ["settled"],1)
        self.assertEqual(verify_top3(group,ledger,NOW+timedelta(days=1))
                         ["verified_baskets"],1)
        report=top3_report(group,NOW+timedelta(days=1))
        self.assertEqual(report["settled_hit_distribution"]["2"],1)
        self.assertEqual(report["settled_selected_match_hits"],2)
    def test_score_void_cancels_basket_without_counting_as_loss(self):
        idx=sample_history()
        archive=empty()
        events=[fixture(60000+i,NOW+timedelta(hours=4+i)) for i in range(3)]
        self.assertEqual(capture(archive,events,idx,DummyDC(),NOW,clock=lambda:NOW)["captured"],3)
        basket=top3_empty()
        self.assertEqual(select_groups(basket,archive,NOW)["created"],1)
        cancelled=fixture(60000,NOW+timedelta(hours=4))
        cancelled["status"]="cancelled"
        self.assertEqual(settle(archive,[cancelled],NOW)["void"],1)
        self.assertEqual(summary(archive,NOW)["void"],1)
        self.assertEqual(settle_groups(basket,archive,NOW)["void"],1)
        self.assertEqual(top3_report(basket,NOW)["void_baskets"],1)
        self.assertEqual(verify_top3(basket,archive,NOW)["verified_baskets"],1)
    def test_changed_kickoff_invalidates_original(self):
        idx=sample_history()
        archive=empty()
        f=fixture(60100,NOW+timedelta(hours=3))
        capture(archive,[f],idx,DummyDC(),NOW,clock=lambda:NOW)
        rescheduled=fixture(60100,NOW+timedelta(hours=5))
        self.assertEqual(settle(archive,[rescheduled],NOW)["void"],1)
        self.assertEqual(archive["records"]["60100"]["void_reason"],
                         "kickoff_rescheduled_over_90_minutes")
    def test_archived_model_params_migrate_without_changing_forecasts(self):
        idx=sample_history();archive=empty()
        f=fixture(60200,NOW+timedelta(hours=6))
        capture(archive,[f],idx,DummyDC(),NOW,clock=lambda:NOW)
        archive["model"]={**archive["model"],"future_parameter_not_used":.713}
        secret=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"single.enc.json"
            save(archive,path,secret)
            self.assertEqual(read(path,secret),archive)
    def test_top3_rank_version_mixed_is_comparable_and_no_lookahead(self):
        from single_exact_score_top3 import _candidate
        row={"id":"700","status":"pending","score":[1,1],
             "estimated_probability":.15,"score_margin":.02,
             "kickoff":(NOW+timedelta(hours=6)).isoformat(),
             "captured_at":NOW.isoformat(),"forecast_sha256":"old"}
        a=_candidate(row,NOW)
        row["selection_rank"]=.99
        row["rank_version"]="old-irrelevant"
        self.assertEqual(_candidate(row,NOW)["selection_rank"],a["selection_rank"])
        self.assertEqual(a["rank_provenance"],RANK_VERSION)
    def test_top3_cutoff_prevents_early_frozen_selection(self):
        ledger={"records":{}}
        for i in range(3):
            t=NOW+timedelta(hours=5+i)
            ledger["records"][str(i)]={"id":str(i),"status":"pending","score":[1,1],
                "estimated_probability":.17,"score_margin":.02,
                "kickoff":t.isoformat(),"captured_at":NOW.isoformat()}
        group=top3_empty()
        self.assertEqual(select_groups(group,ledger,NOW,enforce_cutoff=True)["created"],0)
        at=NOW+timedelta(minutes=15)
        self.assertEqual(select_groups(group,ledger,at,enforce_cutoff=True)["created"],1)
    def test_top3_settlement_verification_rejects_modified_hit_count(self):
        ledger={"records":{}}
        for i in range(3):
            k=str(71000+i)
            ledger["records"][k]={"id":k,"status":"pending","score":[1,1],
                "estimated_probability":.17,"score_margin":.02,
                "kickoff":(NOW+timedelta(hours=5+i)).isoformat(),
                "captured_at":NOW.isoformat(),"forecast_sha256":"h"+k}
        group=top3_empty()
        select_groups(group,ledger,NOW)
        for row in ledger["records"].values():
            row["status"]="settled";row["actual_score"]=[1,1]
        settle_groups(group,ledger,NOW+timedelta(days=1))
        item=next(iter(group["records"].values()))
        item["hits"]=1
        with self.assertRaises(ValueError):
            verify_top3(group,ledger,NOW+timedelta(days=1))
    def test_empty_backtest_no_false_accuracy(self):
        empty_report=compare([],year=2026,dc_model=DummyDC())
        self.assertEqual(empty_report["eligible"],0)
        self.assertIsNone(empty_report["variants"]["under25_fusion"]["top1_rate"])
        self.assertEqual(empty_report["variants"]["under25_fusion"]["matches"],0)
if __name__=="__main__":unittest.main()
