"""Offline contracts for explicitly authorized CineX cross-channel sources."""
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from film_relay.authorized_cross_sources import (
    linked_posts, cross_channel_movie_pairs, authorized_peers,
)
from film_relay.category_runner import CATEGORIES, category_config


class CrossSourceTests(unittest.TestCase):
    def test_action_never_has_implicit_source(self):
        self.assertIn("action", CATEGORIES)
        with self.assertRaisesRegex(ValueError, "ACTION_SOURCE_CHANNEL"):
            category_config("action", {
                "ACTION_PUBLIC_CHANNEL": "@filmsaction2026vf",
                "ACTION_PRIVATE_CHANNEL": "-1003545242931",
            })
        cfg = category_config("action", {
            "ACTION_PUBLIC_CHANNEL": "@filmsaction2026vf",
            "ACTION_PRIVATE_CHANNEL": "-1003545242931",
            "ACTION_SOURCE_CHANNEL": "@SourceLicensedOne",
        })
        self.assertEqual(cfg["sources"], ["@SourceLicensedOne"])

    def test_links_only_from_separately_authorized_media_channels(self):
        poster = NS(buttons=[[NS(url="https://t.me/OnlyAllowed123/128"),
                              NS(url="https://t.me/NotApproved123/129"),
                              NS(url="https://t.me/+HiddenInviteLink")],
                             [NS(url="https://t.me/c/12345678/43")]])
        links = linked_posts(poster, ["@OnlyAllowed123"])
        self.assertEqual(links, [("@OnlyAllowed123", 128)])

    def test_cross_channel_film_requires_unique_matching_video(self):
        poster = NS(id=10, photo=object(), noforwards=False,
                    raw_text="Le Dernier Voyage\nGenre: Action")
        movie = NS(id=55, photo=None, noforwards=False,
                   document=NS(id=900, mime_type="video/mp4"),
                   raw_text="Le Dernier Voyage", file=NS(name="Le Dernier Voyage.mp4"),
                   reply_to=None, grouped_id=None)
        unknown = NS(id=56, photo=None, noforwards=False,
                     document=NS(id=901, mime_type="video/mp4"),
                     raw_text="Le Voyage d'Ailleurs", file=NS(name="Voyage ailleurs.mp4"),
                     reply_to=None, grouped_id=None)
        matched = cross_channel_movie_pairs([poster], [(movie, "Médias autorisés"),
                                                       (unknown, "Médias autorisés")])
        self.assertEqual(len(matched), 1)
        self.assertIs(matched[0].video, movie)
        self.assertEqual(
            cross_channel_movie_pairs([poster], [(movie, "Médias"),
                                                 (movie, "Médias")]), [])

    def test_missing_or_protected_media_is_not_allowed(self):
        async def main():
            from telethon import utils
            # Resolved username must match the actual public identity.
            client = NS(get_entity=AsyncMock(return_value=NS(
                username="DifferentSource", broadcast=True,
                noforwards=False, id=98765)))
            with self.assertRaises(RuntimeError):
                await authorized_peers(client, ["@AllowedOther"])
        asyncio.run(main())


if __name__ == "__main__":
    unittest.main()
