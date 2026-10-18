"""Offline tests for premium production scheduler; no network or Telegram."""
from __future__ import annotations
import unittest
from unittest.mock import patch

from crypto import production_live_v1 as live


class ProductionSchedulerTests(unittest.TestCase):
    def test_modes_only_approved_rubrics(self):
        self.assertEqual(live.MODES["morning"], (1, 5, 6))
        self.assertEqual(live.MODES["midday"], (2, 3))
        self.assertEqual(live.MODES["news"], (8, 9))
        self.assertEqual(live.MODES["weekly"], (7,))
        self.assertNotIn(10, [i for arr in live.MODES.values() for i in arr])

    def test_daily_idempotence_and_market_slots(self):
        self.assertEqual(
            live.key_for(1, {}, "morning"),
            live.key_for(1, {}, "morning"))
        self.assertNotEqual(
            live.key_for(1, {}, "morning"),
            live.key_for(1, {}, "evening"))
        self.assertIn("daily:02:", live.key_for(2, {}, "midday"))

    def test_news_fingerprints_are_sorted_and_stable(self):
        a = live.key_for(8, {"fingerprints": ["aa", "bb"]}, "news")
        b = live.key_for(8, {"fingerprints": ["bb", "aa"]}, "news")
        self.assertEqual(a, b)
        self.assertNotEqual(a, live.key_for(9, {"fingerprints": ["aa", "bb"]}, "news"))
        self.assertNotEqual(a, live.key_for(8, {"fingerprints": ["cc", "bb"]}, "news"))
        with self.assertRaises(ValueError):
            live.key_for(8, {"fingerprints": []}, "news")

    def test_alert_never_produces_static_news_id(self):
        d = {"row": {"symbol": "BTC", "change": 6.4, "level": 5}}
        key = live.key_for(4, d, "alerts")
        self.assertIn(":BTC:up:5", key)
        d["row"]["change"] = -6.5
        self.assertNotEqual(key, live.key_for(4, d, "alerts"))

    def test_initial_history_suppresses_daily_duplication(self):
        st = {"sent": {"initial_history_02": {
            "sent_at": live.TODAY.isoformat(), "message_id": 7}}}
        self.assertTrue(live.blocked_by_initial_history(st, 2))
        self.assertFalse(live.blocked_by_initial_history(st, 8))

    def test_weekly_key_contains_iso_week(self):
        self.assertIn("weekly:07:", live.key_for(7, {}, "weekly"))

    def test_legal_review_never_checks_telegram_or_sends(self):
        with patch.object(live.seed, "run") as command:
            with patch.object(live.seed, "verify_production_route") as route:
                with patch.object(live, "REG") as reg:
                    reg.is_file.return_value = False
                    live.execute("legal")
        route.assert_not_called()
        command.assert_called_once_with("python", "-m", "crypto.export_regulation_v2")

    def test_real_sender_requires_image_and_photo_confirmation(self):
        with patch.object(live.seed, "validate_image") as validate:
            with patch.object(live.requests, "post") as request:
                request.return_value.raise_for_status.return_value = None
                request.return_value.json.return_value = {
                    "ok": True,
                    "result": {
                        "message_id": 44,
                        "chat": {"id": -1001234},
                        "photo": [{"file_id": "a"}],
                    },
                }
                import tempfile
                from pathlib import Path
                with tempfile.TemporaryDirectory() as tmp:
                    p = Path(tmp) / "real.png"
                    p.write_bytes(b"x" * 12000)
                    self.assertEqual(
                        live.record_send({"id": -1001234}, "TEST REAL", p), 44)
                validate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
