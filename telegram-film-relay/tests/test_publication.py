"""Native Telegram button contract and HTML-caption regression checks."""
import asyncio
from types import SimpleNamespace as NS
import sys
import types
import unittest
from unittest.mock import patch

from film_relay.publication import (rich_caption, rich_video_title, url_button_rows,
                                    send_public_poster_with_buttons, film_folder_url, DEFAULT_FILM_FOLDER_URL,
                                    FILM_FOLDER_BUTTON_TEXT)


class RenderTests(unittest.TestCase):
    def test_html_escapes_and_emphasizes_metadata(self):
        rendered = rich_caption("🎬 Le Film <Danger>\nGenre: Comédie & Action\nSynopsis: Un <héros> voyage")
        self.assertIn("<b>🎬 Le Film &lt;Danger&gt;</b>", rendered)
        self.assertIn("<b>Genre :</b> Comédie &amp; Action", rendered)
        self.assertIn("<b>Synopsis :</b> <i>Un &lt;héros&gt; voyage</i>", rendered)
        self.assertNotIn("https://t.me/c/", rendered)
        self.assertIn("bouton", rendered)

    def test_styled_video_title(self):
        self.assertEqual(rich_video_title("Le Film & Moi"), "<b>🎞️ Le Film &amp; Moi</b>")

    def test_telegram_keyboard_rows(self):
        r = url_button_rows("https://t.me/c/1234/56", "https://t.me/+ABC123")
        self.assertEqual(r[0][0], ("🎬 REGARDER LE FILM", "https://t.me/c/1234/56"))
        self.assertEqual(len(r), 2)
        self.assertEqual(len(url_button_rows("https://t.me/c/1234/56")), 2)
        self.assertEqual(r[1][0], (FILM_FOLDER_BUTTON_TEXT, DEFAULT_FILM_FOLDER_URL))
        with self.assertRaises(ValueError):
            url_button_rows("https://google.com/example")

    def test_shared_folder_url_replaces_old_private_invitation(self):
        self.assertEqual(film_folder_url(), "https://t.me/addlist/ZmW4vfwcrMAwNzJk")
        movie = "https://t.me/c/12345/6"
        self.assertEqual(url_button_rows(movie, "https://t.me/+OLDPRIVATE")[1][0][1],
                         DEFAULT_FILM_FOLDER_URL)
        self.assertEqual(url_button_rows(movie)[0][0][1], movie)

    def test_send_photo_with_inline_keyboard(self):
        class FakeReader:
            async def download_media(self, media, file):
                self.calls = (media, file)
                return b"image data"

        class FakeBot:
            async def send_file(self, channel, image, **kwargs):
                self.channel, self.bytes, self.opts = channel, image.read(), kwargs
                return NS(id=66)

        mocktelethon = types.ModuleType("telethon")
        mocktelethon.Button = NS(url=lambda label, url, **kw: (label, url, kw.get("style")))
        user, bot = FakeReader(), FakeBot()
        with patch.dict(sys.modules, {"telethon": mocktelethon}):
            result = asyncio.run(send_public_poster_with_buttons(
                user, bot, "@cinex", NS(media="photo"),
                "🎬 Mon film\nGenre: Action",
                "https://t.me/c/12345/6", "https://t.me/+TEST",
            ))
        self.assertEqual(result.id, 66)
        self.assertEqual(bot.bytes, b"image data")
        self.assertEqual(bot.opts["parse_mode"], "html")
        self.assertEqual(bot.opts["buttons"][0][0][1], "https://t.me/c/12345/6")
        self.assertEqual(bot.opts["buttons"][1][0][1], DEFAULT_FILM_FOLDER_URL)
        self.assertEqual(bot.opts["buttons"][0][0][2], "success")
        self.assertEqual(bot.opts["buttons"][1][0][2], "danger")
        self.assertNotIn("https://t.me/c/", bot.opts["caption"])
        self.assertIn(DEFAULT_FILM_FOLDER_URL, bot.opts["caption"])
        self.assertIn("REJOINS LA TEAM", bot.opts["caption"])


if __name__ == "__main__":
    unittest.main()
