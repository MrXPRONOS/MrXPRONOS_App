"""Offline recovery regression: source-repost changes and interrupted posts."""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from film_relay.publication import (
    catalog_public_marker, publish_catalog_episode_pairs,
)


def video(doc):
    return NS(video=object(), document=NS(id=doc, attributes=[]))


class ReceiptsTests(unittest.TestCase):
    def test_public_marker_is_source_independent_and_episode_specific(self):
        self.assertEqual(catalog_public_marker("Naruto", 1, 7),
                         catalog_public_marker("NARUTO", 1, 7))
        self.assertNotEqual(catalog_public_marker("Naruto", 1, 7),
                            catalog_public_marker("Naruto", 1, 8))
        self.assertNotEqual(catalog_public_marker("Naruto", 1, 7),
                            catalog_public_marker("Bleach", 1, 7))

    def test_existing_valid_public_pair_does_not_resend_new_source_encoding(self):
        source_repost = video(999)
        entry = {
            "title": "Naruto", "episodes": {"1": {"7": {"message_id": 27}}},
            "public_episode_posts": {"S01E07": {
                "poster": 70, "video": 71, "private_video": 27
            }},
        }
        async def get_messages(peer, ids):
            if peer == "@private":
                return video(111)
            return NS(photo=object()) if ids == 70 else video(111)
        client = NS(get_messages=get_messages)
        row = {"season": 1, "episode": 7, "source_key": "other:707",
               "poster": NS(photo=object(), media="photo", raw_text="Naruto"),
               "video": source_repost, "title": "Naruto"}
        with patch("film_relay.publication.send_public_poster_with_buttons",
                   new=AsyncMock()) as send_poster, patch(
             "film_relay.publication.post_public_video_after_poster",
                   new=AsyncMock()) as send_video:
            asyncio.run(publish_catalog_episode_pairs(
                client, NS(), "@public", "@private", -1001234567890,
                entry, [row], {"series": {"naruto": entry}},
                lambda _: None, 0))
        send_poster.assert_not_awaited()
        send_video.assert_not_awaited()

    def test_photo_sent_before_crash_is_not_sent_again(self):
        marker = catalog_public_marker("Naruto", 1, 7)
        entry = {"title": "Naruto",
                 "episodes": {"1": {"7": {"message_id": 27}}},
                 "pending_public_episode_posts": {
                     "S01E07": {"poster": 70},
                 }}
        async def get_messages(peer, ids):
            if peer == "@private":
                return video(111)
            if ids == 70:
                return NS(id=70, photo=object(), raw_text="Naruto "+marker)
            return video(111)
        client = NS(get_messages=get_messages)
        row = {"season": 1, "episode": 7,
               "poster": NS(photo=object(), media="cover", raw_text="Naruto"),
               "video": video(999), "title": "Naruto"}
        saves = []
        with patch("film_relay.publication.send_public_poster_with_buttons",
                   new=AsyncMock()) as send_poster, patch(
             "film_relay.publication.post_public_video_after_poster",
                   new=AsyncMock(return_value=NS(id=71))) as send_video, patch(
             "asyncio.sleep", new=AsyncMock()):
            asyncio.run(publish_catalog_episode_pairs(
                client, NS(), "@public", "@private", -1001234567890,
                entry, [row], {"series": {"naruto": entry}},
                lambda _: saves.append(True), 0))
        send_poster.assert_not_awaited()
        self.assertEqual(send_video.await_count, 1)
        self.assertEqual(send_video.await_args.args[2].document.id, 111)
        self.assertEqual(entry["public_episode_posts"]["S01E07"]["video"], 71)
        self.assertNotIn("S01E07", entry["pending_public_episode_posts"])
        self.assertGreaterEqual(len(saves), 2)

    def test_uncertain_video_send_never_retries_blindly(self):
        marker = catalog_public_marker("Naruto", 1, 7)
        entry = {"title": "Naruto",
                 "episodes": {"1": {"7": {"message_id": 27}}},
                 "pending_public_episode_posts": {
                     "S01E07": {"poster": 70, "video_send_uncertain": True},
                 }}
        async def get_messages(peer, ids):
            if peer == "@private":
                return video(111)
            return NS(id=70, photo=object(), raw_text=marker)
        client = NS(get_messages=get_messages)
        row = {"season": 1, "episode": 7,
               "poster": NS(photo=object(), media="cover", raw_text="Naruto"),
               "video": video(111), "title": "Naruto"}
        with patch("film_relay.publication.post_public_video_after_poster",
                   new=AsyncMock()) as send_video:
            with self.assertRaisesRegex(RuntimeError, "incertain"):
                asyncio.run(publish_catalog_episode_pairs(
                    client, NS(), "@public", "@private", -1001234567890,
                    entry, [row], {"series": {"naruto": entry}},
                    lambda _: None, 0))
        send_video.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
