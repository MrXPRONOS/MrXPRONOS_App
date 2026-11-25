"""Regression tests for real MTProto filenames and cover-first private storage."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock

from film_relay.private_media_contract import (
    bot_copy_source_filename_valid, filename_for, marker_for,
    renamed_receipt_matches, send_named_private_video,
)


def video(mid=19, *, name="VID_20251125.mkv", size=4, caption=""):
    return NS(
        id=mid, raw_text=caption,
        file=NS(name=name), noforwards=False, media=NS(),
        document=NS(id=mid+1000, size=size, mime_type="video/x-matroska",
                    attributes=[]),
        video=NS(),
    )


def photo(mid=10):
    return NS(id=mid, raw_text="🎬 Mon Super Voyage\n"
                     "Genre : aventure et découverte dans un pays imaginaire.",
              photo=NS(id=80), media=NS())


class NamingTests(unittest.TestCase):
    def test_real_filename_from_title_and_original_extension(self):
        self.assertEqual(filename_for(video(), title="Mon Super Voyage"),
                         "Mon Super Voyage.mkv")
        self.assertEqual(filename_for(
            video(name="unnamed.mp4"), title="Dragon Ball S01E03"),
            "Dragon Ball S01E03.mp4")

    def test_two_movie_parts_keep_distinct_real_filenames(self):
        one = video(name="Le Grand Voyage.Partie.1.mkv",
                    caption="Le Grand Voyage Partie 1")
        two = video(name="Le Grand Voyage.Partie.2.mkv",
                    caption="Le Grand Voyage Partie 2")
        self.assertEqual(filename_for(one, title="Le Grand Voyage"),
                         "Le Grand Voyage Partie 1.mkv")
        self.assertEqual(filename_for(two, title="Le Grand Voyage"),
                         "Le Grand Voyage Partie 2.mkv")

    def test_video_part_number_not_added_twice(self):
        one = video(name="Le Voyage.Part.3.mp4", caption="Le Voyage Partie 3")
        self.assertEqual(filename_for(one, title="Le Voyage Partie 3"),
                         "Le Voyage Partie 3.mp4")

    def test_disagreeing_numbers_block_storage(self):
        bad = video(name="Le Voyage.Partie.2.mkv",
                    caption="Le Voyage Partie 1")
        with self.assertRaisesRegex(RuntimeError, "Contradiction"):
            filename_for(bad, title="Le Voyage")
        bad.raw_text = "Le Voyage Partie 2"
        with self.assertRaisesRegex(RuntimeError, "affiche différent"):
            filename_for(bad, title="Le Voyage Partie 1")

    def test_episode_code_in_source_survives_generic_cover(self):
        src = video(name="Naruto.S02E07.mkv", caption="Naruto")
        self.assertEqual(filename_for(src, title="Naruto"),
                         "Naruto S02E07.mkv")

    def test_unnamed_fails_without_descriptive_title(self):
        with self.assertRaisesRegex(RuntimeError, "Nom descriptif"):
            filename_for(video(name="video.mkv", caption="Film"),
                         title="Titre non identifié")

    def test_receipt_must_match_filename_and_bytes(self):
        source = video()
        renamed = video(mid=42, name="Mon Super Voyage.mkv", size=4,
                        caption="🎞 Mon Super Voyage\n" + marker_for(source))
        self.assertTrue(renamed_receipt_matches(
            source, renamed, title="Mon Super Voyage"))
        renamed.file.name = "video.mkv"
        self.assertFalse(renamed_receipt_matches(
            source, renamed, title="Mon Super Voyage"))
        renamed.file.name = "Mon Super Voyage.mkv"
        renamed.document.size = 7
        self.assertFalse(renamed_receipt_matches(
            source, renamed, title="Mon Super Voyage"))

    def test_interrupted_named_send_is_recovered_by_source_marker(self):
        from film_relay.recovery import (
            TelegramReceiptCache, recover_from_snapshot,
        )
        source = video()
        cache = TelegramReceiptCache(
            by_document={}, public_by_video={},
            by_source_marker={marker_for(source): [81]})
        state = NS(stage=unittest.mock.Mock())
        result = recover_from_snapshot(
            cache, state, "source:10:11", "1100", source)
        self.assertEqual(result, "staged")
        state.stage.assert_called_once_with("source:10:11", 81)

    def test_bot_copy_must_have_correct_existing_filename(self):
        self.assertTrue(bot_copy_source_filename_valid(
            "Naruto.S01E03.mkv", "Naruto", "S01E03"))
        self.assertFalse(bot_copy_source_filename_valid(
            "video_0003.mkv", "Naruto", "S01E03"))
        self.assertFalse(bot_copy_source_filename_valid(
            "Naruto.S01E04.mkv", "Naruto", "S01E03"))
        self.assertFalse(bot_copy_source_filename_valid(
            "", "Naruto", "S01E03"))


class PrivateSendTests(unittest.IsolatedAsyncioTestCase):
    async def test_already_named_server_copy_requires_prior_cover(self):
        source = video(name="Mon Super Voyage.mkv")
        cover = photo()
        stored = video(mid=11, name="Mon Super Voyage.mkv")
        stored.document.id = source.document.id
        stored.raw_text = "🎞️ Mon Super Voyage"
        client = NS(
            get_messages=AsyncMock(side_effect=[cover, stored]),
            send_file=AsyncMock(return_value=NS(id=11)),
            download_media=AsyncMock(),
        )
        got = await send_named_private_video(
            client, "private", source,
            title="Mon Super Voyage", caption="🎞️ Mon Super Voyage",
            private_cover_id=10, poster=cover)
        self.assertEqual(got.id, 11)
        self.assertEqual(client.send_file.await_args.args[1], source.media)
        client.download_media.assert_not_awaited()

    async def test_missing_cover_never_uploads(self):
        client = NS(
            get_messages=AsyncMock(return_value=None),
            send_file=AsyncMock(),
            download_media=AsyncMock(),
        )
        with self.assertRaisesRegex(RuntimeError, "Affiche privée"):
            await send_named_private_video(
                client, "private", video(),
                title="Mon Super Voyage", caption="🎞 Mon Super Voyage",
                private_cover_id=10)
        client.send_file.assert_not_awaited()

    async def test_rename_requires_download_and_reupload_bytes(self):
        source = video()
        cover = photo()
        named = video(mid=12, name="Mon Super Voyage.mkv")
        named.raw_text = "🎞 Mon Super Voyage\n" + marker_for(source)
        client = NS(
            get_messages=AsyncMock(side_effect=[cover, named]),
            send_file=AsyncMock(return_value=NS(id=12)),
        )
        async def download(_source, *, file):
            Path(file).write_bytes(b"1234")
            return file
        client.download_media = AsyncMock(side_effect=download)
        got = await send_named_private_video(
            client, "private", source,
            title="Mon Super Voyage", caption="🎞 Mon Super Voyage",
            private_cover_id=10, poster=cover)
        self.assertEqual(got.id, 12)
        self.assertEqual(client.send_file.await_args.kwargs["force_document"], True)
        self.assertTrue(client.send_file.await_args.args[1].endswith("Mon Super Voyage.mkv"))
        client.download_media.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
