import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from telegram_reaction_coverage_audit import locate_radar_bot, reaction_policy


class ChannelReactionAuditTests(unittest.TestCase):
    def test_find_cine_radar_token_without_logging_or_using_other_bot(self):
        def fake(url, data, headers):
            username = "CineRadarFr_Bot" if "real-radar" in url else "SomeOtherBot"
            return 200, {"ok": True, "result": {"id": 42, "username": username}}
        token, bot_id = locate_radar_bot({
            "CINE_RADAR_BOT_TOKEN": "not-radar",
            "TELEGRAM_BOT_TOKEN": "real-radar",
        }, fake)
        self.assertEqual(token, "real-radar")
        self.assertEqual(bot_id, 42)

    def test_reaction_policy_does_not_invent_channel_permissions(self):
        self.assertEqual(reaction_policy({}), "unspecified")
        self.assertEqual(reaction_policy({"available_reactions": []}), "disabled")
        self.assertEqual(reaction_policy({"available_reactions": [
            {"type": "emoji", "emoji": "❤️"},
            {"type": "emoji", "emoji": "👍"},
        ]}), "heart_and_thumb_allowed")
        self.assertEqual(reaction_policy({"available_reactions": [
            {"type": "emoji", "emoji": "❤️"},
        ]}), "restricted")


if __name__ == "__main__":
    unittest.main()
