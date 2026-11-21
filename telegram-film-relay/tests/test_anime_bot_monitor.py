"""Read-only Anime Bot V2 alerts never leak source or Telegram IDs."""
from __future__ import annotations

import unittest

from film_relay.anime_bot_monitor import health_snapshot, evaluate_alerts
from film_relay.anime_bot_queue import mark_bot_review


class BotMonitorTests(unittest.TestCase):
    def test_stale_weekly_series_and_uncertain_send_are_reported(self):
        now = 1800000000
        state = {
            "series": {"naruto": {
                "cadence_hint": "weekly",
                "last_published_source_date": now - 15 * 86400,
            }},
            "messages": {"private-id:1": {
                "status": "review", "kind": "video", "date": now - 500}},
            "operation_receipts": {"private:bad": {"status": "uncertain"}},
        }
        report = health_snapshot(state, now=now)
        self.assertEqual(report["weekly_overdue_estimate"], 1)
        self.assertEqual(report["ambiguous_operations"], 1)
        self.assertEqual(report["queue_quarantined"], 1)
        self.assertEqual(report["status"], "action_required")
        alerts = evaluate_alerts(state, now=now)
        self.assertGreaterEqual(len(alerts), 3)
        self.assertNotIn("private-id", str(report))
        self.assertNotIn("private-id", str(alerts))

    def test_manual_review_never_alters_published_source_receipt(self):
        state = {"messages": {
            "source:1": {"status": "pending", "kind": "video"},
            "source:2": {"status": "published", "kind": "video"},
        }}
        marked = mark_bot_review(state, [
            {"source_key": "source:1", "reason": "wrong_title"},
            {"source_key": "source:2", "reason": "ambiguous"},
        ], [])
        self.assertEqual(marked, 1)
        self.assertEqual(state["messages"]["source:1"]["status"], "review")
        self.assertEqual(state["messages"]["source:2"]["status"], "published")
        self.assertEqual(mark_bot_review(state, [
            {"source_key": "source:1", "reason": "wrong_title"}
        ], []), 0)


if __name__ == "__main__":
    unittest.main()
