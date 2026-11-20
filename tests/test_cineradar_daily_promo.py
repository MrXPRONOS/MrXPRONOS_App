import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cineradar_daily_promo.py"
spec = importlib.util.spec_from_file_location("cineradar_daily_promo", SCRIPT)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class CineradarDailyPromoTests(unittest.TestCase):
    def test_targets_exact_public_subset(self):
        handles = {name.casefold() for name, _ in p.TARGETS}
        self.assertEqual(len(handles), 13)
        self.assertIn("cinexfilms_vf", handles)
        self.assertIn("actucrypto24h", handles)
        self.assertIn("seriesvf_cinex", handles)
        self.assertIn("cinexanimefr", handles)
        self.assertNotIn("mrxpronosfr", handles)
        self.assertNotIn("actufoot_mrxp", handles)
        self.assertNotIn("predict_mrxp", handles)
        self.assertTrue(all(not name.startswith("-100") and len(name) >= 5 for name, _ in p.TARGETS))

    def test_formatting_and_button(self):
        self.assertIn("<b>", p.CAPTION)
        self.assertIn("<i>", p.CAPTION)
        self.assertIn("<blockquote>", p.CAPTION)
        self.assertLessEqual(len(p.CAPTION), 1024)
        b = p.BUTTON["inline_keyboard"][0][0]
        self.assertEqual(b["style"], "primary")
        self.assertEqual(b["url"], "https://t.me/CineRadarFr_Bot")
        self.assertEqual(p.SOURCE_MESSAGE_ID, 373)

    def test_verified_admin_with_post_access(self):
        def good_api(token, method, payload):
            if method == "getChat":
                return {"type": "channel", "id": -1001234567, "username": "CineXFilms_vf"}
            return {"status": "administrator", "can_post_messages": True}
        with patch.object(p, "api", side_effect=good_api):
            self.assertEqual(p.eligible_channel("token", 123, "CineXFilms_vf"),
                             ("-1001234567", "@CineXFilms_vf"))

    def test_denies_bot_without_rights(self):
        def denied_api(token, method, payload):
            if method == "getChat":
                return {"type": "channel", "id": -1001234567, "username": "CineXFilms_vf"}
            return {"status": "administrator", "can_post_messages": False}
        with patch.object(p, "api", side_effect=denied_api):
            with self.assertRaisesRegex(RuntimeError, "publisher_not_authorized"):
                p.eligible_channel("token", 123, "CineXFilms_vf")

    def test_denies_unexpected_channel_identity(self):
        with patch.object(p, "api", return_value={"type": "supergroup", "id": -1001234567, "username": "CineXFilms_vf"}):
            with self.assertRaisesRegex(RuntimeError, "unexpected_channel_identity"):
                p.eligible_channel("token", 123, "CineXFilms_vf")

    def test_reservation_prevents_duplicates(self):
        session = Mock()
        response = Mock()
        response.json.return_value = []
        session.post.return_value = response
        self.assertFalse(p.reserve(session, "https://example.supabase.co/rest/v1/telegram_promo_deliveries",
                                   "2026-11-21", "-1001234567"))
        self.assertEqual(session.post.call_args.kwargs["params"]["on_conflict"],
                         "campaign,delivery_day,chat_id")

    def test_dry_run_does_not_write_or_send(self):
        with patch.object(p, "find_publisher", return_value=("token", 101)), \
             patch.object(p, "eligible_channel", side_effect=lambda t, b, u: ("-1001234", "@" + u)), \
             patch.object(p, "ledger_session") as ledger, \
             patch.object(p, "api") as send, \
             patch.object(p, "reserve") as reserve:
            self.assertEqual(p.run(dry_run=True), 0)
            ledger.assert_not_called()
            send.assert_not_called()
            reserve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
