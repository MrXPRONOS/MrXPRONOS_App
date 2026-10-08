"""Offline checks for BSD archive coverage statistics."""
import unittest
from bsd_quality_audit import audit


class AuditTests(unittest.TestCase):
    def test_duplicate_and_outside_year(self):
        rows = [
            {"id": 1, "event_date": "2025-01-01T12:00:00Z", "status": "finished",
             "home_team_id": 10, "away_team_id": 20, "home_score": 2, "away_score": 1},
            {"id": 1, "event_date": "2025-01-01T12:00:00Z", "status": "finished",
             "home_team_id": 10, "away_team_id": 20, "home_score": 2, "away_score": 1},
            {"id": 2, "event_date": "2023-11-01T12:00:00Z", "status": "finished",
             "home_team_id": 20, "away_team_id": 10, "home_score": 0, "away_score": 2},
        ]
        r = audit(rows, {"season_tasks": [1], "completed_seasons": [1]}, samples=3)
        self.assertEqual(r["issues"]["duplicate_id"], 1)
        self.assertEqual(r["issues"]["out_of_target_dates"], 1)
        self.assertEqual(r["valid_events_for_analysis"], 2)

    def test_invalid_scores(self):
        r = audit([{"id": 3, "event_date": "2025-01-01T12:00:00Z",
                    "status": "finished", "home_team_id": 10, "away_team_id": 20,
                    "home_score": None, "away_score": 0}], {}, samples=0)
        self.assertEqual(r["issues"]["invalid_final_score"], 1)


if __name__ == "__main__":
    unittest.main()
