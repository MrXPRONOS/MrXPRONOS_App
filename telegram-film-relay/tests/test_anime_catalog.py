"""Offline tests: recognize seasons correctly and avoid duplicate anime cards."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as N

from film_relay.anime_catalog import (
    classify, episode_numbers, series_title, slug, season_text,
    main_index_text, public_buttons,
)
from film_relay.category_runner import category_config
from scripts.merge_anime_catalog import merge


def video(number, filename, caption=""):
    return N(id=number, photo=None, noforwards=False, document=N(
        mime_type="video/mp4", id=number + 1000), file=N(name=filename),
        date=datetime(2026, 10, 17, tzinfo=timezone.utc), raw_text=caption)


def poster(number, caption):
    return N(id=number, photo=object(), noforwards=False, raw_text=caption)


class AnimeCatalogTests(unittest.TestCase):
    def test_season_episode_formats(self):
        for value, wanted in (
            ("Naruto S01E03.mkv", (1, 3)),
            ("One Piece saison 2 épisode 12", (2, 12)),
            ("Bleach 3x04", (3, 4)),
            ("Épisode 7", (1, 7)),
            ("EP 09", (1, 9)),
        ):
            with self.subTest(value=value):
                self.assertEqual(episode_numbers(value), wanted)
        self.assertIsNone(episode_numbers("Naruto.mkv"))
        self.assertIsNone(episode_numbers("Saison 2 seulement"))

    def test_title_does_not_use_episode_as_anime_name(self):
        self.assertFalse(series_title("S01E03"))
        self.assertEqual(slug(series_title("One.Piece.S01E03")), "one-piece")

    def test_single_poster_followed_by_many_episodes(self):
        rows = [poster(10, "Naruto"), video(11, "S01E01.mkv"),
                video(12, "S01E02.mkv"), video(13, "S01E03.mkv")]
        found = classify(rows, -100123456)
        self.assertEqual(len(found), 3)
        self.assertEqual({r["series"] for r in found}, {"naruto"})
        self.assertEqual({r["episode"] for r in found}, {1, 2, 3})

    def test_unnumbered_file_is_skipped(self):
        found = classify([poster(10, "Bleach"), video(11, "video.mp4")], -100123)
        self.assertEqual(found, [])

    def test_season_banner_changes_episode_group(self):
        records = [
            poster(10, "Naruto"),
            video(11, "Episode_01.mkv"),
            N(id=12, photo=None, document=None, noforwards=False,
              raw_text="Saison 2", date=datetime(2026, 10, 17, tzinfo=timezone.utc)),
            video(13, "Episode_01.mkv"),
        ]
        result = classify(records, -100777)
        self.assertEqual([(r["season"], r["episode"]) for r in result],
                         [(1, 1), (2, 1)])

    def test_new_series_poster_overrides_previous(self):
        items = [poster(10, "Naruto"), video(11, "S01E01.mp4"),
                 poster(12, "Bleach"), video(13, "S01E02.mp4")]
        found = classify(items, -100)
        self.assertEqual([e["series"] for e in found], ["naruto", "bleach"])

    def test_visible_episode_links(self):
        result = season_text("Naruto", 1, {
            "1": {"url": "https://t.me/c/1234/100"},
            "12": {"url": "https://t.me/c/1234/102"},
        })
        self.assertIn("Saison 1", result)
        self.assertIn("Épisode 12", result)
        self.assertIn("https://t.me/c/1234/100", result)

    def test_public_card_links_to_saison_and_main_index(self):
        serial = {"main_index_id": 55, "season_indices": {"1": 33, "2": 40}}
        buttons = public_buttons(-1001234567, serial)
        self.assertEqual(len(buttons), 4)
        self.assertEqual(buttons[0][0].url, "https://t.me/c/1234567/33")
        self.assertIn("55", buttons[2][0].url)
        self.assertIn("https://t.me/", buttons[3][0].url)

    def test_existing_sources_remain_unchanged(self):
        cfg = category_config("anime", {
            "ANIME_SOURCE_CHANNELS": "@orak_dessinanime,@AnotherAnimeSource",
            "ANIME_PUBLIC_CHANNEL": "@CineXAnimeFR",
            "ANIME_PRIVATE_CHANNEL": "-100123456789",
        })
        self.assertEqual(cfg["sources"], ["@orak_dessinanime", "@AnotherAnimeSource"])

    def test_state_merges_episode_receipts_without_overwrite(self):
        remote = {"series": {"naruto": {
            "title": "Naruto", "episodes": {"1": {"1": {"url": "https://t.me/c/1/10"}}},
            "source_items": {"a": 10}, "season_indices": {"1": 9}}}}
        local = {"series": {"naruto": {
            "episodes": {"1": {"2": {"url": "https://t.me/c/1/11"}}},
            "source_items": {"b": 11}, "season_indices": {"2": 12}}}}
        merged = merge(remote, local)["series"]["naruto"]
        self.assertEqual(len(merged["episodes"]["1"]), 2)
        self.assertEqual(len(merged["source_items"]), 2)
        self.assertEqual(len(merged["season_indices"]), 2)


if __name__ == "__main__":
    unittest.main()
