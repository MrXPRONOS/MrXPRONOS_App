"""Native Telegram button contract and HTML-caption regression checks."""
import asyncio
from types import SimpleNamespace as NS
import sys
import types
import unittest
from unittest.mock import patch

from film_relay.publication import (rich_caption, rich_video_title, url_button_rows,
                                    send_public_poster_with_buttons, film_folder_url, DEFAULT_FILM_FOLDER_URL,
                                    FILM_FOLDER_BUTTON_TEXT,
                                    library_button_rows, send_library_poster_with_buttons,
                                    publish_catalog_episode_pairs)


class RenderTests(unittest.TestCase):
    def test_html_escapes_and_emphasizes_metadata(self):
        rendered = rich_caption("🎬 Le Film <Danger>\nGenre: Comédie & Action\nSynopsis: Un <héros> voyage")
        self.assertIn("<b>🎬 Le Film &lt;Danger&gt;</b>", rendered)
        self.assertIn("<b>Genre :</b> Comédie &amp; Action", rendered)
        self.assertIn("<b>Synopsis :</b> <i>Un &lt;héros&gt; voyage</i>", rendered)
        self.assertNotIn("https://t.me/c/", rendered)
        self.assertIn("rejoins notre team", rendered)

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

    def test_private_library_fiche_has_exactly_rescue_and_folder_buttons(self):
        from unittest.mock import AsyncMock
        image = NS(media="source-photo")
        reader = NS(download_media=AsyncMock(return_value=b"original-poster"))
        bot = NS(send_file=AsyncMock(return_value=NS(id=77)))
        with patch("film_relay.rescue_channels.rescue_link_for",
                   return_value="https://t.me/+RescueExample123"):
            result = asyncio.run(send_library_poster_with_buttons(
                reader, bot, "@private_library", "@public_channel",
                image, "🎬 Film complet\\nSynopsis: Un film"))
        self.assertEqual(result.id, 77)
        keyboard = bot.send_file.await_args.kwargs["buttons"]
        self.assertEqual(len(keyboard), 2)
        self.assertEqual(keyboard[0][0].url, "https://t.me/+RescueExample123")
        self.assertEqual(keyboard[1][0].url, DEFAULT_FILM_FOLDER_URL)
        self.assertIn("Synopsis", bot.send_file.await_args.kwargs["caption"])

    def test_public_fiche_requires_existing_verified_rescue_invitation(self):
        from unittest.mock import AsyncMock
        reader = NS(download_media=AsyncMock(return_value=b"photo"))
        bot = NS(send_file=AsyncMock())
        with patch("film_relay.rescue_channels.rescue_link_for",
                   return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Secours"):
                asyncio.run(send_public_poster_with_buttons(
                    reader, bot, "@public", NS(media="photo"), "Mon Film",
                    "https://t.me/c/123456/12"))
        bot.send_file.assert_not_awaited()

    def test_complete_series_episode_public_pair_is_receipted_and_not_duplicated(self):
        from unittest.mock import AsyncMock
        poster = NS(photo=object(), media="photo", raw_text="Série épisode",
                    entities=None)
        video = NS(id=10, video=object(), document=NS(id=444, attributes=[]))
        row = {"season": 1, "episode": 2, "poster": poster,
               "video": video, "title": "Série exemple"}
        private_video = NS(video=object(), document=NS(id=444, attributes=[]))
        public_photo = NS(photo=object(), raw_text="Série épisode")
        public_video = NS(video=object(), document=NS(id=444, attributes=[]))

        async def get_messages(peer, ids):
            if peer == "@private":
                return private_video
            return public_photo if ids == 55 else public_video

        client = NS(get_messages=get_messages)
        series = {"title": "Série exemple", "episodes": {
            "1": {"2": {"message_id": 35}}}}
        catalogue = {"series": {"test": series}}
        saved = []
        with patch("film_relay.publication.send_public_poster_with_buttons",
                   new=AsyncMock(return_value=NS(id=55))) as poster_send, patch(
                   "film_relay.publication.post_public_video_after_poster",
                   new=AsyncMock(return_value=NS(id=56))) as video_send, patch(
                   "asyncio.sleep", new=AsyncMock()):
            asyncio.run(publish_catalog_episode_pairs(
                client, NS(), "@public", "@private", -1001234567890,
                series, [row], catalogue, lambda x: saved.append(x), 0))
            self.assertEqual(series["public_episode_posts"]["S01E02"],
                             {"poster": 55, "video": 56, "private_video": 35})
            self.assertEqual(len(saved), 1)
            asyncio.run(publish_catalog_episode_pairs(
                client, NS(), "@public", "@private", -1001234567890,
                series, [row], catalogue, lambda x: saved.append(x), 0))
            poster_send.assert_awaited_once()
            video_send.assert_awaited_once()

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
        with patch.dict(sys.modules, {"telethon": mocktelethon}), patch(
                "film_relay.publication.library_button_rows",
                return_value=[[("Secours", "https://t.me/+test")],
                              [(FILM_FOLDER_BUTTON_TEXT, DEFAULT_FILM_FOLDER_URL)]]):
            result = asyncio.run(send_public_poster_with_buttons(
                user, bot, "@cinex", NS(media="photo"),
                "🎬 Mon film\nGenre: Action",
                "https://t.me/c/12345/6", "https://t.me/+TEST",
            ))
        self.assertEqual(result.id, 66)
        self.assertEqual(bot.bytes, b"image data")
        self.assertEqual(bot.opts["parse_mode"], "html")
        self.assertEqual(bot.opts["buttons"][0][0].url, "https://t.me/c/12345/6")
        self.assertEqual(bot.opts["buttons"][1][0].url, DEFAULT_FILM_FOLDER_URL)
        self.assertEqual(bot.opts["buttons"][0][0].style, "success")
        self.assertEqual(bot.opts["buttons"][1][0].style, "primary")
        self.assertNotIn("https://t.me/c/", bot.opts["caption"])
        self.assertIn(DEFAULT_FILM_FOLDER_URL, bot.opts["caption"])
        self.assertIn("DÉCOUVRE ENCORE PLUS DE FILMS", bot.opts["caption"])


if __name__ == "__main__":
    unittest.main()
