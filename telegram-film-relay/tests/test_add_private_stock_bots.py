"""Offline verification of trusted bot discovery, minimal permissions, and no media writes."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import add_private_stock_bots as app


class StockBotTests(TestCase):
    def identity(self, token):
        mapping = {
            "radar": {"id": 10, "username": "CineRadarFr_Bot", "is_bot": True},
            "radar_copy": {"id": 10, "username": "CineRadarFr_Bot", "is_bot": True},
            "action": {"id": 20, "username": "ActionCinemaBot", "is_bot": True},
            "series": {"id": 30, "username": "CineSeriesBot", "is_bot": True},
            "fake": {"id": 40, "username": "not_a_bot", "is_bot": False},
            "publisher": {"id": 50, "username": "NewPublisherBot", "is_bot": True},
        }
        return mapping[token]

    def test_deduplicate_aliases_from_many_github_secrets(self):
        env = {"CINEX_RADAR_BOT_TOKEN": "radar", "TELEGRAM_BOT_TOKEN": "radar_copy",
               "ACTION_BOT_TOKEN": "action", "SERIES_BOT_TOKEN": "series"}
        bots, missing, invalid = app.discover_bot_candidates(env, self.identity)
        self.assertEqual([(b["label"], b["id"]) for b in bots],
                         [("radar", 10), ("series", 30), ("action", 20)])
        self.assertEqual(invalid, [])
        self.assertEqual(len(missing), len(app.BOT_SECRETS) - 4)

    def test_mismatched_publisher_never_gets_admin_rights(self):
        env = {"CINEX_RADAR_BOT_TOKEN": "radar", "CINEX_PUBLISH_BOT_TOKEN": "publisher",
               "CINEX_PUBLISH_BOT_USERNAME": "@ExpectedPublisherBot"}
        bots, missing, invalid = app.discover_bot_candidates(env, self.identity)
        self.assertEqual([bot["id"] for bot in bots], [10])
        self.assertIn("publisher", invalid)

    def test_publisher_requires_explicit_expected_name(self):
        env = {"CINEX_RADAR_BOT_TOKEN": "radar", "CINEX_PUBLISH_BOT_TOKEN": "publisher"}
        bots, _, invalid = app.discover_bot_candidates(env, self.identity)
        self.assertEqual([bot["id"] for bot in bots], [10])
        self.assertIn("publisher", invalid)
        env["CINEX_PUBLISH_BOT_USERNAME"] = "@NewPublisherBot"
        bots, _, invalid = app.discover_bot_candidates(env, self.identity)
        self.assertEqual([bot["id"] for bot in bots], [10, 50])
        self.assertEqual(invalid, [])

    def test_invalid_bot_token_never_admitted(self):
        env = {"CINEX_RADAR_BOT_TOKEN": "radar", "ANIME_BOT_TOKEN": "fake"}
        bots, _, invalid = app.discover_bot_candidates(env, self.identity)
        self.assertEqual(len(bots), 1)
        self.assertEqual(invalid, ["anime"])

    def test_radar_verification_is_mandatory(self):
        with self.assertRaisesRegex(RuntimeError, "radar_identity_missing"):
            app.discover_bot_candidates({"SERIES_BOT_TOKEN": "series"}, self.identity)

    def test_only_post_permission_passes_least_privilege_check(self):
        minimal = SimpleNamespace(post_messages=True, delete_messages=False,
                                  invite_users=False, add_admins=False)
        self.assertTrue(app._minimal_rights(minimal))
        # Telegram can set the implicit 'other' bit on a channel administrator
        # without granting any extra actionable rights.
        self.assertTrue(app._minimal_rights(SimpleNamespace(post_messages=True, other=True)))
        self.assertFalse(app._minimal_rights(None))
        self.assertFalse(app._minimal_rights(SimpleNamespace(post_messages=True,
                                                             delete_messages=True)))
        self.assertFalse(app._minimal_rights(SimpleNamespace(post_messages=True,
                                                             add_admins=True)))

    def test_dry_run_never_opens_personal_session(self):
        with mock.patch.object(app, "discover_bot_candidates",
                               return_value=([{"id": 10, "username": "CineRadarFr_Bot",
                                               "label": "radar"}], [], [])):
            result = asyncio.run(app.attach(apply=False))
        self.assertEqual(result["verified"], 1)
        self.assertEqual(result["mode"], "dry_run")

    def test_source_cannot_create_channel_or_post_video(self):
        script = Path(app.__file__).read_text(encoding="utf-8")
        self.assertNotIn("CreateChannelRequest(", script)
        self.assertNotIn("ExportChatInviteRequest", script)
        self.assertNotIn("send_file(", script)
        self.assertNotIn("copyMessage", script)
        self.assertIn("CINEX_STOCK_BOTS_VERIFIED", script)

    def test_permitted_secrets_are_fixed_explicitly(self):
        names = [key for _, key in app.BOT_SECRETS]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("COMEDIE_BOT_TOKEN", names)
        self.assertIn("ANIME_BOT_TOKEN", names)


if __name__ == "__main__":
    import unittest
    unittest.main()
