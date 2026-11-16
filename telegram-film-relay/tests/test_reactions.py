"""Offline regression tests for the CineX post-film reactions prompt."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from film_relay.reactions import REACTION_TEXT, REACTION_HTML, PINNED_TEXT, PINNED_HTML, send_after_film


class DummyState:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {}

    def save(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")


class DummyClient:
    def __init__(self):
        self.messages = []
        self.sent = []

    async def iter_messages(self, channel, limit=70):
        for m in self.messages[:limit]:
            yield m

    async def send_message(self, channel, text, reply_to=None, formatting_entities=None):
        self.sent.append((channel, text, reply_to, formatting_entities))
        return NS(id=220)


class ReactionTests(unittest.TestCase):
    def test_copy(self):
        self.assertIn("cœur", REACTION_TEXT)
        self.assertIn("Abonnez-vous", PINNED_TEXT)
        self.assertEqual(len(PINNED_TEXT.splitlines()), 1)
        self.assertIn("<b>", REACTION_HTML)
        self.assertIn("<i>", REACTION_HTML)
        self.assertIn("<blockquote>", REACTION_HTML)
        self.assertIn("<blockquote>", PINNED_HTML)

    def test_private_once_and_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DummyState(Path(tmp) / "receipts.json")
            client = DummyClient()
            sent = asyncio.run(send_after_film(client, None, "private", 100,
                                              state, "movie-a", audience="private"))
            self.assertTrue(sent)
            self.assertEqual(len(client.sent), 1)
            self.assertEqual(client.sent[0][:3], ("private", REACTION_TEXT, 100))
            self.assertEqual(len(client.sent[0][3]), 4)
            self.assertFalse(asyncio.run(send_after_film(
                client, None, "private", 100, state, "movie-a", audience="private")))
            self.assertEqual(len(client.sent), 1)
            self.assertEqual(json.loads(state.path.read_text())["reaction_prompts"]["private:movie-a"], 220)

    def test_detects_existing_reply_after_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DummyState(Path(tmp) / "receipts.json")
            client = DummyClient()
            client.messages = [NS(id=331, raw_text=REACTION_TEXT,
                                  reply_to=NS(reply_to_msg_id=42))]
            self.assertFalse(asyncio.run(send_after_film(
                client, None, "channel", 42, state, "movie-b", audience="private")))
            self.assertEqual(client.sent, [])
            self.assertEqual(state.data["reaction_prompts"]["private:movie-b"], 331)

    def test_public_bot_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DummyState(Path(tmp) / "receipts.json")
            client = DummyClient()
            bot = NS(send_message=AsyncMock(return_value=NS(id=444)))
            self.assertTrue(asyncio.run(send_after_film(
                client, bot, "public", 101, state, "movie-c", audience="public")))
            bot.send_message.assert_awaited_once_with(
                "public", REACTION_HTML, parse_mode="html", reply_to_message_id=101)

    def test_failed_send_does_not_mark_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = DummyState(Path(tmp) / "receipts.json")
            client = DummyClient()
            bot = NS(send_message=AsyncMock(side_effect=RuntimeError("error")))
            self.assertFalse(asyncio.run(send_after_film(
                client, bot, "public", 101, state, "movie-d", audience="public")))
            self.assertEqual(state.data.get("reaction_prompts"), {})


if __name__ == "__main__":
    unittest.main()
