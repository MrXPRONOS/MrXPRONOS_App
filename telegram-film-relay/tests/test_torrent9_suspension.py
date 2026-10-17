"""Suspension Torrent9 : aucune publication dans le miroir depuis CinéX."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from film_relay import mirror_policy
from film_relay.runner import forward_public_message
from scripts import partnership_cycle


class Torrent9SuspensionTests(unittest.TestCase):
    def test_default_config_pauses_transfers(self):
        self.assertTrue(mirror_policy.torrent9_paused())
        data = json.loads(mirror_policy.POLICY.read_text(encoding="utf-8"))
        self.assertFalse(data["transfers_enabled"])

    def test_environment_can_only_force_additional_pause(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"override.json"
            p.write_text('{"transfers_enabled": true}',encoding="utf-8")
            with patch.object(mirror_policy,"POLICY",p), \
                 patch.dict(os.environ,{"CINEX_TORRENT9_PAUSED":"true"}):
                self.assertTrue(mirror_policy.torrent9_paused())

    def test_missing_or_invalid_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"missing.json"
            with patch.object(mirror_policy,"POLICY",p):
                self.assertTrue(mirror_policy.torrent9_paused())
            p.write_text("invalid json",encoding="utf-8")
            with patch.object(mirror_policy,"POLICY",p):
                self.assertTrue(mirror_policy.torrent9_paused())

    def test_public_forward_guard_blocks_without_telegram(self):
        class FakeClient:
            async def forward_messages(self,*args,**kwargs):
                raise AssertionError("UNEXPECTED_TELEGRAM_FORWARD")
        with self.assertRaisesRegex(RuntimeError,"suspendus"):
            asyncio.run(forward_public_message(FakeClient(),object(),object(),42))

    def test_category_forward_phase_is_skipped(self):
        with patch.object(partnership_cycle, "settings",
                          side_effect=AssertionError("should not read Telegram settings")):
            self.assertIsNone(asyncio.run(partnership_cycle.after("films")))

    def test_resume_never_changes_publications(self):
        # Un miroir désactivé ne doit pas rendre les canaux Films/Anime/Désir inactifs.
        self.assertFalse(mirror_policy.POLICY.read_text().find("transfers_enabled") == -1)


if __name__=="__main__":
    unittest.main()
