import unittest
from datetime import datetime,timezone,timedelta
from scripts.football_multisource_calibrated_replay import model_index_partition,replay

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
