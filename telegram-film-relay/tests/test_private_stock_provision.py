"""Offline, no personal Telegram login, token or network calls."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "provision_private_stock.py"
SPEC = importlib.util.spec_from_file_location("private_stock_provision", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrivateStockProvisionTests(TestCase):
    def test_only_verified_radar_and_expected_publisher_identity(self):
        def getbot(token):
            return {"radar": {"id": 23, "is_bot": True, "username": "CineRadarFr_Bot"},
                    "publisher": {"id": 31, "is_bot": True, "username": "MyPublisher"}}[token]
        with mock.patch.object(MODULE, "bot_identity", side_effect=getbot):
            env = {"CINEX_RADAR_BOT_TOKEN": "radar", "CINEX_PUBLISH_BOT_TOKEN": "publisher",
                   "CINEX_PUBLISH_BOT_USERNAME": "@MyPublisher"}
            result = MODULE.configured_bots(env)
            self.assertEqual([x["id"] for x in result], [23, 31])
            env["CINEX_PUBLISH_BOT_USERNAME"] = "UnknownBot"
            with self.assertRaisesRegex(RuntimeError, "publisher_identity_mismatch"):
                MODULE.configured_bots(env)

    def test_no_nonradar_bot_can_be_substituted(self):
        with mock.patch.object(MODULE, "bot_identity", return_value={"id": 5, "username": "wrong"}):
            with self.assertRaisesRegex(RuntimeError, "cineradar_identity_not_verified"):
                MODULE.configured_bots({"CINEX_RADAR_BOT_TOKEN": "bad"})

    def test_no_personal_telegram_session_in_dry_run(self):
        with mock.patch.object(MODULE, "configured_bots", return_value=[{"id": 7, "username": "CineRadarFr_Bot"}]):
            result = asyncio.run(MODULE.provision(apply=False))
            self.assertFalse(result["ready"])

    def test_db_rejects_reassignment_to_other_stock(self):
        saved = {"stock_chat_id": "-1001234567890", "owner_id": 99, "radar_bot_id": 7, "ready": 1}
        with mock.patch.object(MODULE, "d1_query") as query, mock.patch.object(MODULE, "registered_stock", return_value=saved):
            with self.assertRaisesRegex(RuntimeError, "d1_stock_already_bound"):
                MODULE.store_stock("-1009999999999", 99, 7)
            self.assertEqual(query.call_count, len(MODULE.DDL))

    def test_only_owner_and_approved_bot_participants_are_allowed(self):
        class Fake:
            async def iter_participants(self, channel, limit=40):
                for user in (SimpleNamespace(id=100), SimpleNamespace(id=200)):
                    yield user
        n = asyncio.run(MODULE.verify_members(Fake(), object(), 100, [{"id": 200}]))
        self.assertEqual(n, 2)
        with self.assertRaisesRegex(RuntimeError, "unknown_private_stock_member"):
            asyncio.run(MODULE.verify_members(Fake(), object(), 100, [{"id": 300}]))

    def test_source_contains_no_telegram_media_transfer_or_invite_export(self):
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("send_file(", content)
        self.assertNotIn("forward_messages(", content)
        self.assertNotIn("ExportChatInviteRequest", content)
        self.assertIn("CreateChannelRequest", content)
        self.assertIn("CINEX_PRIVATE_STOCK_READY", content)


if __name__ == "__main__":
    import unittest
    unittest.main()
