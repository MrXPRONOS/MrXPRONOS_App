"""Manual bot series aliases cannot overwrite receipts or create cycles."""
from __future__ import annotations

import unittest

from film_relay.anime_bot_aliases import add_alias, resolve_alias
from scripts.anime_bot_v2 import prepare


class BotAliasesTests(unittest.TestCase):
    def test_manual_alias_preserves_existing_series_and_resolves(self):
        state = {"series": {"naruto": {"title": "Naruto",
                                     "episodes": {}, "public_episode_posts": {}}}}
        add_alias(state, "Naruto Anime VF", "naruto")
        self.assertEqual(resolve_alias(state, "Naruto Anime VF"), "naruto")
        self.assertEqual(set(state["series"]), {"naruto"})

    def test_alias_refuses_existing_episodes_and_conflicting_titles(self):
        state = {"series": {"naruto": {}, "bleach": {}}}
        with self.assertRaises(RuntimeError):
            add_alias(state, "Bleach", "Naruto")
        with self.assertRaises(ValueError):
            add_alias(state, "Unknown", "Not In Library")

    def test_publisher_selection_never_creates_new_card_for_known_alias(self):
        base = {
            "schema_version": 1,
            "series": {"naruto": {
                "title": "Naruto", "episodes": {"1": {
                    "1": {"message_id": 1001}}},
                "public_episode_posts": {"S01E01": {
                    "poster": 10, "video": 11}},
            }},
            "series_aliases": {"naruto-anime-vf": "naruto"},
            "messages": {
                "-1001234567890:2": {
                    "source_id": "-1001234567890", "message_id": 2,
                    "kind": "poster", "text": "Naruto Anime VF",
                    "filename": "", "date": 200},
                "-1001234567890:3": {
                    "source_id": "-1001234567890", "message_id": 3,
                    "kind": "video", "text": "Episode 02",
                    "filename": "Episode_02.mkv",
                    "file_id": "file", "file_unique_id": "unique",
                    "date": 300},
            },
        }
        batches, report = prepare(base)
        self.assertEqual(report["selected_episodes"], 1)
        self.assertEqual(batches[0][0], "naruto")
        self.assertEqual(batches[0][1][0]["episode"], 2)


if __name__ == "__main__":
    unittest.main()
