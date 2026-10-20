"""Non-publishing regression checks for catalogue idempotency and routing."""
import asyncio
import unittest
from unittest.mock import AsyncMock

from telethon.errors import MessageNotModifiedError

from film_relay.editing import edit_message_if_changed
from film_relay.category_runner import category_config
from film_relay.anime_catalog import series_title as anime_title


class CatalogueReliabilityTests(unittest.TestCase):
    def test_unchanged_index_is_not_fatal(self):
        client = type("FakeClient", (), {})()
        client.edit_message = AsyncMock(side_effect=MessageNotModifiedError(request=None))
        result = asyncio.run(edit_message_if_changed(client, "peer", 123, "same", parse_mode="html"))
        self.assertFalse(result)

    def test_changed_index_is_written(self):
        client = type("FakeClient", (), {})()
        client.edit_message = AsyncMock(return_value=None)
        self.assertTrue(asyncio.run(edit_message_if_changed(client, "peer", 123, "changed")))
        client.edit_message.assert_awaited_once()

    def test_romance_and_classic_dont_leak_to_comedy(self):
        config = category_config("comedie", {
            "COMEDIE_SOURCE_CHANNEL": "@comexflex @cineromances @filmsromantiques",
            "COMEDIE_SOURCE_CHANNELS": "@comexflex,@filmcomplets",
            "COMEDIE_PUBLIC_CHANNEL": "@CineXComediefr",
            "COMEDIE_PRIVATE_CHANNEL": "-1004305932623",
        })
        self.assertEqual(config["sources"], ["@comexflex"])

    def test_anime_source_signature_removed(self):
        self.assertEqual(anime_title("@Mangas fv Yu-Gi-Oh! Duel Monsters"),
                         "fv Yu-Gi-Oh! Duel Monsters")


if __name__ == "__main__":
    unittest.main()
