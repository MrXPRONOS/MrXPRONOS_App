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


    def test_legacy_publications_are_disabled_at_activation(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        for name in ("telegram-daily-xpvip-promo.yml",
                     "telegram-day-based-bookmaker-promos.yml",
                     "telegram-daily-bookmaker-bonus-ads.yml",
                     "telegram-daily-bookmaker-guide.yml"):
            source=(root/".github"/"workflows"/name).read_text(encoding="utf8")
            self.assertIn("vars.TG_BOT_BUTTONS_DAILY_ENABLED != 'true'",source)

    def test_new_workflow_has_four_dedicated_slots(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        source=(root/".github"/"workflows"/"telegram-bot-buttons-daily.yml").read_text(encoding="utf8")
        for slot in SLOTS:
            self.assertIn("cron: '"+slot+"'",source)
        self.assertIn("vars.TG_BOT_BUTTONS_DAILY_ENABLED == 'true'",source)

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


    def test_telegram_rich_fallback_keeps_actual_keyboard(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock
        from scripts import telegram_bot_buttons_daily as dispatch
        import sys
        from pathlib import Path as PathType
        from scripts import telegram_bot_buttons_daily as dispatch_import
        sys.path.insert(0, str(dispatch_import.SCRIPTS))
        from telegram_rich import post_photo
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / "button-photo.jpg"
            image.write_bytes(b"safe-offline-fixture")
            rich = Mock(status_code=404)
            rich.json.return_value = {"ok": False, "error_code": 404}
            legacy = Mock(status_code=200)
            legacy.json.return_value = {"ok": True, "result": {"message_id": 42}}
            legacy.raise_for_status.return_value = None
            session = Mock()
            session.post.side_effect = [rich, legacy]
            keyboard = {"inline_keyboard": [[{"text": "Voir le lien", "url": "https://t.me/CineRadarFr_Bot"}]]}
            self.assertEqual(post_photo(session, "sample", -1001, image,
                       "<b>Caption</b>", keyboard, mime="image/jpeg"), 42)
            self.assertEqual(session.post.call_count, 2)
            first = session.post.call_args_list[0]
            second = session.post.call_args_list[1]
            self.assertIn("sendRichMessage", first.args[0])
            self.assertIn("tg-button", json.loads(first.kwargs["data"]["rich_message"])["html"])
            self.assertIn("sendPhoto", second.args[0])
            self.assertEqual(json.loads(second.kwargs["data"]["reply_markup"]), keyboard)

    def test_execute_requires_feature_gate(self):
        with patch.dict(os.environ,{"TG_BOT_BUTTONS_DAILY_ENABLED":"false"}), patch(
            "scripts.telegram_bot_buttons_daily.subprocess.run"
        ) as send:
            with self.assertRaises(RuntimeError):
                main(["--campaign","xpvip","--execute"])
            send.assert_not_called()
