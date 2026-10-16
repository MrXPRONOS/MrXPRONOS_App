"""Secondary public channel: native Telegram forward, provenance and durable replay."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from film_relay.runner import forward_public_message
from film_relay.state import State


class FakeForwarder:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def forward_messages(self, to, ids, *, from_peer):
        self.calls.append((to, ids, from_peer))
        if self.fail:
            raise RuntimeError("mirror channel temporarily unavailable")
        return NS(id=9876, original_source=from_peer, original_message_id=ids)


class MirrorTests(unittest.TestCase):
    def test_native_forward_preserves_original_source(self):
        bot_public = NS(username="cinex_public")
        mirror = NS(username="Torrent9SeriesFilm")
        client = FakeForwarder()
        result_id = asyncio.run(forward_public_message(client, bot_public, mirror, 77))
        self.assertEqual(result_id, 9876)
        self.assertEqual(client.calls, [(mirror, 77, bot_public)])

    def test_pending_before_forward_and_receipt_after(self):
        with TemporaryDirectory() as d:
            path = str(Path(d) / "state.json")
            state = State(path)
            state.add("source:11:12", "doc:123", 50, 80)
            target = "-100777"
            self.assertEqual(state.pending_mirrors(target), [("source:11:12", 80)])
            self.assertFalse(state.mirrored("source:11:12", target))
            state.mark_mirrored("source:11:12", target, 92)
            self.assertTrue(State(path).mirrored("source:11:12", target))
            self.assertEqual(State(path).pending_mirrors(target), [])

    def test_forward_error_keeps_primary_for_retry(self):
        with TemporaryDirectory() as d:
            path = str(Path(d) / "state.json")
            state = State(path)
            state.add("source:11:12", "doc:123", 50, 80)
            client = FakeForwarder(fail=True)
            with self.assertRaises(RuntimeError):
                asyncio.run(forward_public_message(client, "main", "mirror", 80))
            resumed = State(path)
            self.assertTrue(resumed.recorded("source:11:12", "doc:123"))
            self.assertEqual(resumed.pending_mirrors("-100777"), [("source:11:12", 80)])

    def test_reject_receipt_for_incomplete_primary(self):
        with TemporaryDirectory() as d:
            state = State(str(Path(d) / "state.json"))
            with self.assertRaises(ValueError):
                state.mark_mirrored("unknown", "-100777", 12)


if __name__ == "__main__":
    unittest.main()
