"""Prospective risk brakes and fair paired evaluation are tested without credentials."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from bsd_v3.registry import append_once
from bsd_v3.monitor import monitor,wilson_interval
from bsd_v3.legacy import V2History,score_matrix,markets_from_matrix
from bsd_v3.selection import serialize_candidates
from bsd_v3.comparison import compare_all_markets

UTC=timezone.utc

def fixture(i,home,away,date,hs,aws):
    return {"id":i,"home_team_id":home,"away_team_id":away,
            "league_id":7,"status":"finished","event_date":date.isoformat(),
            "home_score":hs,"away_score":aws}

class MonitorTests(unittest.TestCase):
    def test_market_drift_disables_only_observed_overconfident_key(self):
        root=Path.cwd()/"bsd_v3"/"artifacts"
        root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as location:
            path=Path(location)/"ledger.jsonl"
            for i in range(5):
                eid=str(100+i)
                snapshot={"event_id":eid,
                          "kickoff_utc":"2026-11-06T15:00:00+00:00",
                          "league_key":"id:7",
                          "candidates":[{"key":"1","family":"result",
                                         "probability":.92,"quote":None}],
                          "selections":{"pro_vip_shadow":["1"],
                                        "value_shadow":[]}}
                settled={"event_id":eid,"markets":{"1":{"won":False,"settled":True,
                                                        "return_per_unit":None}}}
                append_once(path,"forecast",eid,snapshot)
                append_once(path,"settlement",eid,settled)
            report=monitor(path,min_samples=5)
            self.assertEqual(report["forecasts"],5)
            self.assertEqual(report["market_outcomes"],5)
            self.assertEqual(report["disabled_keys"],["1"])
            self.assertEqual(report["sections"]["pro_vip_shadow"]["1"]["n"],5)
            self.assertIsNone(report["sections"]["market"]["1"]["paper_roi_named_bookmaker"])
            self.assertEqual(report["sections"]["market"]["1"]["wins"],0)

    def test_blacklist_does_not_remove_audited_candidates(self):
        matrix=score_matrix(1.4,1.1)
        candidates=markets_from_matrix(matrix)
        features={"home_recent_matches":12,"away_recent_matches":12,
                  "league_samples":150,"home_venue_matches":6,
                  "away_venue_matches":6}
        quality={"level":"full","league_games":150,"venue_games":6,"recent_games":12}
        rows=serialize_candidates(candidates,features,quality,{},blocked_keys={"OVER_15"})
        self.assertEqual(len(rows),16)
        over=next(r for r in rows if r["key"]=="OVER_15")
        self.assertEqual(over["decision"]["disabled_reason"],"prospective_calibration_drift")
        self.assertFalse(over["decision"]["pro_vip_shadow"])
        self.assertFalse(over["decision"]["value_shadow"])

    def test_interval_is_bounded(self):
        for wins,n in ((0,100),(100,100),(50,100)):
            low,high=wilson_interval(wins,n)
            self.assertTrue(0<=low<=high<=1)

class RetrospectiveComparisonTests(unittest.TestCase):
    def test_paired_models_evaluate_same_finished_fixtures(self):
        start=datetime(2025,9,1,tzinfo=UTC)
        archive=[fixture(i+1,1 if i%2==0 else 2,
                         2 if i%2==0 else 1,
                         start+timedelta(days=i*3),
                         i%4,(i+1)%3)
                 for i in range(45)]
        anchor=datetime(2026,1,18,tzinfo=UTC)
        archive += [fixture(1000+i,1 if i%2==0 else 2,
                            2 if i%2==0 else 1,
                            anchor+timedelta(days=i*3),
                            i%3,(i+2)%3)
                    for i in range(12)]
        models={"goals":None,"result":None,"btts":None}
        with patch("bsd_v3.comparison.build_models",return_value=(
                models,None,None,{"stub_no_historical_training":True})):
            report=compare_all_markets(archive,max_matches=10)
        self.assertEqual(report["fixtures_examined"],10)
        self.assertGreater(report["coverage"]["paired_fixtures"],0)
        self.assertEqual(len(report["markets"]),16)
        self.assertIsNone(report["real_bookmaker_roi"])
        for name,stat in report["markets"].items():
            self.assertAlmostEqual(stat["v2_brier"],stat["v3_brier"],places=3)


class GoalStrengthGateTests(unittest.TestCase):
    def test_2026_results_do_not_change_2025_gate(self):
        from bsd_v3.goal_strength import fit_goal_strength,goal_strength
        base=datetime(2025,1,1,tzinfo=UTC)
        train=[fixture(i+1,1 if i%2 else 2,2 if i%2 else 1,
                       base+timedelta(days=i*3),i%4,(i+1)%3)
               for i in range(60)]
        valid=[fixture(200+i,1 if i%2 else 2,2 if i%2 else 1,
                       datetime(2025,9,1,tzinfo=UTC)+timedelta(days=i*3),
                       (i+1)%3,i%3)
               for i in range(25)]
        original=V2History(train+valid)
        extra=[fixture(800+i,1 if i%2 else 2,2 if i%2 else 1,
                       datetime(2026,3,1,tzinfo=UTC)+timedelta(days=i),
                       18 if i%2 else 0,0 if i%2 else 18)
               for i in range(10)]
        revised=V2History(train+valid+extra)
        before=fit_goal_strength(original,0.,min_train=20,min_validation=10)
        after=fit_goal_strength(revised,0.,min_train=20,min_validation=10)
        self.assertEqual(before.metadata(),after.metadata())
        self.assertGreater(before.validated,0)
        self.assertIn(before.alpha,(0.,.06,.12,.18,.24))
        test_event=fixture(901,1,2,datetime(2025,11,22,tzinfo=UTC),1,1)
        raw={"home":1.4,"away":1.1}
        first=goal_strength(test_event,original,raw,.12)
        second=goal_strength(test_event,revised,raw,.12)
        self.assertEqual(first,second)


class MonthlyPolicyBacktestTests(unittest.TestCase):
    def test_exact_month_replays_only_closed_matches_and_scores_current_policy(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from bsd_v3.monthly_backtest import monthly_policy_backtest
        oct1=fixture(5001,1,2,datetime(2026,10,5,tzinfo=UTC),2,0)
        oct2=fixture(5002,3,4,datetime(2026,10,6,tzinfo=UTC),1,1)
        sep=fixture(4999,1,2,datetime(2026,9,30,tzinfo=UTC),3,1)
        fake_index=SimpleNamespace(global_games=[
            (datetime(2026,9,30,tzinfo=UTC),sep),
            (datetime(2026,10,5,tzinfo=UTC),oct1),
            (datetime(2026,10,6,tzinfo=UTC),oct2),
        ])
        runtime={"index":fake_index,"calibration":None,"goal_strength":None}
        def fake_eval(event,runtime,now,policy):
            if str(event["id"])=="5001":
                rows=[
                    {"key":"1","probability":.76,"conservative_probability":.73},
                    {"key":"OVER_15","probability":.86,"conservative_probability":.83},
                ]
                picks=["1","OVER_15"]
            else:
                rows=[{"key":"BTTS_YES","probability":.74,
                       "conservative_probability":.71}]
                picks=["BTTS_YES"]
            return {"status":"analyzed","candidates":rows,
                    "selections":{"pro_vip_shadow":picks}}
        with patch("bsd_v3.monthly_backtest.train_runtime",return_value=runtime), \
             patch("bsd_v3.monthly_backtest.evaluate_fixture",side_effect=fake_eval):
            report=monthly_policy_backtest([sep,oct1,oct2],year=2026,month=10)
        self.assertEqual(report["fixtures_in_archive"],2)
        self.assertEqual(report["counts"]["fixtures_with_pick"],2)
        self.assertEqual(report["counts"]["selections"],3)
        self.assertEqual(report["counts"]["preferred_selections"],3)
        self.assertEqual(report["primary_by_market"]["1"]["wins"],1)
        self.assertEqual(report["primary_by_market"]["BTTS_YES"]["wins"],1)
        self.assertIsNone(report["real_bookmaker_roi"])

if __name__=="__main__":
    unittest.main()
