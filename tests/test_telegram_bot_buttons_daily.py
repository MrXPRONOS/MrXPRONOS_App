"""All tests are offline; user bot tokens are never needed."""
import os
import unittest
from unittest.mock import patch
from scripts.telegram_bot_buttons_daily import (
    PUBLISHERS, SLOTS, selected_campaign, assert_buttons, validate_templates, main,
)


class TestBotButtonDaily(unittest.TestCase):
    def test_four_daily_spaced_slots(self):
        self.assertEqual(len(SLOTS), 4)
        self.assertEqual(set(SLOTS.values()),set(PUBLISHERS))
        self.assertEqual(list(SLOTS),["0 6 * * *","30 6 * * *","0 7 * * *","30 7 * * *"])

    def test_cron_routes(self):
        for slot, campaign in SLOTS.items():
            self.assertEqual(selected_campaign(event_schedule=slot),campaign)

    def test_reject_unknown_slot(self):
        with self.assertRaises(ValueError):
            selected_campaign(event_schedule="0 8 * * *")
        with self.assertRaises(ValueError):
            selected_campaign()
        with self.assertRaises(ValueError):
            selected_campaign(event_schedule="0 6 * * *", manual_campaign="guide")

    def test_real_buttons_existing_scripts(self):
        result=validate_templates()
        self.assertGreaterEqual(result["xpvip"],6)
        self.assertGreaterEqual(result["weekday"],1)
        self.assertGreaterEqual(result["bonus"],6)
        self.assertGreaterEqual(result["guide"],6)

    def test_no_button_or_insecure_url_fails(self):
        for markup in ({"inline_keyboard":[]},
                       {"inline_keyboard":[[{"text":"broken","url":"http://example.org"}]]},
                       None):
            with self.assertRaises(ValueError):
                assert_buttons(markup, "test")

    def test_preview_never_sends(self):
        with patch("scripts.telegram_bot_buttons_daily.subprocess.run") as send:
            self.assertEqual(main(["--campaign","xpvip"]),0)
            send.assert_not_called()

    def test_execute_requires_feature_gate(self):
        with patch.dict(os.environ,{"TG_BOT_BUTTONS_DAILY_ENABLED":"false"}), patch(
            "scripts.telegram_bot_buttons_daily.subprocess.run"
        ) as send:
            with self.assertRaises(RuntimeError):
                main(["--campaign","xpvip","--execute"])
            send.assert_not_called()
