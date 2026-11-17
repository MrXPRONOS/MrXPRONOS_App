"""Désir must continue after a vanished first source, but never ignore flood waits."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from film_relay.desir_runner import first_available_source


class DesireSourceFailoverTests(unittest.TestCase):
    def test_next_available_source(self):
        async def resolve(_client, name, _private, _public):
            if name == "@unavailable_source":
                raise ValueError("username not found")
            return ("source-peer", "private-peer", "public-peer")
        with patch("film_relay.desir_runner.preflight_user", side_effect=resolve):
            value = asyncio.run(first_available_source(
                object(), ["@unavailable_source", "@g_romanticfilm"],
                "-1001234567890", "@CineXDesirfr"))
        self.assertEqual(value, ("@g_romanticfilm", "source-peer", "private-peer", "public-peer"))

    def test_all_sources_missing_fails_before_upload(self):
        with patch("film_relay.desir_runner.preflight_user",
                   new_callable=AsyncMock, side_effect=ValueError("not found")):
            with self.assertRaisesRegex(RuntimeError, "aucune source accessible"):
                asyncio.run(first_available_source(
                    object(), ["@first_source", "@second_source"],
                    "-1001234567890", "@CineXDesirfr"))

    def test_flood_wait_is_not_swallowed(self):
        from telethon.errors import FloodWaitError
        with patch("film_relay.desir_runner.preflight_user",
                   new_callable=AsyncMock, side_effect=FloodWaitError(request=None, capture=30)):
            with self.assertRaises(FloodWaitError):
                asyncio.run(first_available_source(
                    object(), ["@first_source", "@second_source"],
                    "-1001234567890", "@CineXDesirfr"))


if __name__ == "__main__":
    unittest.main()
