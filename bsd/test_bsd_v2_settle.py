"""Prospective settlement verification : never settle from future data."""
import unittest
from datetime import datetime, timezone
from bsd_v2_shadow import generate_shadow
from bsd_v2_policies import V2Calibration, V2QualityPolicy
from bsd_v2_settle import settle_snapshot, verify_snapshot


class SettlementTests(unittest.TestCase):
    def make_snapshot(self):
        start=datetime(2026,10,8,5,tzinfo=timezone.utc)
        s=generate_shadow([],[],V2Calibration(),V2QualityPolicy(),0,now=start)
        pred={
            "source_event_id":999,
            "event_date":"2026-10-08T12:00:00+00:00",
            "prediction":{"key":"UNDER_45","probability":0.85,"bookmaker_odds":None}
        }
        s["matches"].append(pred)
        import hashlib,json
        s["fingerprint_sha256"]=hashlib.sha256(json.dumps(
            {k:v for k,v in s.items() if k!="fingerprint_sha256"},
            sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()
        return s

    def test_valid_snapshot_settles_and_does_not_guess(self):
        s=self.make_snapshot()
        now=datetime(2026,10,9,10,tzinfo=timezone.utc)
        event={"id":999,"event_date":"2026-10-08T12:00:00Z",
               "status":"finished","home_score":2,"away_score":1}
        result=settle_snapshot(s,{"999":event},now=now)
        self.assertEqual(result["settled"],1)
        self.assertEqual(result["wins"],1)

    def test_no_settlement_before_kickoff_plus_delay(self):
        s=self.make_snapshot()
        event={"id":999,"event_date":"2026-10-08T12:00:00Z",
               "status":"finished","home_score":2,"away_score":1}
        result=settle_snapshot(s,{"999":event},
            now=datetime(2026,10,8,13,tzinfo=timezone.utc))
        self.assertEqual(result["settled"],0)
        self.assertEqual(result["unsettled_reasons"]["not_safely_settleable"],1)

    def test_tampered_snapshot_rejected(self):
        s=self.make_snapshot()
        s["matches"][0]["prediction"]["probability"]=0.1
        with self.assertRaises(ValueError):
            verify_snapshot(s)


if __name__=="__main__":
    unittest.main()
