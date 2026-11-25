"""Offline safeguards for Telegram administrator and emoji reaction rollout."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import cineradar_admin_rollout as rollout


class AdminRolloutTests(unittest.TestCase):
    def test_all_supported_channel_rights_except_admin_delegation(self):
        rights = rollout.full_channel_rights()
        self.assertTrue(rights.post_messages)
        self.assertTrue(rights.change_info)
        self.assertTrue(rights.edit_messages)
        self.assertTrue(rights.delete_messages)
        self.assertTrue(rights.invite_users)
        self.assertTrue(rights.ban_users)
        self.assertFalse(rights.add_admins)
        self.assertFalse(rights.anonymous)
        self.assertFalse(rights.manage_topics)

    def test_existing_bot_admin_with_add_admins_is_not_accepted(self):
        desired=rollout.full_channel_rights()
        actual=SimpleNamespace(**{
            key:bool(getattr(desired,key,False)) for key in (
                "change_info","post_messages","edit_messages","delete_messages",
                "ban_users","invite_users","manage_call","post_stories",
                "edit_stories","delete_stories","manage_direct_messages","manage_ranks",
            )
        },add_admins=True)
        self.assertFalse(rollout.rights_satisfied(actual,desired))
        actual.add_admins=False
        self.assertTrue(rollout.rights_satisfied(actual,desired))

    def test_known_named_and_numbered_secrets_are_deduplicated(self):
        candidates=rollout.bot_token_candidates({
            "CINE_RADAR_BOT_TOKEN":"token-a",
            "TELEGRAM_REACTION_BOT_03_TOKEN":"token-a",
            "ANIME_BOT_TOKEN":"token-b",
            "ALT_ANIME_BOT_TOKEN":"token-b",
            "TELEGRAM_REACTION_BOTS_JSON":'{"100":"token-c"}',
        })
        self.assertEqual(set(candidates),{"token-a","token-b","token-c"})

    def test_bot_identity_verified_never_by_secret_name_alone(self):
        def fake(url, data, headers):
            token=url.split("/bot",1)[1].rsplit("/",1)[0]
            if token=="fake":
                return 200,{"ok":True,"result":{"id":123,"username":"genuinebot","is_bot":False}}
            return 200,{"ok":True,"result":{"id":456,"username":"validbotname","is_bot":True}}
        found=rollout.resolve_bot_accounts(
            {"ANIME_BOT_TOKEN":"fake","ACTION_BOT_TOKEN":"valid"},fake,
        )
        self.assertEqual(found,[{"id":456,"username":"validbotname"}])

    def test_torrent9_metadata_exclusion(self):
        channel=SimpleNamespace(title="TORRENT-9 officiel",username=None)
        self.assertTrue(rollout.is_torrent9(channel))
        channel.title="Animation VF"
        self.assertFalse(rollout.is_torrent9(channel))

    def test_cursor_requires_authenticated_fingerprint(self):
        from scripts.actu_foot_github_vault import VaultSnapshot
        class Vault:
            def read(self,**kwargs):
                return VaultSnapshot(
                    {"version":1,"fingerprint":"old","cursor":94,"cooldown_until":0},
                    "sha",
                )
        state,sha=rollout.cursor_state(Vault(),["-1001111111111"])
        self.assertEqual(sha,"sha")
        self.assertEqual(state["cursor"],0)
        self.assertNotEqual(state["fingerprint"],"old")

    def test_never_posts_or_changes_webhooks(self):
        import inspect
        source=inspect.getsource(rollout)
        self.assertNotIn("deleteWebhook",source)
        self.assertNotIn("setWebhook",source)
        self.assertNotIn("sendMessage",source)
        self.assertNotIn("sendFile",source)
        self.assertNotIn("CreateChannelRequest(",source)
        self.assertNotIn("CLOUDFLARE_API_TOKEN",source)
        self.assertNotIn("SUPABASE_URL",source)


if __name__=="__main__":
    unittest.main()
