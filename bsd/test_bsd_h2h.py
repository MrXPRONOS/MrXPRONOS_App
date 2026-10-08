"""Tests H2H hors-ligne: sens des équipes, dates, données manquantes et API."""
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from bsd_h2h import local_h2h, hybrid_h2h


def event(id, date, home, away, hs, aws, status="finished"):
    return {
        "id": id, "event_date": date, "home_team_id": home, "away_team_id": away,
        "home_score": hs, "away_score": aws, "status": status,
    }


class H2HTests(unittest.TestCase):
    def setUp(self):
        self.kickoff = "2026-10-20T15:00:00+00:00"
        self.events = [
            event(1, "2025-05-01T15:00:00Z", 11, 22, 2, 0),
            event(2, "2025-09-01T15:00:00Z", 22, 11, 0, 1),
            event(3, "2026-02-01T15:00:00Z", 11, 22, 1, 1),
            event(3, "2026-02-01T15:00:00Z", 11, 22, 1, 1),
            event(4, "2026-10-22T15:00:00Z", 11, 22, 0, 5),
            event(5, "2026-10-01T15:00:00Z", 11, 22, None, None),
            event(6, "2026-10-01T15:00:00Z", 11, 22, 0, 0, "live"),
        ]

    def test_orientation_and_duplicates(self):
        r = local_h2h(self.events, 11, 22, self.kickoff)
        self.assertEqual(r["total_matches"], 3)
        self.assertEqual(r["home_wins"], 2)
        self.assertEqual(r["away_wins"], 0)
        self.assertEqual(r["draws"], 1)
        self.assertEqual(r["home_goals"], 4)
        self.assertEqual(r["away_goals"], 1)

    def test_as_of_excludes_future_and_missing(self):
        r = local_h2h(self.events, 11, 22, "2025-08-01T00:00:00Z")
        self.assertEqual(r["total_matches"], 1)

    def test_history_never_fetches_remote(self):
        client = Mock()
        fixture = event(7, self.kickoff, 11, 22, None, None, "notstarted")
        r = hybrid_h2h(client, fixture, [], now=datetime(2026, 10, 21, tzinfo=timezone.utc))
        self.assertEqual(r["api_skipped"], "historical_or_disabled")
        client.get_h2h.assert_not_called()

    def test_uses_local_when_enough(self):
        client = Mock()
        fixture = event(7, self.kickoff, 11, 22, None, None, "notstarted")
        r = hybrid_h2h(client, fixture, self.events, now=datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.assertEqual(r["source"], "local")
        client.get_h2h.assert_not_called()

    def test_calls_remote_only_for_future_and_short_history(self):
        client = Mock()
        client.get_h2h.return_value = {
            "total_matches": 3, "home_wins": 1, "away_wins": 1, "draws": 1,
        }
        fixture = event(7, self.kickoff, 11, 22, None, None, "notstarted")
        r = hybrid_h2h(client, fixture, self.events[:1], now=datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.assertEqual(r["source"], "api")
        client.get_h2h.assert_called_once_with(7, ttl=86400)

    def test_no_remote_schema_does_not_become_fake_data(self):
        client = Mock()
        client.get_h2h.return_value = {"irrelevant": 1}
        fixture = event(7, self.kickoff, 11, 22, None, None, "notstarted")
        r = hybrid_h2h(client, fixture, [], now=datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.assertEqual(r["total_matches"], 0)


if __name__ == "__main__":
    unittest.main()
