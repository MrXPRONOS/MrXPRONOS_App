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
            self.assertIsNone(asyncio.run(partnership_cycle.after("desir")))

    def test_resume_never_changes_publications(self):
        # Un miroir désactivé ne doit pas rendre les canaux Films/Anime/Désir inactifs.
        self.assertFalse(mirror_policy.POLICY.read_text().find("transfers_enabled") == -1)


    def test_scoped_film_forward_does_not_unpause_other_categories(self):
        self.assertTrue(mirror_policy.torrent9_paused())
        self.assertTrue(partnership_cycle.film_single_transfer_enabled())
        with patch.dict(os.environ, {"CINEX_SINGLE_FILM_FORWARD_PAUSED": "true"}):
            self.assertFalse(partnership_cycle.film_single_transfer_enabled())

    def test_one_candidate_per_film_and_newest_first(self):
        data = {
            "processed": {
                "old": {"public_message_id": 31},
                "done": {"public_message_id": 32},
                "new": {"public_message_id": 33},
            },
            "mirrors": {"-1002909390103": {"done": 990}},
        }
        self.assertEqual(
            partnership_cycle.pending_main_films(data, "-1002909390103"),
            [("new", 33), ("old", 31)],
        )

    def test_real_forward_code_sends_exactly_one_main_film(self):
        from types import SimpleNamespace as N
        from unittest.mock import AsyncMock
        with tempfile.TemporaryDirectory() as folder:
            state_file = Path(folder) / "state.json"
            state_file.write_text(json.dumps({
                "processed": {
                    "film-a": {"public_message_id": 51},
                    "film-b": {"public_message_id": 52},
                    "film-c": {"public_message_id": 53},
                },
                "mirrors": {}
            }), encoding="utf-8")
            source = N(peer_id=-100123, noforwards=False)
            target = N(peer_id=-1002909390103, broadcast=True)
            client = N(
                get_me=AsyncMock(return_value=N(id=42)),
                get_permissions=AsyncMock(return_value=N(is_creator=True)),
                get_messages=AsyncMock(return_value=N(id=53, noforwards=False)),
                forward_messages=AsyncMock(return_value=N(id=3000)),
                disconnect=AsyncMock(),
            )
            async def lookup(_client, name):
                return source if name == "@CineXMain" else target
            with patch.object(partnership_cycle, "film_single_transfer_enabled",
                              return_value=True), \
                 patch.object(partnership_cycle, "settings",
                              return_value=("@CineXMain", "@Torrent9SeriesFilms", state_file, None)), \
                 patch.object(partnership_cycle, "session",
                              new_callable=AsyncMock, return_value=(client, 123, "fake")), \
                 patch.object(partnership_cycle, "resolve_peer", side_effect=lookup), \
                 patch.object(partnership_cycle, "existing_native_forwards",
                              new_callable=AsyncMock, return_value={}), \
                 patch.object(partnership_cycle.utils, "get_peer_id",
                              side_effect=lambda entity: entity.peer_id):
                count = asyncio.run(partnership_cycle.forward_one_main_film())
            self.assertEqual(count, 1)
            client.forward_messages.assert_awaited_once_with(
                target, 53, from_peer=source
            )
            updated = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(
                updated["mirrors"]["-1002909390103"],
                {"film-c": 3000},
            )

if __name__=="__main__":
    unittest.main()
