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

    def test_public_policy_79_percent(self):
        row={"key":"1","family":"result","probability":.79,
             "conservative_probability":.74}
        self.assertFalse(public_candidate(row,{"level":"full"}))
        row["conservative_probability"]=.78
        self.assertTrue(public_candidate(row,{"level":"full"}))

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

if __name__=="__main__":
    unittest.main()
