"""Offline tests for owner-only Telegram repair (no network or channels created)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, Mock, patch

from scripts import telegram_owner_channel_repair as mod


class OwnerRepairSafetyTests(unittest.TestCase):
    def test_stage_must_be_private_telegram_numeric_id(self):
        self.assertTrue(mod.valid_stage_id("-1001234567890"))
        for value in (None, "", "@teststage", "-123", "1001234567890",
                      "https://t.me/test", "-100a", False):
            self.assertFalse(mod.valid_stage_id(value))

    def test_legacy_channel_must_be_a_public_handle(self):
        self.assertEqual(mod.legacy_handle("@actucrypto_mrxp"), "@actucrypto_mrxp")
        for value in ("", None, "-1001234567890", "https://t.me/actucrypto_mrxp",
                      "@a", "@bad handle"):
            self.assertEqual(mod.legacy_handle(value), "")

    def test_configured_stage_selected_over_named_candidate(self):
        configured = Obj(peer_id="-1001234567890", broadcast=True,
                         username=None, title="Existing stage")
        candidate = Obj(peer_id="-1009999999999", broadcast=True,
                        username=None, title=mod.STAGE_TITLE)
        with patch("telethon.utils.get_peer_id", side_effect=lambda e: e.peer_id):
            entity, mode = mod.select_stage([candidate, configured], "-1001234567890")
        self.assertIs(entity, configured)
        self.assertEqual(mode, "configured")

    def test_ambiguous_stages_do_not_create_duplicate(self):
        one = Obj(broadcast=True, username=None, title=mod.STAGE_TITLE)
        two = Obj(broadcast=True, username=None, title=mod.STAGE_TITLE)
        with self.assertRaisesRegex(RuntimeError, "ambiguous_stage_titles"):
            mod.select_stage([one, two], "-1001111111111")

    def test_stage_creation_requires_secret_write_capability(self):
        with self.assertRaisesRegex(RuntimeError, "github_secret_update_unavailable"):
            mod.secret_key_credentials({})

    def test_correct_bot_required(self):
        import requests
        reply = Mock()
        reply.json.return_value = {
            "ok": True, "result": {"id": 123, "is_bot": True,
                                   "username": "other_bot"}}
        with patch.object(requests, "get", return_value=reply):
            with self.assertRaisesRegex(RuntimeError, "unexpected_bot_identity"):
                mod.check_bot("123:secret")

    def test_public_channel_cannot_be_a_private_stage(self):
        import asyncio
        entity = Obj(username="public_channel", broadcast=True)
        with self.assertRaisesRegex(RuntimeError, "stage_not_private_broadcast"):
            asyncio.run(mod.validate_stage_candidate(Mock(), entity, "configured"))

    def test_owner_rights_required_for_bot_promotion(self):
        import asyncio
        client = Mock()
        client.get_permissions = AsyncMock(return_value=Obj(is_creator=False))
        outcome = asyncio.run(mod.ensure_minimum_admin(
            client, Obj(), Obj(), Obj()))
        self.assertEqual(outcome, "owner_not_creator")
        self.assertEqual(client.get_permissions.await_count, 1)

    def test_existing_bot_admin_no_mutation(self):
        import asyncio
        client = Mock()
        client.get_permissions = AsyncMock(side_effect=[
            Obj(is_creator=True),
            Obj(is_creator=False, is_admin=True, post_messages=True),
        ])
        outcome = asyncio.run(mod.ensure_minimum_admin(
            client, Obj(), Obj(), Obj()))
        self.assertEqual(outcome, "already_admin")
        self.assertEqual(client.get_permissions.await_count, 2)

    def test_explicit_run_authorization_required(self):
        import asyncio
        with patch.dict(mod.os.environ, {"TELEGRAM_OWNER_REPAIR_AUTHORIZED": "false"}):
            with self.assertRaisesRegex(RuntimeError, "explicit_authorization_missing"):
                asyncio.run(mod.run())


if __name__ == "__main__":
    unittest.main()
