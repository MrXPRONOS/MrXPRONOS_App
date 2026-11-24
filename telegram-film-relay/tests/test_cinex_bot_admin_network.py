"""Offline guards for reconciling known bot admins in CineX channels."""
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import cinex_bot_admin_network as app


def identity(token):
    records = {
        "radar": {"id": 101, "username": "CineRadarFr_Bot", "is_bot": True},
        "telegram": {"id": 101, "username": "CineRadarFr_Bot", "is_bot": True},
        "anime": {"id": 102, "username": "CineAnimeBot", "is_bot": True},
        "editorial": {"id": 103, "username": "EditorialBot", "is_bot": True},
        "false": {"id": 104, "username": "NotReallyBot", "is_bot": False},
    }
    return records[token]


class NetworkAdminTests(unittest.TestCase):
    def test_all_allowlisted_secrets_are_known_and_distinct(self):
        keys = [key for _, key in app.ALL_BOT_SECRETS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertGreaterEqual(len(keys), 12)
        self.assertIn("CINEX_RADAR_BOT_TOKEN", keys)
        self.assertIn("COMEDIE_BOT_TOKEN", keys)
        self.assertIn("MRXPRONOS_CANAL_BOT_TOKEN", keys)

    def test_tokens_with_same_identity_are_only_one_bot(self):
        env = {
            "CINEX_RADAR_BOT_TOKEN": "radar",
            "TELEGRAM_BOT_TOKEN": "telegram",
            "ANIME_BOT_TOKEN": "anime",
            "EDITORIAL_TELEGRAM_BOT_TOKEN": "editorial",
        }
        candidates, missing, invalid = app.discover_network_bots(env, identity)
        self.assertEqual({b["id"] for b in candidates}, {101, 102, 103})
        self.assertEqual(invalid, [])
        self.assertEqual(len(missing), len(app.ALL_BOT_SECRETS) - len(env))

    def test_reaction_bots_numbered_and_json_bundle_are_discovered(self):
        env = {
            "CINEX_RADAR_BOT_TOKEN": "radar",
            "TELEGRAM_REACTION_BOT_03_TOKEN": "anime",
            "TELEGRAM_REACTION_BOTS_JSON": '{"100":"editorial","03":"anime"}',
        }
        candidates, _, invalid = app.discover_network_bots(env, identity)
        self.assertEqual({bot["id"] for bot in candidates}, {101, 102, 103})
        self.assertEqual(invalid, [])

    def test_slot16_alias_of_existing_publisher_is_not_an_extra_identity(self):
        env = {"CINEX_RADAR_BOT_TOKEN": "radar",
               "FOOTBALL_NEWS_BOT_TOKEN": "editorial",
               "TELEGRAM_REACTION_BOT_16_TOKEN": "editorial"}
        candidates, _, invalid = app.discover_network_bots(env, identity)
        self.assertEqual({bot["id"] for bot in candidates}, {101, 103})
        self.assertEqual(invalid, [])
        self.assertEqual(len(candidates), 2)

    def test_reaction_bot_secret_invalid_json_rejected(self):
        env = {"CINEX_RADAR_BOT_TOKEN": "radar",
               "TELEGRAM_REACTION_BOTS_JSON": '[{"03":"anime"}]'}
        with self.assertRaisesRegex(RuntimeError, "reaction_bot_secret_bundle_invalid"):
            app.discover_network_bots(env, identity)

    def test_reaction_bot_identity_must_be_telegram_bot(self):
        env = {"CINEX_RADAR_BOT_TOKEN": "radar",
               "TELEGRAM_REACTION_BOT_03_TOKEN": "false"}
        candidates, _, invalid = app.discover_network_bots(env, identity)
        self.assertEqual([b["id"] for b in candidates], [101])
        self.assertIn("reaction_03", invalid)

    def test_false_identity_is_never_approved(self):
        env = {
            "CINEX_RADAR_BOT_TOKEN": "radar",
            "PARTNERSHIP_BOT_TOKEN": "false",
        }
        candidates, missing, invalid = app.discover_network_bots(env, identity)
        self.assertEqual([b["id"] for b in candidates], [101])
        self.assertIn("partnership", invalid)

    def test_all_seven_checkpoints_required(self):
        row = {
            "public_username": "@fichiers_cloud",
            "public_id": -1001111111111,
            "rescue_channel_id": -1002222222222,
            "rescue_title": "Fichiers Cloud Secours",
        }
        with patch.object(app, "read_state",
                          return_value={"channels": {"@fichiers_cloud": row}}):
            with self.assertRaisesRegex(RuntimeError, "seven_official"):
                app.validated_checkpoints()

    def test_new_admin_has_only_posting_permission(self):
        rights = app.minimal_rights()
        self.assertTrue(rights.post_messages)
        for attr in ("add_admins", "delete_messages", "invite_users",
                     "ban_users", "edit_messages", "change_info"):
            self.assertFalse(getattr(rights, attr))

    def test_existing_permissions_are_preserved_when_post_added(self):
        rights = SimpleNamespace(delete_messages=True, post_messages=False)
        promoted = app.admin_with_post_rights(rights)
        self.assertTrue(promoted.post_messages)
        self.assertTrue(promoted.delete_messages)
        self.assertFalse(promoted.add_admins)

    def test_no_channel_creation_no_media_publication_no_secrets_logged(self):
        source = inspect.getsource(app)
        self.assertNotIn("CreateChannelRequest(", source)
        self.assertNotIn("send_file(", source)
        self.assertNotIn("ExportChatInviteRequest(", source)
        self.assertNotIn("bot_token", source.lower().split("print(")[-1])


if __name__ == "__main__":
    unittest.main()
