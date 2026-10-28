"""Offline regression checks: never treat Telegram link previews as real photos."""
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from film_relay.media_guard import valid_photo_message, require_photo
from film_relay.desir_runner import post_public


class MediaGuardTests(unittest.TestCase):
    def test_webpage_preview_is_not_a_photo(self):
        preview = NS(photo=None, media=NS(webpage=object()), noforwards=False)
        self.assertFalse(valid_photo_message(preview))
        with self.assertRaisesRegex(ValueError, "photo Telegram"):
            require_photo(preview)

    def test_protected_photo_rejected(self):
        photo = NS(photo=object(), media=NS(photo=object()), noforwards=True)
        self.assertFalse(valid_photo_message(photo))

    def test_media_without_photo_is_rejected(self):
        fake = NS(photo=object(), media=NS(webpage=object()), noforwards=False)
        self.assertFalse(valid_photo_message(fake))

    def test_valid_photo_preserved(self):
        media = NS(photo=object())
        photo = NS(photo=media.photo, media=media, noforwards=False)
        self.assertTrue(valid_photo_message(photo))
        self.assertIs(require_photo(photo), media)

    def test_public_post_without_photo_never_sends_text(self):
        bot = NS(send_file=AsyncMock(), send_message=AsyncMock())
        user = NS(download_media=AsyncMock())
        item = NS(poster=None)
        with self.assertRaisesRegex(ValueError, "affiche"):
            asyncio.run(post_public(bot, user, "@Example", item, "Film",
                                    "https://t.me/c/123456/5", ""))
        bot.send_file.assert_not_awaited()
        bot.send_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
