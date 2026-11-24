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

    def test_media_title_fallback_and_source_description(self):
        from film_relay.text import resolved_media_title, description_with_title
        poster = NS(raw_text="#Film\nGenre : Drame\nSynopsis : Une histoire.")
        video = NS(raw_text="", file=NS(name="Le.Dernier.Voyage.2025.FRENCH.1080p.mkv"))
        title = resolved_media_title(poster, video)
        self.assertEqual(title, "Le Dernier Voyage")
        details = description_with_title(title, poster.raw_text, "Langue : VF")
        self.assertEqual(details.splitlines()[0], title)
        self.assertIn("Synopsis : Une histoire.", details)
        self.assertIn("Langue : VF", details)
        self.assertNotIn("#Film", details)
        self.assertEqual(resolved_media_title(
            NS(raw_text="🎬 Titre : Supergirl\nAnnée : 2026"), video), "Supergirl")
        self.assertEqual(resolved_media_title(
            NS(raw_text="Synopsis : Un voyage\nUne histoire inconnue."),
            NS(raw_text="", file=NS(name="video_123456.mp4"))), "Titre non identifié")
        self.assertEqual(resolved_media_title(
            NS(raw_text=""), NS(raw_text="", file=NS(name="Supergirl.2026.1080p.mkv"))),
            "Supergirl")
        self.assertEqual(resolved_media_title(
            NS(raw_text="Série Exemple"), video, preferred="Série Exemple S02E03"),
            "Série Exemple S02E03")

    def test_styled_video_title(self):
        self.assertEqual(rich_video_title("Le Film & Moi"), "<b>🎞️ Le Film &amp; Moi</b>")

    def test_telegram_keyboard_rows(self):
        r = url_button_rows("https://t.me/c/1234/56", "https://t.me/+ABC123")
        self.assertEqual(r[0][0], ("🎬 VOIR LE FILM", "https://t.me/c/1234/56"))
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

    def test_private_library_fiche_has_exactly_three_verified_buttons(self):
        from unittest.mock import AsyncMock
        download = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        image = NS(media="source-photo")
        reader = NS(download_media=AsyncMock(return_value=b"original-poster"))
        bot = NS(send_file=AsyncMock(return_value=NS(id=77)))
        result = asyncio.run(send_library_poster_with_buttons(
            reader, bot, "@private_library", "@CineXFilms_vf",
            image, "🎬 Film complet\\nSynopsis: Un film",
            download_url=download))
        self.assertEqual(result.id, 77)
        keyboard = bot.send_file.await_args.kwargs["buttons"]
        self.assertEqual(len(keyboard), 3)
        self.assertEqual([row[0].url for row in keyboard],
                         ["https://t.me/cinexfilms_vf", DEFAULT_FILM_FOLDER_URL,
                          download])
        self.assertEqual([row[0].text for row in keyboard],
                         ["📢 REJOINDRE LE CANAL", FILM_FOLDER_BUTTON_TEXT,
                          "⬇️ TÉLÉCHARGER"])
        self.assertIn("Synopsis", bot.send_file.await_args.kwargs["caption"])

    def test_private_library_rejects_absent_or_fake_download(self):
        from unittest.mock import AsyncMock
        bot = NS(send_file=AsyncMock())
        reader = NS(download_media=AsyncMock(return_value=b"photo"))
        for bad in (None, "", "https://example.com/movie"):
            with self.subTest(link=bad), self.assertRaises(RuntimeError):
                asyncio.run(send_library_poster_with_buttons(
                    reader, bot, "@private", "@CineXFilms_vf",
                    NS(media="photo"), "Film", download_url=bad))
        bot.send_file.assert_not_awaited()

    def test_public_labels_match_category_and_count(self):
        from film_relay.publication import (
            video_labels, complete_public_video_rows, library_button_rows)
        self.assertEqual(video_labels("series"),
                         ("📺 VOIR LA SÉRIE", "⬇️ TÉLÉCHARGER LES VIDÉOS"))
        self.assertEqual(video_labels("anime"),
                         ("🌸 VOIR L'ANIMÉ", "⬇️ TÉLÉCHARGER LES VIDÉOS"))
        self.assertEqual(video_labels("films"),
                         ("🎬 VOIR LE FILM", "⬇️ TÉLÉCHARGER LA VIDÉO"))
        central = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        with patch("film_relay.rescue_channels.rescue_link_for",
                   return_value="https://t.me/+VerifiedRescueDemo123"):
            for kind in ("series", "anime", "films"):
                rows = complete_public_video_rows(
                    "https://t.me/c/1234567890/35", central,
                    public_peer="@CineXFilms_vf",
                    watch_label=video_labels(kind)[0])
                self.assertEqual(len(rows), 4)
                self.assertEqual(rows[0][0][0], video_labels(kind)[0])
                self.assertEqual(rows[1][0][0], video_labels(kind)[1])
        self.assertEqual(len(library_button_rows("@CineXFilms_vf", central)), 3)

    def test_existing_private_poster_is_updated_in_place_without_repost(self):
        from unittest.mock import AsyncMock
        from film_relay.publication import (
            library_button_rows, make_button_keyboard,
            ensure_library_poster_buttons, verify_library_poster_buttons)
        download = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        original = NS(id=99, photo=object(), buttons=[
            [NS(text="🛟 Secours", url="https://t.me/+LegacyRescue123456")],
            [NS(text="Dossier", url=DEFAULT_FILM_FOLDER_URL)]])
        publisher = NS(edit_reply_markup=AsyncMock())
        async def edit(peer, mid, *, buttons):
            original.buttons = buttons
        publisher.edit_reply_markup.side_effect = edit
        user = NS(get_messages=AsyncMock(return_value=original))
        asyncio.run(ensure_library_poster_buttons(
            user, publisher, "@private", 99, "@CineXFilms_vf", download))
        self.assertTrue(verify_library_poster_buttons(
            original, "@CineXFilms_vf", download))
        self.assertEqual(len(original.buttons), 3)
        publisher.edit_reply_markup.assert_awaited_once()
        asyncio.run(ensure_library_poster_buttons(
            user, publisher, "@private", 99, "@CineXFilms_vf", download))
        publisher.edit_reply_markup.assert_awaited_once()  # idempotent

    def test_private_download_link_must_be_a_real_cineradar_link(self):
        from film_relay.publication import library_button_rows
        for fake in ("https://t.me/c/123/4", "https://example.com/film",
                     "https://t.me/CineRadarFr_Bot?start=bad"):
            with self.subTest(link=fake):
                with self.assertRaises(RuntimeError):
                    library_button_rows("@CineXFilms_vf", fake)

    def test_public_fiche_requires_existing_verified_rescue_invitation(self):
        from unittest.mock import AsyncMock
        reader = NS(download_media=AsyncMock(return_value=b"photo"))
        bot = NS(send_file=AsyncMock())
        with patch("film_relay.rescue_channels.rescue_link_for",
                   return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Secours"):
                asyncio.run(send_public_poster_with_buttons(
                    reader, bot, "@public", NS(media="photo"), "Mon Film",
                    "https://t.me/c/123456/12",
                    download_url="https://t.me/CineRadarFr_Bot?start=d_" + "A"*24))
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
            "1": {"2": {"message_id": 35, "download_url":
                         "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24}}}}
        catalogue = {"series": {"test": series}}
        saved = []
        with patch("film_relay.publication.send_public_poster_with_buttons",
                   new=AsyncMock(return_value=NS(id=55))) as poster_send, patch(
                   "film_relay.publication.post_public_video_by_bot_copy",
                   new=AsyncMock(return_value=NS(id=56))) as video_send, patch(
                   "asyncio.sleep", new=AsyncMock()):
            asyncio.run(publish_catalog_episode_pairs(
                client, NS(copy_message=AsyncMock()), "@public", "@private", -1001234567890,
                series, [row], catalogue, lambda x: saved.append(x), 0))
            self.assertEqual(series["public_episode_posts"]["S01E02"],
                             {"poster": 55, "video": 56, "private_video": 35})
            self.assertGreaterEqual(len(saved), 2)
            asyncio.run(publish_catalog_episode_pairs(
                client, NS(), "@public", "@private", -1001234567890,
                series, [row], catalogue, lambda x: saved.append(x), 0))
            poster_send.assert_awaited_once()
            video_send.assert_awaited_once()
            self.assertEqual(poster_send.await_args.kwargs["watch_label"],
                             "📺 VOIR LA SÉRIE")
            self.assertEqual(video_send.await_args.kwargs["download_url"],
                             "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24)

    def test_verified_bot_video_carries_same_four_buttons_as_its_poster(self):
        from unittest.mock import AsyncMock
        from film_relay.publication import (
            post_public_video_by_bot_copy, complete_public_video_rows,
            make_button_keyboard,
        )
        public = NS(id=-1001234567890, username="CineXFilms_vf")
        private = NS(id=-1002345678901)
        movie_link = "https://t.me/c/2345678901/50"
        download_link = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        rescue_link = "https://t.me/+VerifiedRescueDemo123"
        video = NS(id=50, document=NS(id=987, attributes=[]), video=object())
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=rescue_link):
            keyboard = make_button_keyboard(complete_public_video_rows(
                movie_link, download_link, public_peer=public))
            poster = NS(id=70, photo=object(), raw_text="Mon film", buttons=keyboard)
            posted = NS(id=71, document=NS(id=987, attributes=[]),
                        video=object(), buttons=keyboard,
                        raw_text="🎞️ Mon film\n#CINEX_VIDEO_24H_V1")
            async def read(channel, ids):
                return poster if ids == 70 else posted
            async def recent(channel, limit):
                yield poster
            reader = NS(get_messages=read, iter_messages=recent)
            bot = NS(copy_message=AsyncMock(return_value=NS(id=71)))
            result = asyncio.run(post_public_video_by_bot_copy(
                reader, bot, public, private, video, 70, movie_link,
                "Mon film", download_url=download_link))
        self.assertEqual(result.id, 71)
        self.assertIn("#CINEX_VIDEO_24H_V1",
                      bot.copy_message.await_args.kwargs["caption"])
        self.assertEqual(len(bot.copy_message.await_args.kwargs["buttons"]), 4)
        self.assertEqual(
            [row[0].url for row in bot.copy_message.await_args.kwargs["buttons"]],
            [movie_link, download_link, rescue_link, DEFAULT_FILM_FOLDER_URL])

    def test_raw_inline_markup_is_verified_without_convenience_buttons(self):
        from film_relay.publication import (
            complete_public_video_rows, verify_complete_public_video_poster,
            verify_complete_public_video_keyboard, make_button_keyboard)
        public = NS(username="CineXFilms_vf")
        link = "https://t.me/c/2222222222/31"
        download = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        with patch("film_relay.rescue_channels.rescue_link_for",
                   return_value="https://t.me/+VerifiedRescueDemo123"):
            expected = complete_public_video_rows(link, download, public_peer=public)
            keyboard = make_button_keyboard(expected)
            message = NS(photo=object(), buttons=None,
                         reply_markup=NS(rows=[NS(buttons=row) for row in keyboard]))
            self.assertTrue(verify_complete_public_video_poster(message, public, link, download))
            self.assertTrue(verify_complete_public_video_keyboard(message, public, link, download))
            message.buttons = keyboard[:3]
            self.assertFalse(verify_complete_public_video_poster(message, public, link, download))
            message.buttons = None
            message.reply_markup.rows.pop()
            self.assertFalse(verify_complete_public_video_keyboard(message, public, link, download))

    def test_public_poster_with_stale_series_label_blocks_video_copy(self):
        from unittest.mock import AsyncMock
        from film_relay.publication import (
            complete_public_video_rows, make_button_keyboard,
            post_public_video_by_bot_copy,
            verify_complete_public_video_poster)
        public = NS(id=-1001234567890, username="seriesvf_cinex")
        private = NS(id=-1002222222222)
        link = "https://t.me/c/2222222222/31"
        download = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        rescue = "https://t.me/+VerifiedRescueDemo123"
        with patch("film_relay.rescue_channels.rescue_link_for",
                   return_value=rescue):
            stale = make_button_keyboard(complete_public_video_rows(
                link, download, public_peer=public,
                watch_label="📺 VOIR L'ÉPISODE"))
            poster = NS(id=77, photo=object(), buttons=stale)
            self.assertFalse(verify_complete_public_video_poster(
                poster, public, link, download, watch_label="📺 VOIR LA SÉRIE"))
            bot = NS(copy_message=AsyncMock())
            async def read(peer, ids):
                return poster
            async def latest(peer, limit):
                yield poster
            user = NS(get_messages=read, iter_messages=latest)
            movie = NS(id=31, video=object(),
                       document=NS(id=111, attributes=[]))
            with self.assertRaisesRegex(RuntimeError, "boutons conformes"):
                asyncio.run(post_public_video_by_bot_copy(
                    user, bot, public, private, movie, 77, link,
                    "Série", download_url=download,
                    watch_label="📺 VOIR LA SÉRIE"))
            bot.copy_message.assert_not_awaited()

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
                "film_relay.rescue_channels.rescue_link_for",
                return_value="https://t.me/+VerifiedRescueDemo123"):
            result = asyncio.run(send_public_poster_with_buttons(
                user, bot, "@cinex", NS(media="photo"),
                "🎬 Mon film\nGenre: Action",
                "https://t.me/c/12345/6", "https://t.me/+TEST",
                download_url="https://t.me/CineRadarFr_Bot?start=d_" + "A"*24,
            ))
        self.assertEqual(result.id, 66)
        self.assertEqual(bot.bytes, b"image data")
        self.assertEqual(bot.opts["parse_mode"], "html")
        self.assertEqual(bot.opts["buttons"][0][0].url, "https://t.me/c/12345/6")
        self.assertEqual(bot.opts["buttons"][1][0].url,
                         "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24)
        self.assertEqual(bot.opts["buttons"][2][0].url, "https://t.me/+VerifiedRescueDemo123")
        self.assertEqual(bot.opts["buttons"][3][0].url, DEFAULT_FILM_FOLDER_URL)
        self.assertEqual(len(bot.opts["buttons"]), 4)
        self.assertEqual(bot.opts["buttons"][0][0].style, "success")
        self.assertEqual(bot.opts["buttons"][1][0].style, "success")
        self.assertEqual(bot.opts["buttons"][2][0].style, "danger")
        self.assertEqual(bot.opts["buttons"][3][0].style, "primary")
        self.assertNotIn("https://t.me/c/", bot.opts["caption"])
        self.assertIn(DEFAULT_FILM_FOLDER_URL, bot.opts["caption"])
        self.assertIn("DÉCOUVRE ENCORE PLUS DE FILMS", bot.opts["caption"])


if __name__ == "__main__":
    unittest.main()
