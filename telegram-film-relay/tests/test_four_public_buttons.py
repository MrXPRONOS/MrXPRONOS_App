"""CineX public media contract: photo with four verified buttons THEN video."""
import asyncio
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from film_relay.publication import (
    complete_public_video_rows, verify_complete_public_video_poster,
    send_public_poster_with_buttons, post_public_video_after_poster,
)

PRIVATE = "https://t.me/c/4392607284/56"
DOWNLOAD = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
RESCUE = "https://t.me/+VerifiedRescueDemo123"
FOLDER = "https://t.me/addlist/ZmW4vfwcrMAwNzJk"


class FourButtonsTests(unittest.TestCase):
    def test_four_url_targets_in_exact_order(self):
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=RESCUE):
            rows = complete_public_video_rows(PRIVATE, DOWNLOAD, public_peer="@CineXFilms_vf")
        self.assertEqual([row[0][1] for row in rows],
                         [PRIVATE, DOWNLOAD, RESCUE, FOLDER])
        self.assertEqual(len(rows), 4)
        self.assertEqual([len(x) for x in rows], [1, 1, 1, 1])
        self.assertIn("VOIR LE FILM", rows[0][0][0])
        self.assertIn("TÉLÉCHARGER", rows[1][0][0])

    def test_episode_has_the_same_four_buttons(self):
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=RESCUE):
            rows = complete_public_video_rows(
                PRIVATE, DOWNLOAD, public_peer="@seriesvf_cinex",
                watch_label="📺 VOIR L'ÉPISODE")
        self.assertIn("VOIR L'ÉPISODE", rows[0][0][0])
        self.assertEqual([row[0][1] for row in rows],
                         [PRIVATE, DOWNLOAD, RESCUE, FOLDER])

    def test_all_six_main_channels_need_their_own_rescue(self):
        cats = ["@CineXFilms_vf", "@seriesvf_cinex", "@CineXDesirfr",
                "@comedie_vf_test", "@CineXAnimeFR", "@filmsaction2026vf"]
        for name in cats:
            with self.subTest(name=name), patch(
                "film_relay.rescue_channels.rescue_link_for",
                return_value=RESCUE):
                rows = complete_public_video_rows(PRIVATE, DOWNLOAD,
                                                   public_peer=name)
                self.assertEqual(len(rows), 4)

    def test_no_public_photo_when_download_is_unavailable(self):
        bot = NS(send_file=AsyncMock(return_value=NS(id=88)))
        user = NS(download_media=AsyncMock(return_value=b"photo"))
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=RESCUE):
            with self.assertRaisesRegex(RuntimeError, "Téléchargement"):
                asyncio.run(send_public_poster_with_buttons(
                    user, bot, "@CineXFilms_vf", NS(media="photo"),
                    "Film\nSynopsis", PRIVATE, download_url=None))
        bot.send_file.assert_not_awaited()
        user.download_media.assert_not_awaited()

    def test_missing_rescue_blocks_photo(self):
        bot = NS(send_file=AsyncMock())
        user = NS(download_media=AsyncMock(return_value=b"photo"))
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Secours"):
                asyncio.run(send_public_poster_with_buttons(
                    user, bot, "@CineXFilms_vf", NS(media="photo"),
                    "Film\nSynopsis", PRIVATE, download_url=DOWNLOAD))
        bot.send_file.assert_not_awaited()

    def test_download_must_be_real_cineradar_deeplink(self):
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=RESCUE):
            with self.assertRaisesRegex(ValueError, "CinéRadar"):
                complete_public_video_rows(PRIVATE,
                    "https://t.me/c/4353068771/23", public_peer="@CineXFilms_vf")

    def test_live_verification_requires_all_four_not_only_watch_button(self):
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=RESCUE):
            complete = NS(id=41, photo=object(), raw_text="Film",
                          buttons=[[NS(text=label, url=url)] for row in
                                   complete_public_video_rows(
                                       PRIVATE, DOWNLOAD,
                                       public_peer="@CineXFilms_vf")
                                   for label, url in row])
            self.assertTrue(verify_complete_public_video_poster(
                complete, "@CineXFilms_vf", PRIVATE, DOWNLOAD))
            complete.buttons.pop(1)
            self.assertFalse(verify_complete_public_video_poster(
                complete, "@CineXFilms_vf", PRIVATE, DOWNLOAD))

    def test_public_video_requires_full_poster_and_follows_it(self):
        poster = NS(id=101, photo=object(), raw_text="Film\nSynopsis",
                    buttons=[[NS(text=label, url=url)] for row in
                             complete_public_video_rows(
                                 PRIVATE, DOWNLOAD, public_peer="@CineXFilms_vf")
                             for label, url in row])
        incoming = NS(media="video-source", document=NS(id=99, attributes=[]),
                      video=object(), file=NS(name="film.mkv"))
        sent = NS(id=102, document=NS(id=99, attributes=[]),
                  video=object(), file=NS(name="film.mkv"))
        class Client:
            def __init__(self):
                self.calls = []
            async def get_messages(self, peer, ids):
                return poster if ids == 101 else sent
            async def iter_messages(self, peer, limit=1):
                yield poster
            async def send_file(self, peer, media, **kwargs):
                self.calls.append((peer, media))
                return NS(id=102)
        client = Client()
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=RESCUE):
            result = asyncio.run(post_public_video_after_poster(
                client, "@CineXFilms_vf", incoming, "Film", 101, PRIVATE,
                download_url=DOWNLOAD))
        self.assertEqual(result.id, 102)
        self.assertEqual(client.calls, [("@CineXFilms_vf", "video-source")])
        client.calls.clear()
        poster.buttons.pop(1)
        with patch("film_relay.rescue_channels.rescue_link_for", return_value=RESCUE):
            with self.assertRaisesRegex(RuntimeError, "quatre boutons"):
                asyncio.run(post_public_video_after_poster(
                    client, "@CineXFilms_vf", incoming, "Film", 101, PRIVATE,
                    download_url=DOWNLOAD))
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
