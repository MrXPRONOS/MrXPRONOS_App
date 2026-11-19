"""Off-line guardrails for private invitations and destructive Telegram actions."""
from __future__ import annotations
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from film_relay.rescue_links_runtime import fingerprint, write_runtime, get_existing_invite
from film_relay.rescue_channels import rescue_link_for, write_state


class Phase1SecurityTests(unittest.TestCase):
    def test_runtime_file_is_not_in_git_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            invite = "https://t.me/+abcdefghijklmnop"
            public = "@cinexfilms_vf"
            ledger = path / "rescue.json"
            runtime = path / "runtime.json"
            write_state({"channels":{public:{
                "public_username":public,
                "rescue_channel_id":-100987654321,
                "invite_link":invite}}},ledger)
            write_runtime(runtime,{"channels":{public:{
                "url":invite,
                "rescue_channel_id":-100987654321}}})
            self.assertNotIn(invite,ledger.read_text(encoding="utf-8"))
            self.assertIn(fingerprint(invite),ledger.read_text(encoding="utf-8"))
            with patch.dict(os.environ,{"CINEX_RESCUE_RUNTIME_FILE":str(runtime)}):
                self.assertEqual(rescue_link_for(public,path=ledger),invite)
            self.assertEqual(runtime.stat().st_mode & 0o777,0o600)

    def test_wrong_invite_never_reaches_public_buttons(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            username="@cinexfilms_vf"
            ledger=path/"rescue.json"
            runtime=path/"runtime.json"
            write_state({"channels":{username:{
                "public_username":username,"rescue_channel_id":-100987654321,
                "invite_link":"https://t.me/+abcdefghijklmnop"}}},ledger)
            write_runtime(runtime,{"channels":{username:{
                "url":"https://t.me/+1234567890abcdef",
                "rescue_channel_id":-100987654321}}})
            with patch.dict(os.environ,{"CINEX_RESCUE_RUNTIME_FILE":str(runtime)}):
                self.assertIsNone(rescue_link_for(username,path=ledger))


class InviteTelegramTests(unittest.IsolatedAsyncioTestCase):
    async def test_use_verified_primary_without_creating_another_invitation(self):
        from telethon import functions
        link="https://t.me/+abcdefghijklmnop"
        client=AsyncMock()
        client.get_me.return_value=SimpleNamespace(id=1)
        client.side_effect=lambda request: SimpleNamespace(
            full_chat=SimpleNamespace(exported_invite=SimpleNamespace(link=link,revoked=False)))
        got=await get_existing_invite(client,SimpleNamespace(),expected_sha=fingerprint(link))
        self.assertEqual(got,link)
        self.assertEqual(client.await_count,1)

    async def test_wrong_primary_does_not_override_expected_hash(self):
        link="https://t.me/+abcdefghijklmnop"
        client=AsyncMock()
        client.get_me.return_value=SimpleNamespace(id=1)
        async def responder(request):
            if request.__class__.__name__=="GetFullChannelRequest":
                return SimpleNamespace(full_chat=SimpleNamespace(
                    exported_invite=SimpleNamespace(link="https://t.me/+ffffffffffffffff",revoked=False)))
            return SimpleNamespace(invites=[])
        client.side_effect=responder
        self.assertIsNone(await get_existing_invite(client,SimpleNamespace(),
                                                      expected_sha=fingerprint(link)))


if __name__=="__main__":
    unittest.main()
