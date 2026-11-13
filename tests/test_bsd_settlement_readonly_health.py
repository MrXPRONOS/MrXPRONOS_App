"""Read-only BSD live settlement audit: offline mock regression."""
import unittest
from datetime import datetime, timedelta, timezone
from scripts.bsd_settlement_readonly_health import inspect

NOW = datetime(2026,11,13,18,tzinfo=timezone.utc)
START=(NOW-timedelta(hours=6)).isoformat()


def row(eid=123):
    return {"source":"bsd","id":"bsd:"+str(eid),"source_event_id":eid,
            "event_date":START,"status":"settlement_pending","is_finished":False,
            "home_team":"Club A","away_team":"Club B",
            "prediction":{"selection_key":"OVER_15","odds":1.8,"confidence":82}}


def feed(rows):
    return {"source":"bsd","model_version":"bsd-v2-isolated","matches":rows}


class BsdLiveSettlementReadOnlyTests(unittest.TestCase):
    def test_verified_native_score_detects_recoverable_pending_without_edit(self):
        original = row()
        data = feed([original])
        result = inspect(data,NOW,lambda eid:{
            "id":int(eid), "event_date":START, "status":"finished",
            "home_score":2, "away_score":0})
        self.assertEqual(result["due"],1)
        self.assertEqual(result["bsd_finished_verified"],1)
        self.assertTrue(original["is_finished"] is False)
        self.assertTrue(data["matches"][0] is original)

    def test_missing_or_unfinished_score_stays_unresolved(self):
        stats=inspect(feed([row()]),NOW,lambda eid:{
            "id":123,"event_date":START,"status":"postponed",
            "home_score":None, "away_score":None})
        self.assertEqual(stats["bsd_still_unresolved"],1)
        self.assertEqual(stats["bsd_finished_verified"],0)

    def test_wrong_native_event_id_is_quarantined(self):
        stats=inspect(feed([row()]),NOW,lambda eid:{
            "id":999, "event_date":START, "status":"finished",
            "home_score":2,"away_score":0})
        self.assertEqual(stats["bsd_identity_mismatch"],1)
        self.assertEqual(stats["bsd_finished_verified"],0)

    def test_no_duplicate_native_id_even_if_matches_different(self):
        with self.assertRaisesRegex(ValueError,"Duplicate published native"):
            inspect(feed([row(),row()]),NOW,lambda eid:None)

    def test_pre_kickoff_and_recent_match_not_poked(self):
        recent=row()
        recent["event_date"]=(NOW-timedelta(hours=1)).isoformat()
        called=[]
        stats=inspect(feed([recent]),NOW,lambda eid:called.append(eid))
        self.assertEqual(stats["sample"],0)
        self.assertEqual(called,[])


if __name__ == "__main__":
    unittest.main()
