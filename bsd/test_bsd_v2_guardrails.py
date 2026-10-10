"""Regression tests for BSD V2 winning guardrails."""
import unittest
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from unittest.mock import patch

from bsd_markets import candidates_from_goals
from bsd_v2_core import V2History, choose_market, markets_from_matrix, score_matrix, predict_v2
from bsd_v2_guardrails import (
    POLICY_VERSION, MIN_CONSERVATIVE_BY_FAMILY, post_price_value_guard,
    update_performance_tracker, tracker_penalties,
)
from bsd_v2_publish import assemble
from bsd_v2_settlement_watchdog import apply_watchdog


class GuardrailTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,10,10,tzinfo=timezone.utc)

    def test_real_odds_are_final_veto_not_selector(self):
        pick={"market":"double_chance","selection_key":"1X","odds_source":"bsd_consensus",
              "bookmaker_odds":1.20,"conservative_probability":.80}
        result=post_price_value_guard(pick)
        self.assertTrue(result["checked"])
        self.assertFalse(result["passed"])  # 1/1.20 + 1.8 pts > 80 %

        pick["conservative_probability"]=.86
        result=post_price_value_guard(pick)
        self.assertTrue(result["passed"])

    def test_estimated_price_is_not_independent_value_evidence(self):
        result=post_price_value_guard({
            "market":"goals","selection_key":"OVER_15","odds_source":"mrxpronos_model",
            "bookmaker_odds":1.25,"conservative_probability":.72})
        self.assertFalse(result["checked"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["reason"],"estimated_price_not_independent")

    def test_double_chance_has_75pct_conservative_floor(self):
        original=next(x for x in markets_from_matrix(score_matrix(1.6,1.0)) if x.key=="1X")
        marginal=replace(original,probability=.755)
        choice,_=choose_market([marginal],min_probability=.70,league_samples=100,form_samples=10,
                               family_minimums=MIN_CONSERVATIVE_BY_FAMILY)
        self.assertIsNone(choice)
        strong=replace(original,probability=.78)
        choice,_=choose_market([strong],min_probability=.70,league_samples=100,form_samples=10,
                               family_minimums=MIN_CONSERVATIVE_BY_FAMILY)
        self.assertIsNotNone(choice)

    def test_drift_penalty_stays_zero_before_minimum_sample(self):
        rows=[]
        for i in range(99):
            rows.append({"id":"bsd:%d"%i,"event_date":"2026-10-01T10:00:00+00:00",
                         "is_finished":True,"verified_prediction":i%2==0,
                         "prediction":{"selection_key":"OVER_15","market":"over_under_15",
                                       "confidence":90}})
        tracker=update_performance_tracker(None,rows,now=self.now)
        by_key,by_family=tracker_penalties(tracker)
        self.assertEqual(by_key["OVER_15"],0.)
        self.assertEqual(by_family["goals"],0.)

    def test_drift_penalty_activates_slowly_after_100_samples(self):
        rows=[]
        for i in range(120):
            rows.append({"id":"bsd:%d"%i,"event_date":"2026-10-01T10:00:00+00:00",
                         "is_finished":True,"verified_prediction":i%2==0,
                         "prediction":{"selection_key":"OVER_15","market":"over_under_15",
                                       "confidence":90}})
        tracker=update_performance_tracker(None,rows,now=self.now)
        by_key,by_family=tracker_penalties(tracker)
        self.assertGreater(by_key["OVER_15"],0.)
        self.assertLessEqual(by_key["OVER_15"],.08)
        self.assertGreater(by_family["goals"],0.)

    def test_tracker_never_counts_unsettled(self):
        tracker=update_performance_tracker(None,[{
            "id":"bsd:1","event_date":"2026-10-01T10:00:00+00:00",
            "is_finished":False,"status":"settlement_pending",
            "prediction":{"selection_key":"OVER_15","market":"over_under_15","confidence":90}
        }],now=self.now)
        self.assertEqual(tracker["by_selection"],{})

    def test_watchdog_marks_unresolved_and_settles_finished(self):
        kickoff=self.now-timedelta(hours=13)
        base={"source":"bsd","model_version":"bsd-v2-isolated","matches":[
            {"id":"bsd:1","source":"bsd","source_event_id":1,"event_date":kickoff.isoformat(),
             "status":"notstarted","is_finished":False,
             "prediction":{"selection_key":"OVER_15","confidence":80}},
            {"id":"bsd:2","source":"bsd","source_event_id":2,"event_date":kickoff.isoformat(),
             "status":"notstarted","is_finished":False,
             "prediction":{"selection_key":"OVER_15","confidence":80}},
        ]}
        event={"id":1,"status":"finished","event_date":kickoff.isoformat(),
               "home_score":1,"away_score":1}
        out=apply_watchdog(base,{"1":event},now=self.now,detail_fetcher=lambda _id:None)
        rows={x["source_event_id"]:x for x in out["matches"]}
        self.assertTrue(rows[1]["is_finished"])
        self.assertTrue(rows[1]["verified_prediction"])
        self.assertEqual(rows[2]["status"],"settlement_pending")
        self.assertTrue(rows[2]["settlement_pending"])

    def test_saved_future_pick_can_be_retired_but_never_substituted(self):
        kickoff=self.now+timedelta(hours=5)
        original={"source":"bsd","matches":[{
            "id":"bsd:17","source":"bsd","source_event_id":17,
            "event_date":kickoff.isoformat(),"status":"notstarted","is_finished":False,
            "model_version":"bsd-v2-isolated",
            "prediction":{"selection_key":"1X","odds":1.30,"odds_source":"bsd_consensus",
                          "estimated_odds":False}
        }]}
        fixture={"id":17,"event_date":kickoff.isoformat(),"status":"notstarted",
                 "home_team_id":1,"away_team_id":2,"league_id":9,
                 "home_team":"A","away_team":"B"}
        history=[{"id":i+100,"event_date":(self.now-timedelta(days=20-i)).isoformat(),
                  "status":"finished","home_team_id":1,"away_team_id":2,"league_id":9,
                  "home_score":1,"away_score":0} for i in range(12)]
        recheck={"ranked_candidates":[{"key":"OVER_15","passes_quality_policy":True}]}
        with patch("bsd_v2_publish.predict_v2",return_value=(recheck,"ok")):
            out=assemble(original,[fixture],history,now=self.now,calibration=None,
                         policy=None,rho=0,odds_fetcher=lambda *_:({},{}))
        self.assertEqual(out["matches"],[])
        self.assertEqual(len(out["retired_predictions"]),1)
        self.assertEqual(out["retired_predictions"][0]["selection_key"],"1X")
        self.assertEqual(out["retired_predictions"][0]["retired_policy_version"],POLICY_VERSION)

    def test_over15_is_removed_when_models_disagree_by_more_than_7_points(self):
        future={"id":99,"event_date":(self.now+timedelta(hours=5)).isoformat(),
                "status":"notstarted","home_team_id":1,"away_team_id":2,"league_id":9}
        history=[]
        for i in range(35):
            history.append({"id":i+1,"event_date":(self.now-timedelta(days=40-i)).isoformat(),
                            "status":"finished","home_team_id":1 if i%2 else 2,
                            "away_team_id":2 if i%2 else 1,"league_id":9,
                            "home_score":1+(i%2),"away_score":i%2})
        index=V2History(history)
        class Dummy:
            blend=1.
        def disagree(event,index,candidates,model):
            out=[]
            for c in candidates:
                if c.key=="OVER_15":
                    out.append(replace(c,probability=max(.01,c.probability-.20)))
                else:
                    out.append(c)
            return out
        audit=[]
        with patch("bsd_v2_over_under.adjust_candidates",side_effect=disagree),              patch("bsd_v2_over_under.uncertainty",return_value=None):
            pred,reason=predict_v2(future,index,total_model=Dummy(),market_audit=audit)
        self.assertEqual(reason,"ok")
        self.assertTrue(any(x.get("result")=="over15_models_disagree" for x in audit))
        keys={x["key"] for x in pred["ranked_candidates"]}
        self.assertNotIn("OVER_15",keys)


if __name__=="__main__":
    unittest.main()
