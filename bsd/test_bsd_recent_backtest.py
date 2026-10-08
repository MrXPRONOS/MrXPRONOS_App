"""Offline tests for 3-day BSD recent backtest."""
import unittest
from datetime import date
from bsd_recent_backtest import window_dates, evaluate_recent
from bsd_markets import MarketCalibrator


class RecentBacktestTests(unittest.TestCase):
    def test_three_completed_days(self):
        dates = window_dates(date(2026, 10, 7), 3, today=date(2026, 10, 8))
        self.assertEqual([str(d) for d in dates], ["2026-10-05", "2026-10-06", "2026-10-07"])

    def test_no_today_included(self):
        with self.assertRaises(ValueError):
            window_dates(date(2026, 10, 8), 3, today=date(2026, 10, 8))

    def test_no_empty_or_partial_fixtures(self):
        history = [{
            "id": 1, "event_date": "2026-09-01T12:00:00Z",
            "status": "finished", "home_team_id": 5, "away_team_id": 6,
            "home_score": 1, "away_score": 0,
        }]
        inputs = {
            "2026-10-05": [],
            "2026-10-06": [],
            "2026-10-07": [],
        }
        with self.assertRaises(RuntimeError):
            evaluate_recent(inputs, history, MarketCalibrator(),
                            end_date=date(2026, 10, 7), days=3)

    def test_result_only_from_api_fixture_not_history(self):
        history = [{
            "id": 1, "event_date": "2026-09-01T12:00:00Z",
            "status": "finished", "home_team_id": 5, "away_team_id": 6,
            "home_score": 1, "away_score": 0,
        }]
        fixtures = {
            "2026-10-05": [{"id": 2, "event_date": "2026-10-05T18:00:00Z", "status": "finished",
                            "home_team_id": 5, "away_team_id": 6, "home_score": 1, "away_score": 1}],
            "2026-10-06": [],
            "2026-10-07": [],
        }
        report = evaluate_recent(fixtures, history, MarketCalibrator(),
                                 end_date=date(2026, 10, 7), days=3)
        self.assertEqual(report["summary"]["finished_with_scores"], 1)
        self.assertEqual(report["summary"]["selected"], 0)
        self.assertEqual(report["rejected_predictions"]["insufficient_form"], 1)
        self.assertEqual(report["history_events_used"], 1)


if __name__ == "__main__":
    unittest.main()
