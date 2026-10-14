import unittest
from datetime import datetime,timezone,timedelta
from scripts.football_multisource_calibrated_replay import model_index_partition,replay
from bsd.bsd_v2_publish import assemble as original_assembler

def when(stamp):
    return datetime.fromisoformat(stamp.replace("Z","+00:00"))

class CalibratedReplayIsolationTests(unittest.TestCase):
    def test_training_frozen_before_2026_holdout(self):
        events=[
            {"event_date":"2025-12-31T19:00:00+00:00","id":1},
            {"event_date":"2025-12-31T22:00:00+00:00","id":2},
            {"event_date":"2026-01-03T12:00:00+00:00","id":3},
            {"event_date":"2026-10-15T12:00:00+00:00","id":4},
        ]
        train,observed=model_index_partition(events,
            cutoff=when("2026-01-01T00:00:00Z"),
            analysis_at=when("2026-10-14T19:00:00Z"))
        self.assertEqual([x["id"] for x in train],[1])
        self.assertEqual([x["id"] for x in observed],[1,2,3])

    def test_same_day_data_cannot_be_assumed_pre_match(self):
        rows=[
            {"event_date":"2026-10-14T23:59:00+00:00","id":"today"},
            {"event_date":"2026-10-13T23:59:00+00:00","id":"yesterday"},
            {"event_date":"2026-10-12T22:00:00+00:00","id":"older"},
        ]
        # Predict on Oct 15 based ONLY on data settled before Oct 14
        # 23:59; Oct 14 results must remain excluded.
        train,observed=model_index_partition(rows,
            cutoff=when("2026-10-14T23:59:00Z"),
            analysis_at=when("2026-10-17T00:00:00Z"))
        self.assertNotIn("today",[x["id"] for x in train])
        self.assertIn("yesterday",[x["id"] for x in train])
        self.assertIn("today",[x["id"] for x in observed])

    def test_real_production_assembler_can_run_offline_with_zero_fixtures(self):
        now=when("2026-10-14T20:00:00Z")
        original_existing={"matches":[],"performance_tracker":{}}
        output=original_assembler(
            original_existing,[],[],now=now,calibration=None,
            policy=None,rho=0.,odds_fetcher=None,max_odds_requests=0)
        self.assertEqual(output["matches"],[])
        self.assertEqual(output["diagnostics"]["rejections"].get("odds_attempts",0),0)
        self.assertEqual(output["diagnostics"]["v21_new_picks"],0)
        self.assertEqual(original_existing,{"matches":[],"performance_tracker":{}})

    def test_invalid_time_window_and_unbounded_holdout_rejected(self):
        with self.assertRaises(ValueError):
            model_index_partition([],cutoff=datetime(2026,1,1),
                                  analysis_at=when("2026-10-14T00:00:00Z"))
        with self.assertRaises(ValueError):
            replay([],[],at=when("2026-10-14T00:00:00Z"),
                   cutoff=when("2026-01-01T00:00:00Z"),max_holdout=201)
        with self.assertRaises(ValueError):
            replay([],[],at=when("2025-12-30T00:00:00Z"),
                   cutoff=when("2026-01-01T00:00:00Z"))

if __name__=="__main__":
    unittest.main()
