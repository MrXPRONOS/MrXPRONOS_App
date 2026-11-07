"""BSD V3 offline regression: no secrets, APIs, or paid dependencies."""
import unittest
from datetime import datetime,timedelta,timezone
from bsd_v3.legacy import V2History,markets_from_matrix,score_matrix
from bsd_v3.probabilities import coherent_candidates,prove_coherence,tilt_event
from bsd_v3.policy import V3Policy,label_candidate,public_candidate
from bsd_v3.quotes import validate_quote
from bsd_v3.selection import select_candidates,joint_event_probability
from bsd_v3.engine import evaluate_fixture

UTC=timezone.utc
def event(i,home,away,when,status="finished",hs=1,aws=0):
    return {"id":i,"home_team_id":home,"away_team_id":away,"league_id":7,
            "event_date":when.isoformat(),"status":status,
            "home_score":hs if status=="finished" else None,
            "away_score":aws if status=="finished" else None}

class TestV3(unittest.TestCase):
    def test_coherent_market_probabilities(self):
        for home,away in ((.4,.5),(1.4,1.2),(3.1,2.8)):
            matrix,rows=coherent_candidates({"home":home,"away":away})
            self.assertEqual(len(rows),16)
            self.assertTrue(prove_coherence(rows))
            self.assertAlmostEqual(sum(matrix.values()),1,places=9)

    def test_projection_keeps_monotonicity(self):
        matrix=score_matrix(1.5,1.1)
        projected=tilt_event(matrix,lambda s:sum(s)>2.5,.65)
        self.assertTrue(prove_coherence(markets_from_matrix(projected)))

    def test_correlation_not_independence(self):
        matrix,rows=coherent_candidates({"home":1.4,"away":1.2})
        p={c.key:{"key":c.key,"line":c.line,"probability":c.probability} for c in rows}
        self.assertAlmostEqual(joint_event_probability(matrix,p["BTTS_YES"],p["OVER_15"]),
                               p["BTTS_YES"]["probability"],places=8)

    def test_quote_consensus_is_benchmark_only(self):
        now=datetime(2026,11,6,12,tzinfo=UTC)
        raw={"odds":1.8,"bookmaker":"consensus","origin":"bsd_consensus",
             "captured_at":(now-timedelta(minutes=10)).isoformat(),
             "updated_at":(now-timedelta(minutes=15)).isoformat()}
        q,reason=validate_quote(raw,now=now,kickoff=now+timedelta(hours=3))
        self.assertEqual(reason,"ok")
        self.assertTrue(q["benchmark_only"])
        row={"key":"OVER_25","family":"goals","probability":.75,
             "conservative_probability":.72}
        self.assertFalse(label_candidate(row,{"level":"full"},q)["value_shadow"])
        named=dict(raw,origin="bsd_bookmaker",bookmaker="named-bookmaker")
        q,_=validate_quote(named,now=now,kickoff=now+timedelta(hours=3))
        self.assertTrue(label_candidate(row,{"level":"full"},q)["value_shadow"])
        self.assertIsNone(validate_quote(dict(raw,estimated=True),now=now,
                                         kickoff=now+timedelta(hours=3))[0])
        self.assertEqual(validate_quote(dict(raw,updated_at=(now-timedelta(hours=3)).isoformat()),
                                        now=now,kickoff=now+timedelta(hours=3))[1],"stale_quote")

    def test_preferred_markets_have_specific_reliability_floors(self):
        quality={"level":"full","league_games":45,"recent_games":10,"venue_games":4}
        home={"key":"1","family":"result","probability":.69,
              "conservative_probability":.67}
        self.assertFalse(public_candidate(home,quality))
        home.update(probability=.70,conservative_probability=.68)
        self.assertTrue(public_candidate(home,quality))
        away={"key":"2","family":"result","probability":.70,
              "conservative_probability":.68}
        self.assertTrue(public_candidate(away,quality))
        btts={"key":"BTTS_YES","family":"btts","probability":.70,
              "conservative_probability":.68}
        self.assertTrue(public_candidate(btts,quality))
        over={"key":"OVER_15","family":"goals","probability":.82,
              "conservative_probability":.80}
        self.assertTrue(public_candidate(over,quality))
        over["conservative_probability"]=.79
        self.assertFalse(public_candidate(over,quality))
        fallback={"key":"1X","family":"double_chance","probability":.79,
                  "conservative_probability":.774}
        self.assertFalse(public_candidate(fallback,quality))
        fallback["conservative_probability"]=.775
        self.assertTrue(public_candidate(fallback,quality))

    def test_two_selections_must_be_different_families(self):
        matrix,cs=coherent_candidates({"home":1.3,"away":1.1})
        rows=[]
        for c in cs:
            rows.append({"key":c.key,"family":c.family,"market":c.market,"line":c.line,
                         "probability":c.probability,"conservative_probability":c.probability,
                         "decision":{"pro_vip_shadow":c.key in {"OVER_15","UNDER_35","1X"},
                                     "value_shadow":False,"ev":None}})
        choices=select_candidates(rows,matrix,V3Policy(max_joint_correlation=.99))
        self.assertLessEqual(len(choices["pro_vip_shadow"]),2)
        selected=[x for x in rows if x["key"] in choices["pro_vip_shadow"]]
        self.assertEqual(len({x["family"] for x in selected}),len(selected))
        self.assertTrue(choices["no_publication"])

    def test_no_future_result_leakage_and_full_engine(self):
        start=datetime(2025,8,1,tzinfo=UTC)
        history=[event(i+1,1 if i%2==0 else 2,2 if i%2==0 else 1,
                       start+timedelta(days=i*2),hs=i%4,aws=(i+1)%3)
                 for i in range(40)]
        before=V2History(history).team(1,datetime(2025,9,10,tzinfo=UTC))
        after=V2History(history+[event(1234,1,2,datetime(2026,1,1,tzinfo=UTC),hs=19)]
                        ).team(1,datetime(2025,9,10,tzinfo=UTC))
        self.assertEqual([m["id"] for m in before],[m["id"] for m in after])
        upcoming=event(9000,1,2,datetime(2025,11,15,tzinfo=UTC),status="notstarted")
        runtime={"index":V2History(history),"rho":0.,"calibration":None,"challengers":{}}
        report=evaluate_fixture(upcoming,runtime,now=datetime(2025,11,14,tzinfo=UTC))
        self.assertEqual(report["status"],"analyzed")
        self.assertEqual(len(report["candidates"]),16)
        self.assertTrue(report["experimental"])
        self.assertFalse(report["published"])


    def test_immutable_forecast_and_prospective_settlement(self):
        import tempfile
        from pathlib import Path
        from bsd_v3.registry import append_once,verify_registry
        from bsd_v3.settlement import settle_registry,performance_report
        base=Path.cwd()/"bsd_v3"/"artifacts"
        base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temp:
            path=Path(temp)/"records.jsonl"
            start=datetime(2026,11,6,10,tzinfo=UTC)
            candidate={"key":"OVER_15","probability":.75,
                       "quote":{"verified":True,"executable":True,"odds":1.65}}
            record={"event_id":"500","kickoff_utc":start.isoformat(),
                    "candidates":[candidate],"model":"bsd-v3-shadow-0.1",
                    "selections":{}}
            _,added=append_once(path,"forecast","2026-11-06:500",record)
            self.assertTrue(added)
            _,added=append_once(path,"forecast","2026-11-06:500",record)
            self.assertFalse(added)
            with self.assertRaises(ValueError):
                append_once(path,"forecast","2026-11-06:500",dict(record,event_id="501"))
            final=event(500,1,2,start,status="finished",hs=2,aws=1)
            report=settle_registry(path,[final],now=start+timedelta(hours=6))
            self.assertEqual(report["new_settlements"],1)
            self.assertEqual(len(verify_registry(path)),2)
            self.assertEqual(settle_registry(path,[final],now=start+timedelta(hours=6))["new_settlements"],0)
            stats=performance_report(path)
            self.assertEqual(stats["by_market"]["OVER_15"]["priced_n"],1)
            self.assertAlmostEqual(stats["by_market"]["OVER_15"]["roi_verified_named_bookmaker"],.65)
            lines=path.read_text(encoding="utf-8").splitlines()
            path.write_text(lines[0].replace("500","501",1)+"\n"+lines[1]+"\n",encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_registry(path)


    def test_shadow_fingerprint_is_verified_before_archiving(self):
        import tempfile,hashlib,json
        from pathlib import Path
        from bsd_v3.registry import record_snapshot,verify_registry
        folder=Path.cwd()/"bsd_v3"/"artifacts"
        folder.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as temp:
            dest=Path(temp)/"shadow.jsonl"
            payload={"format":"bsd-v3-shadow-v1","published":False,
                     "generated_at_utc":"2026-11-06T12:00:00+00:00",
                     "matches":[{"event_id":"300","status":"analyzed",
                                 "kickoff_utc":"2026-11-06T16:00:00+00:00",
                                 "generated_at_utc":"2026-11-06T12:00:00+00:00",
                                 "model":"bsd-v3-shadow-0.1",
                                 "candidates":[],"selections":{}}]}
            raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False)
            payload["fingerprint_sha256"]=hashlib.sha256(raw.encode("utf-8")).hexdigest()
            self.assertEqual(record_snapshot(payload,path=dest),1)
            self.assertEqual(record_snapshot(payload,path=dest),0)
            self.assertEqual(len(verify_registry(dest)),1)
            modified=dict(payload,published=True)
            with self.assertRaises(ValueError):
                record_snapshot(modified,path=dest)
            modified=dict(payload,model="unrecorded-change")
            with self.assertRaises(ValueError):
                record_snapshot(modified,path=dest)


    def test_complete_shadow_cycle_without_network(self):
        import hashlib,json
        from unittest.mock import patch
        from bsd_v3.engine import run_shadow
        start=datetime(2025,8,1,tzinfo=UTC)
        history=[event(i+1,1 if i%2==0 else 2,2 if i%2==0 else 1,
                       start+timedelta(days=i*2),hs=i%4,aws=(i+1)%3)
                 for i in range(40)]
        fixture=event(9001,1,2,datetime(2025,11,15,tzinfo=UTC),status="notstarted")
        runtime={"index":V2History(history),"rho":0.,"calibration":None,
                 "challengers":{},"challenger_training":{}}
        now=datetime(2025,11,14,tzinfo=UTC)
        quote={"odds":1.8,"origin":"bsd_consensus","bookmaker":"consensus",
               "captured_at":now.isoformat(),
               "updated_at":(now-timedelta(minutes=10)).isoformat()}
        def free_quotes(f, t):
            return {"OU_1.5_OVER_FT":quote},{"provider":"bsd-consensus"}
        with patch("bsd_v3.engine.train_runtime",return_value=runtime):
            result=run_shadow([fixture],history,now=now,quote_fetcher=free_quotes)
        self.assertEqual(result["format"],"bsd-v3-shadow-v1")
        self.assertEqual(result["diagnostics"]["odds_events_queried"],1)
        self.assertFalse(result["published"])
        self.assertEqual(len(result["matches"][0]["candidates"]),16)
        self.assertGreaterEqual(result["matches"][0]["quote_diagnostics"]["accepted"],1)
        original={k:v for k,v in result.items() if k!="fingerprint_sha256"}
        expected=hashlib.sha256(json.dumps(original,sort_keys=True,separators=(",",":"),
                                         ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(result["fingerprint_sha256"],expected)


    def test_preferred_markets_beat_nonpreferred_when_both_are_qualified(self):
        from bsd_v3.market_priors import attach_market_merit
        matrix,cs=coherent_candidates({"home":1.45,"away":1.05})
        by={x.key:x for x in cs}
        priors={"markets":{
            "1":{"rate":.46,"n":5000},
            "1X":{"rate":.73,"n":5000},
            "UNDER_35":{"rate":.71,"n":5000},
        }}
        rows=[]
        for key,p in (("1",.80),("1X",.92),("UNDER_35",.90)):
            cand=by[key]
            row={"key":cand.key,"family":cand.family,"market":cand.market,
                 "line":cand.line,"probability":p,"conservative_probability":p,
                 "decision":{"pro_vip_shadow":True,"value_shadow":False,"ev":None}}
            rows.append(attach_market_merit(row,priors))
        choices=select_candidates(rows,matrix,V3Policy(max_joint_correlation=.99))
        self.assertEqual(choices["pro_vip_shadow"][0],"1")
        self.assertEqual(choices["preferred_pro_vip_shadow"],["1"])

    def test_strongest_signal_wins_inside_preferred_group(self):
        from bsd_v3.market_priors import attach_market_merit
        matrix,cs=coherent_candidates({"home":1.45,"away":1.15})
        by={x.key:x for x in cs}
        priors={"markets":{
            "1":{"rate":.46,"n":5000},
            "BTTS_YES":{"rate":.50,"n":5000},
            "OVER_15":{"rate":.70,"n":5000},
        }}
        rows=[]
        for key,p in (("1",.80),("BTTS_YES",.86),("OVER_15",.88)):
            cand=by[key]
            row={"key":cand.key,"family":cand.family,"market":cand.market,
                 "line":cand.line,"probability":p,"conservative_probability":p,
                 "decision":{"pro_vip_shadow":True,"value_shadow":False,"ev":None}}
            rows.append(attach_market_merit(row,priors))
        choices=select_candidates(rows,matrix,V3Policy(max_joint_correlation=.99))
        self.assertEqual(choices["pro_vip_shadow"][0],"BTTS_YES")

    def test_nonpreferred_market_remains_fallback_when_no_priority_market_qualifies(self):
        from bsd_v3.market_priors import attach_market_merit
        matrix,cs=coherent_candidates({"home":1.2,"away":1.0})
        cand=next(x for x in cs if x.key=="1X")
        row={"key":cand.key,"family":cand.family,"market":cand.market,
             "line":cand.line,"probability":.88,"conservative_probability":.86,
             "decision":{"pro_vip_shadow":True,"value_shadow":False,"ev":None}}
        row=attach_market_merit(row,{"markets":{"1X":{"rate":.72,"n":5000}}})
        choices=select_candidates([row],matrix,V3Policy(max_joint_correlation=.99))
        self.assertEqual(choices["pro_vip_shadow"],["1X"])
        self.assertEqual(choices["preferred_pro_vip_shadow"],[])


    def test_repeated_fixture_snapshots_are_audit_only_not_double_counted(self):
        import tempfile
        from pathlib import Path
        from bsd_v3.registry import append_once,canonical_forecasts,verify_registry
        from bsd_v3.settlement import settle_registry,performance_report
        root=Path.cwd()/"bsd_v3"/"artifacts"
        root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            path=Path(temp)/"ledger.jsonl"
            kickoff=datetime(2026,11,7,5,tzinfo=UTC)
            base={"event_id":"777","kickoff_utc":kickoff.isoformat(),
                  "generated_at_utc":"2026-11-06T20:00:00+00:00",
                  "model":"bsd-v3-shadow-0.1",
                  "candidates":[{"key":"1","probability":.81,"family":"result","quote":None}],
                  "selections":{"pro_vip_shadow":["1"],"value_shadow":[]}}
            later=dict(base,generated_at_utc="2026-11-06T21:00:00+00:00",
                       candidates=[{"key":"1","probability":.85,"family":"result","quote":None}])
            append_once(path,"forecast","old-run-a:777",base)
            append_once(path,"forecast","old-run-b:777",later)
            entries=verify_registry(path)
            self.assertEqual(len(entries),2)
            self.assertEqual(len(canonical_forecasts(entries)),1)
            final=event(777,1,2,kickoff,status="finished",hs=2,aws=0)
            result=settle_registry(path,[final],now=kickoff+timedelta(hours=6))
            self.assertEqual(result["new_settlements"],1)
            report=performance_report(path)
            self.assertEqual(report["forecasts"],1)
            self.assertEqual(report["settlements"],1)
            self.assertEqual(report["by_market"]["1"]["n"],1)
            self.assertAlmostEqual(report["by_market"]["1"]["mean_predicted"],.81)



    def test_reliability_circuit_does_not_require_a_quote_or_value(self):
        quality={"level":"full","league_games":90,"recent_games":12,"venue_games":6}
        row={"key":"1","family":"result","probability":.76,
             "conservative_probability":.73}
        decision=label_candidate(row,quality,None)
        self.assertTrue(decision["pro_vip_shadow"])
        self.assertFalse(decision["priced_reliability_shadow"])
        self.assertFalse(decision["value_shadow"])
        self.assertIsNone(decision["ev"])

    def test_consensus_price_can_confirm_edge_but_value_stays_nonexecutable(self):
        now=datetime(2026,11,6,12,tzinfo=UTC)
        raw={"odds":1.60,"bookmaker":"consensus","origin":"bsd_consensus",
             "captured_at":(now-timedelta(minutes=10)).isoformat(),
             "updated_at":(now-timedelta(minutes=15)).isoformat()}
        quote,_=validate_quote(raw,now=now,kickoff=now+timedelta(hours=3))
        quality={"level":"full","league_games":90,"recent_games":12,"venue_games":6}
        row={"key":"1","family":"result","probability":.76,
             "conservative_probability":.73}
        decision=label_candidate(row,quality,quote)
        self.assertTrue(decision["pro_vip_shadow"])
        self.assertTrue(decision["priced_reliability_shadow"])
        self.assertFalse(decision["value_shadow"])


    def test_over25_is_preferred_to_over15_when_both_goals_markets_qualify(self):
        from bsd_v3.market_priors import attach_market_merit
        matrix,cs=coherent_candidates({"home":1.9,"away":1.4})
        by={x.key:x for x in cs}
        priors={"markets":{
            "OVER_15":{"rate":.74,"n":5000},
            "OVER_25":{"rate":.55,"n":5000},
        }}
        rows=[]
        for key,p in (("OVER_15",.90),("OVER_25",.74)):
            cand=by[key]
            row={"key":cand.key,"family":cand.family,"market":cand.market,
                 "line":cand.line,"probability":p,"conservative_probability":p,
                 "decision":{"pro_vip_shadow":True,"value_shadow":False,"ev":None}}
            rows.append(attach_market_merit(row,priors))
        choices=select_candidates(rows,matrix,V3Policy(max_joint_correlation=.99))
        self.assertEqual(choices["pro_vip_shadow"],["OVER_25"])
        self.assertEqual(choices["preferred_pro_vip_shadow"],["OVER_25"])

if __name__=="__main__":
    unittest.main()
