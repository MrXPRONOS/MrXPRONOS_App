"""Offline tests for the BSD experimental predictor."""
import unittest
from datetime import datetime, timezone
from bsd_predict import HistoryIndex, poisson_markets, predict_fixture
from bsd_generate import generate


class PredictorTests(unittest.TestCase):
    def setUp(self):
        self.history = []
        for n in range(12):
            self.history.append({
                "id": n + 1,
                "event_date": "2026-09-%02dT12:00:00Z" % (n + 1),
                "status": "finished",
                "home_team_id": 10, "away_team_id": 20,
                "home_score": 2, "away_score": 0,
            })
        self.future = {
            "id": 999, "status": "notstarted", "event_date": "2026-10-20T20:00:00Z",
            "home_team_id": 10, "away_team_id": 20,
            "home_team": "Home", "away_team": "Away",
        }

    def test_probabilities(self):
        p = poisson_markets(1.6, 0.8)
        self.assertAlmostEqual(p["home_win"] + p["draw"] + p["away_win"], 1, places=7)
        self.assertTrue(0 < p["over_25"] < 1)

    def test_future_predictable(self):
        pred, reason = predict_fixture(
            self.future, HistoryIndex(self.history),
            clock=datetime(2026, 10, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(reason, "ok")
        self.assertEqual(pred["prediction"]["double_chance"], "1X")
        self.assertEqual(pred["id"], "bsd:999")
        self.assertIsNone(pred["ml_score"])

    def test_future_data_does_not_leak(self):
        future_game = {
            "id": 98, "event_date": "2026-10-21T20:00:00Z",
            "status": "finished", "home_team_id": 10, "away_team_id": 20,
            "home_score": 0, "away_score": 20,
        }
        idx = HistoryIndex(self.history + [future_game])
        self.assertEqual(len(idx.recent(10, self.future["event_date"])), 10)

    def test_notstarted_only(self):
        match = {**self.future, "status": "finished"}
        pred, reason = predict_fixture(match, HistoryIndex(self.history))
        self.assertIsNone(pred)
        self.assertEqual(reason, "not_upcoming")

    def test_does_not_mutate_legacy_data(self):
        from copy import deepcopy
        old = deepcopy(self.history)
        result = generate([self.future], self.history, now=datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.assertEqual(result["source"], "bsd")
        self.assertFalse(result["published"])
        self.assertEqual(self.history, old)


if __name__ == "__main__":
    unittest.main()
