import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit_series_bots", ROOT / "scripts/audit_series_bots.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeBot:
    def __init__(self, role="administrator", radar_role="administrator"):
        self.role = role
        self.radar_role = radar_role
        self.calls = []

    def call(self, method, data):
        self.calls.append(method)
        if method == "getMe":
            return {"id": 101, "username": "poster_bot"}
        if method == "getChat":
            if data["chat_id"] == "@CineRadarFr_Bot":
                return {"id": 202, "username": "CineRadarFr_Bot"}
            return {"id": int(data["chat_id"]), "type": "channel", "title": "Ma série",
                    "pinned_message": {"message_id": 17, "photo": [{"file_id": "x"}]}}
        if method == "getChatMember":
            return {"status": self.radar_role if data["user_id"] == 202 else self.role}
        raise AssertionError(f"Unexpected method {method}")


class SeriesBotInventoryTest(unittest.TestCase):
    def test_space_separated_and_duplicates(self):
        ids = audit.parse_channel_ids("-1001234567890 -1009876543210  -1001234567890\n")
        self.assertEqual(ids, ["-1001234567890", "-1009876543210"])

    def test_reject_unsafe_input(self):
        for value in ("@mychannel", "123", "-1001234567890;rm -rf /", "-100abc"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.parse_channel_ids(value)

    def test_empty_registry(self):
        self.assertEqual(audit.parse_channel_ids(""), [])

    def test_pinned_poster_and_bot_access(self):
        bot = FakeBot()
        report = audit.audit(["-1001234567890"], bot, None)
        self.assertEqual(report["counts"]["verified"], 1)
        self.assertEqual(report["channels"][0]["pinned_poster_message_id"], 17)
        self.assertFalse(report["channels"][0]["message_history_readable"])
        self.assertNotIn("copyMessage", bot.calls)
        self.assertNotIn("getUpdates", bot.calls)

    def test_radar_admin_missing(self):
        bot = FakeBot(radar_role="left")
        report = audit.audit(["-1001234567890"], bot, None)
        self.assertEqual(report["counts"]["radar_not_admin"], 1)


if __name__ == "__main__":
    unittest.main()
