"""Strict isolated tests for observed 1xBet correct-score groups and BSD DC gate."""
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cryptography.fernet import Fernet

sys.path.insert(0,str(Path(__file__).parent))
from grouped_correct_score import (GROUPS,OBSERVED_EXAMPLE,MARKET,
 normalize_scores,group_probability,group_hit,direction_probabilities,
 double_chance_direction,evaluate_groups,template_groups,validate_1xbet_snapshot)
from grouped_correct_score_engine import analyze,selection_summary
from grouped_correct_score_prospective import (empty,capture,settle,report,save,read)
from grouped_correct_score_feed import group_feed
from grouped_correct_score_backtest import run
from bsd_v2_core import V2History
from exact_scores import matrix_for
from exact_scores_h2h import H2HIndex

NOW=datetime(2026,10,20,12,0,tzinfo=timezone.utc)
def fixture(i,when,home=10,away=20,finished=False,score=None):
    return {"id":i,"event_date":when.isoformat(),"home_team_id":home,
            "away_team_id":away,"home_team":{"id":home,"name":"Équipe A"},
            "away_team":{"id":away,"name":"Équipe B"},
            "league_id":99,"league_name":"Test Ligue",
            "home_score":score[0] if score else None,
            "away_score":score[1] if score else None,
            "status":"finished" if finished else "notstarted"}
def history():
    x=[]
    for i in range(7):
        at=NOW-timedelta(days=90-i*11)
        x.append(fixture(100+i,at,home=10,away=55,finished=True,score=(1,0)))
        x.append(fixture(200+i,at,home=66,away=20,finished=True,score=(0,1)))
    for i in range(3):
        x.append(fixture(300+i,NOW-timedelta(days=75-i*17),
                         finished=True,score=(1,0)))
    return V2History(x)
class StubDC:
    blend=.5
    def predict(self,fixture,index,prior):
        return (.58,.27,.15)
class CatalogTests(unittest.TestCase):
    def test_nine_groups_are_different_and_1xbet_patterns(self):
        self.assertEqual(len(GROUPS),9)
        self.assertEqual(GROUPS["G1"],((0,0),(1,0),(0,1)))
        self.assertEqual(GROUPS["G4"],((1,0),(2,0),(3,0)))
        self.assertEqual(len({tuple(v) for v in GROUPS.values()}),9)
        self.assertTrue(all(len(g)==3 for g in GROUPS.values()))
    def test_overlapping_groups_do_not_form_outcomes_partition(self):
        matrix=matrix_for(1.35,1.1)
        self.assertIn((1,0),GROUPS["G1"])
        self.assertIn((1,0),GROUPS["G4"])
        self.assertGreater(group_probability(matrix,GROUPS["G1"]),matrix[(1,0)])
        self.assertGreater(sum(group_probability(matrix,v) for v in GROUPS.values()),
                           0.3)
    def test_exact_group_wins_for_any_member_only(self):
        self.assertTrue(group_hit(GROUPS["G4"],(3,0)))
        self.assertFalse(group_hit(GROUPS["G4"],(1,1)))
        self.assertTrue(group_hit(GROUPS["G1"],(0,0)))
    def test_cannot_repeat_scores_in_one_group(self):
        with self.assertRaises(ValueError):
            normalize_scores(["1-0","1-0"])
    def test_missing_bookmaker_odds_must_never_be_guessed(self):
        a=evaluate_groups(matrix_for(1.5,.9),template_groups())
        self.assertEqual(len(a),9)
        self.assertTrue(all(r["odds"] is None and
                            r["expected_value"] is None and
                            not r["quote_documented"] for r in a))
    def test_group_probability_matches_sum(self):
        m=matrix_for(1.5,.9)
        self.assertAlmostEqual(group_probability(m,["1-0","2-0","3-0"]),
                               m[1,0]+m[2,0]+m[3,0])
class StatisticalIntegrityTests(unittest.TestCase):
    def test_wilson_bounds_without_false_certainty(self):
        from grouped_correct_score_backtest import wilson95,metrics,new_bucket
        self.assertIsNone(wilson95(0,0))
        lo,hi=wilson95(65,122)
        self.assertGreater(lo,.44)
        self.assertLess(hi,.62)
        self.assertLess(lo,65/122)
        self.assertGreater(hi,65/122)
        tiny=new_bucket()
        self.assertTrue(metrics(tiny,16257)["small_sample"])
        self.assertIsNone(metrics(tiny,16257)["hit_rate"])
    def test_same_population_baseline_policy(self):
        from grouped_correct_score_backtest import metrics,new_bucket
        b=new_bucket()
        b.update({"n":122,"hits":65,"sum_p":50.08})
        r=metrics(b,16257)
        self.assertEqual(r["wins"],65)
        self.assertEqual(r["coverage"],round(122/16257,6))
        self.assertFalse(r["small_sample"])

class DirectionTests(unittest.TestCase):
    def test_home_one_x_is_not_home_win_only(self):
        d=double_chance_direction({"1":.56,"X":.29,"2":.15})
        self.assertEqual(d["direction"],"home")
        self.assertEqual(d["double_chance"],"1X")
        self.assertIn("X",d["allowed_outcomes"])
        self.assertNotIn("2",d["allowed_outcomes"])
    def test_away_two_x_is_not_away_win_only(self):
        d=double_chance_direction({"1":.13,"X":.28,"2":.59})
        self.assertEqual(d["direction"],"away")
        self.assertEqual(d["double_chance"],"X2")
        self.assertNotIn("1",d["allowed_outcomes"])
    def test_draw_dominant_prevents_wrong_home_assumption(self):
        d=double_chance_direction({"1":.25,"X":.48,"2":.27})
        self.assertEqual(d["direction"],"draw")
        self.assertEqual(d["allowed_outcomes"],("X",))
    def test_twelve_means_not_draw_not_some_side(self):
        d=double_chance_direction({"1":.41,"X":.18,"2":.41})
        self.assertEqual(d["double_chance"],"12")
        self.assertEqual(d["direction"],"neutral")
    def test_filter_rejects_opposite_side_group(self):
        m=matrix_for(1.6,.8)
        d=double_chance_direction({"1":.55,"X":.3,"2":.15})
        r={x["group_id"]:x for x in evaluate_groups(m,template_groups(),direction=d)}
        self.assertFalse(r["G2"]["direction_eligible"])
        self.assertTrue(r["G4"]["direction_eligible"])
class PriceAdapterTests(unittest.TestCase):
    def doc(self):
        return {"bookmaker":"1xbet","bsd_event_id":"800",
                "bookmaker_event_id":"756687632",
                "market":MARKET,"period":"FT",
                "kickoff_utc":(NOW+timedelta(days=1)).isoformat(),
                "captured_utc":NOW.isoformat(),
                "source_url":OBSERVED_EXAMPLE,
                "capture_reference":"synthetic-unit-test-screenshot",
                "selections":[{"group_id":"G4","scores":["1-0","2-0","3-0"],
                               "odds":2.3}]}
    def test_source_document_parses_and_enables_ev(self):
        doc=self.doc()
        arr=validate_1xbet_snapshot(doc,event_id=800,
             kickoff=NOW+timedelta(days=1),now=NOW)
        self.assertEqual(len(arr),1)
        self.assertEqual(arr[0]["quote_source"],"documented_1xbet_snapshot")
        group=evaluate_groups(matrix_for(1.5,.8),arr)[0]
        self.assertAlmostEqual(group["expected_value"],
                               round(group["probability"]*2.3-1,6),places=5)
    def test_refuse_wrong_match_and_market_and_bookmaker_url(self):
        for field,val in (("bsd_event_id","777"),("market","TOTO Correct Score"),
                          ("period","1H"),("source_url","https://example.org/fake"),
                          ("bookmaker_event_id","123")):
            doc=self.doc()
            doc[field]=val
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_1xbet_snapshot(doc,event_id=800,
                      kickoff=NOW+timedelta(days=1),now=NOW)
    def test_refuse_postmatch_quotes_and_wrong_kickoff(self):
        a=self.doc();a["captured_utc"]=(NOW+timedelta(days=2)).isoformat()
        with self.assertRaises(ValueError):
            validate_1xbet_snapshot(a,event_id=800,
                kickoff=NOW+timedelta(days=1),now=NOW+timedelta(days=2))
        b=self.doc();b["kickoff_utc"]=(NOW+timedelta(days=3)).isoformat()
        with self.assertRaises(ValueError):
            validate_1xbet_snapshot(b,event_id=800,
                kickoff=NOW+timedelta(days=1),now=NOW)
    def test_reject_score_alteration_or_bad_odds(self):
        for value in (0,True,-1,1001):
            doc=self.doc();doc["selections"][0]["odds"]=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_1xbet_snapshot(doc,event_id=800,
                      kickoff=NOW+timedelta(days=1),now=NOW)
        b=self.doc();b["selections"][0]["scores"]=["1-0","2-0","4-0"]
        with self.assertRaises(ValueError):
            validate_1xbet_snapshot(b,event_id=800,
                kickoff=NOW+timedelta(days=1),now=NOW)
    def test_explicit_dynamic_group_accepts_documented_fixture_variation(self):
        doc=self.doc()
        doc["market_variant"]="per_fixture_grouping"
        doc["selections"]=[{"group_id":"XBET_A1",
                            "scores":["0-0","1-0","2-0","3-0"],"odds":2.8}]
        rows=validate_1xbet_snapshot(doc,event_id=800,
             kickoff=NOW+timedelta(days=1),now=NOW)
        self.assertEqual(rows[0]["group_id"],"XBET_A1")
        self.assertEqual(len(rows[0]["scores"]),4)
        self.assertTrue(rows[0]["dynamic_group"])
        m=matrix_for(1.6,.9)
        values=evaluate_groups(m,rows)
        self.assertAlmostEqual(values[0]["probability"],
             round(m[(0,0)]+m[(1,0)]+m[(2,0)]+m[(3,0)],7),places=7)

    def test_dynamic_group_requires_explicit_market_variant(self):
        doc=self.doc()
        doc["selections"]=[{"group_id":"XBET_A1","scores":["0-0","1-0"],
                             "odds":2.8}]
        with self.assertRaises(ValueError):
            validate_1xbet_snapshot(doc,event_id=800,
                kickoff=NOW+timedelta(days=1),now=NOW)

    def test_missing_bookmaker_quote_cannot_produce_live_site_feed(self):
        result,why=analyze(fixture(900,NOW+timedelta(days=1)),history(),
                           H2HIndex(history()),StubDC(),now=NOW)
        self.assertEqual(why,"ok")
        self.assertTrue(all(not p["quote_documented"] for p in result["groups"]))
        self.assertIsNone(selection_summary(result)["with_verified_price"])
    def test_priority_research_without_quote_does_not_invent_value(self):
        g={"group_id":"G4","scores":[[1,0],[2,0],[3,0]],
           "probability":.28,"direction_eligible":True,
           "tier":"recherche_prioritaire","odds":None,"expected_value":None}
        selections=selection_summary({"groups":[g]})
        self.assertEqual(selections["with_h2h_under"]["group_id"],"G4")
        self.assertIsNone(selections["with_verified_price"])

class ProspectiveGroupTests(unittest.TestCase):
    def test_shadow_capture_then_settle_without_recomputing(self):
        led=empty();idx=history()
        new=fixture(981,NOW+timedelta(days=1))
        n=capture(led,[new],idx,StubDC(),now=NOW)
        self.assertEqual(n["captured"],1)
        row=led["predictions"]["981"]
        sha=row["forecast_sha256"]
        self.assertEqual(capture(led,[new],idx,StubDC(),
             now=NOW+timedelta(hours=1))["captured"],0)
        self.assertEqual(row["forecast_sha256"],sha)
        done=fixture(981,NOW+timedelta(days=1),finished=True,score=(1,0))
        self.assertEqual(settle(led,[done],NOW+timedelta(days=1,hours=3)),{})
        self.assertEqual(settle(led,[done],NOW+timedelta(days=1,hours=5)),{"settled":1})
        self.assertEqual(row["forecast_sha256"],sha)
        self.assertIsInstance(row["results"]["baseline"],int)
        self.assertEqual(report(led,NOW)["settled"],1)
    def test_group_encrypted_ledger_roundtrip_and_tamper_detection(self):
        led=empty();idx=history()
        capture(led,[fixture(982,NOW+timedelta(days=1))],idx,StubDC(),now=NOW)
        key=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"ledger.enc.json";save(led,p,key)
            self.assertNotIn('"groups"',p.read_text(encoding="utf-8"))
            self.assertEqual(read(p,key),led)
            r=read(p,key);r["predictions"]["982"]["groups"][0]["probability"]=.99
            with self.assertRaises(ValueError):
                save(r,p,key)
    def test_group_site_feed_keeps_unquoted_match_private(self):
        led=empty()
        capture(led,[fixture(985,NOW+timedelta(days=1))],
                history(),StubDC(),now=NOW)
        view=group_feed(led,now=NOW)
        self.assertFalse(view["published"])
        self.assertEqual(view["matches"],[])
    def test_empty_historical_backtest_safe(self):
        out=run([])
        self.assertEqual(out["eligible"],0)
        self.assertEqual(out["variants"]["with_double_chance"]["n"],0)

class ExpandedGoalBandsTests(unittest.TestCase):
    def test_cumulative_probability_is_monotone_to_seven(self):
        from grouped_total_goals import goal_profile,CEILINGS
        matrix=matrix_for(1.5,1.1)
        profile=goal_profile(matrix)
        cdf=[profile["under_probabilities"][f"under_{n}5"] for n in CEILINGS]
        self.assertEqual(len(cdf),6)
        self.assertTrue(all(0<=a<=b<=1 for a,b in zip(cdf,cdf[1:])))
        self.assertAlmostEqual(sum(profile["exclusive_goal_bands"].values()),1,places=5)
        self.assertAlmostEqual(cdf[0],sum(p for (h,a),p in matrix.items() if h+a<=2),places=6)
    def test_high_goal_away_group_can_enter_under_seven(self):
        from grouped_total_goals import goal_profile,select_for_ceiling
        # High scoring synthetic match: G7 (2-3 / 2-4 / 3-4) rather than G1.
        matrix={(0,0):.05,(1,0):.10,(2,3):.30,(2,4):.30,(3,4):.25}
        profile=goal_profile(matrix)
        self.assertIsNone(profile["smallest_eligible_max_goals"] if False else None)
        self.assertEqual(profile["smallest_eligible_max_goals"],6)
        self.assertFalse(profile["eligible_ceiling"]["under_45"])
        self.assertTrue(profile["eligible_ceiling"]["under_65"])
        options=evaluate_groups(matrix,template_groups(),
                 direction=double_chance_direction({"1":.1,"X":.05,"2":.85}))
        picked=select_for_ceiling(options,profile,matrix,6)
        self.assertIsNotNone(picked)
        self.assertEqual(picked[0]["group_id"],"G7")
        self.assertIsNone(select_for_ceiling(options,profile,matrix,4))
    def test_group_not_resized_to_goal_ceiling_and_probabilities_not_inflated(self):
        from grouped_total_goals import goal_profile,select_for_ceiling
        matrix=matrix_for(1.2,.8)
        profile=goal_profile(matrix)
        groups=evaluate_groups(matrix,template_groups(),
                 direction=double_chance_direction({"1":.6,"X":.28,"2":.12}))
        chosen=select_for_ceiling(groups,profile,matrix,7)
        self.assertIsNotNone(chosen)
        group,share=chosen
        self.assertEqual(group["scores"],[list(x) for x in GROUPS[group["group_id"]]])
        self.assertAlmostEqual(group["probability"],
                 group_probability(matrix,group["scores"]),places=6)
        self.assertIsNone(group["odds"])
        self.assertIsNone(group["expected_value"])
    def test_invalid_matrix_and_invalid_limit_rejected(self):
        from grouped_total_goals import cumulative_goals,goal_profile,select_for_ceiling
        with self.assertRaises(ValueError):goal_profile({(0,0):.8})
        with self.assertRaises(ValueError):goal_profile({(0,0):1.1,(1,0):-.1})
        with self.assertRaises(ValueError):
            select_for_ceiling([],goal_profile({(0,0):1.0}),8)
    def test_grouped_analysis_includes_six_screening_policies_without_book_odds(self):
        fixture_obj=fixture(989,NOW+timedelta(days=1))
        idx=history()
        pred,reason=analyze(fixture_obj,idx,H2HIndex(idx),StubDC(),now=NOW)
        self.assertEqual(reason,"ok")
        self.assertEqual(len(pred["ceiling_choices"]),6)
        choices=selection_summary(pred)
        self.assertIn("ceiling_under_75",choices)
        self.assertIn("with_h2h_under",choices)
        self.assertTrue(all(g["odds"] is None for g in pred["groups"]))
    def test_archived_legacy_forecast_without_ceiling_keys_still_valid(self):
        from grouped_correct_score_prospective import report
        led=empty()
        capture(led,[fixture(989,NOW+timedelta(days=1))],history(),StubDC(),now=NOW)
        row=led["predictions"]["989"]
        self.assertIn("goals_profile",row)
        self.assertIn("ceiling_under_75",row["rules"])
        # First-seen snapshots predating this module contain no ceiling keys.
        del row["goals_profile"]
        for k in tuple(row["rules"]):
            if k.startswith("ceiling_"):del row["rules"][k]
        from grouped_correct_score_prospective import digest
        row["forecast_sha256"]=digest(row)
        self.assertIn("ceiling_under_75",report(led,NOW)["policies"])

if __name__=="__main__":
    unittest.main()
