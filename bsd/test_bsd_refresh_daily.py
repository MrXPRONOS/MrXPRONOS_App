"""Offline contract tests for incremental BSD refresh."""
import unittest
from datetime import date
from unittest.mock import Mock
from bsd_refresh_daily import eligible_finished, refresh


class RefreshTests(unittest.TestCase):
    def test_rejects_invalid_and_future(self):
        rows = [
            {"id": 1, "status": "finished", "event_date": "2026-10-07T12:00:00Z",
             "home_team_id": 1, "away_team_id": 2, "home_score": 2, "away_score": 1},
            {"id": 2, "status": "finished", "event_date": "2026-10-09T12:00:00Z",
             "home_team_id": 1, "away_team_id": 2, "home_score": 1, "away_score": 1},
            {"id": 3, "status": "notstarted", "event_date": "2026-10-07T12:00:00Z",
             "home_team_id": 1, "away_team_id": 2},
        ]
        valid, bad = eligible_finished(rows, as_of=date(2026, 10, 8))
        self.assertEqual([row["id"] for row in valid], [1])
        self.assertEqual(bad, 1)

    def test_incomplete_days_never_persist(self):
        client = Mock()
        client.list_events.return_value = Mock(complete=False, events=[], total_reported=2)
        with self.assertRaises(RuntimeError):
            refresh([], client, as_of=date(2026, 10, 8), days=1)

    def test_merges_without_duplicates(self):
        old = [{"id": 1, "status": "finished", "event_date": "2026-10-08T11:00:00Z",
                "home_team_id": 1, "away_team_id": 2, "home_score": 1, "away_score": 0}]
        client = Mock()
        client.requests_made = 1
        client.rate_limit_remaining = 500
        client.list_events.return_value = Mock(complete=True, total_reported=1, events=[
            {**old[0], "home_score": 2}
        ])
        out, r = refresh(old, client, as_of=date(2026, 10, 8), days=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["home_score"], 2)
        self.assertEqual(r["updated"], 1)


if __name__ == "__main__":
    unittest.main()
