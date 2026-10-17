"""Offline safeguards for the independent CinéX Comedy and Anime workflows."""
import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from film_relay.category_runner import (
    CATEGORIES, category_config, check_bot_permission, run,
)
from film_relay.desir_runner import ReceiptState, DesirPromotionsState
from film_relay.desir_matching import is_supported_video, pair_items


class CategoryRelayTests(unittest.TestCase):
    def test_requires_real_source_public_and_private_ids(self):
        for category in CATEGORIES:
            with self.subTest(category=category):
                with self.assertRaises(ValueError):
                    category_config(category, {})
                prefix = CATEGORIES[category]["prefix"]
                with self.assertRaisesRegex(ValueError, "_PUBLIC_CHANNEL"):
                    category_config(category, {
                        prefix + "_SOURCE_CHANNEL": "@FilmsDemo",
                    })
                with self.assertRaisesRegex(ValueError, "_PRIVATE_CHANNEL"):
                    category_config(category, {
                        prefix + "_SOURCE_CHANNEL": "@FilmsDemo",
                        prefix + "_PUBLIC_CHANNEL": "@CineXTestfr",
                    })

    def test_two_projects_have_unique_receipts_and_default_mirror(self):
        configs = []
        for category in CATEGORIES:
            prefix = CATEGORIES[category]["prefix"]
            configs.append(category_config(category, {
                prefix + "_SOURCE_CHANNEL": "@FilmsDemo",
                prefix + "_PUBLIC_CHANNEL": "@CineX" + category + "fr",
                prefix + "_PRIVATE_CHANNEL": "-1001234567890",
            }))
        self.assertEqual(configs[0]["mirror"], "@Torrent9SeriesFilms")
        self.assertEqual(configs[1]["mirror"], "@Torrent9SeriesFilms")
        self.assertNotEqual(configs[0]["state_path"], configs[1]["state_path"])
        self.assertEqual(configs[0]["state_path"], "state/comedie_state.json")
        self.assertEqual(configs[1]["state_path"], "state/anime_state.json")

    def test_invalid_destination_cannot_be_used(self):
        for cat, config in CATEGORIES.items():
            prefix = config["prefix"]
            env = {
                prefix + "_SOURCE_CHANNEL": "@FilmsDemo",
                prefix + "_PUBLIC_CHANNEL": "@FilmsDemo",
                prefix + "_PRIVATE_CHANNEL": "-1001234567890",
            }
            with self.assertRaisesRegex(ValueError, "distincts"):
                category_config(cat, env)
            env[prefix + "_PUBLIC_CHANNEL"] = "@CineXExemple"
            env[prefix + "_MIRROR_CHANNEL"] = "@AnotherMirror"
            with self.assertRaisesRegex(ValueError, "Torrent9"):
                category_config(cat, env)

    def test_bot_requires_publish_rights(self):
        check_bot_permission(NS(is_creator=True), "@DemoChannel")
        check_bot_permission(NS(is_creator=False, is_admin=True, post_messages=True),
                             "@DemoChannel")
        with self.assertRaisesRegex(RuntimeError, "administrateur"):
            check_bot_permission(NS(is_creator=False, is_admin=True, post_messages=False),
                                 "@DemoChannel")

    def test_category_state_and_promos_are_isolated(self):
        from film_relay.promotions import due
        with TemporaryDirectory() as folder:
            states = [ReceiptState(str(Path(folder) / (cat + ".json")))
                      for cat in ("comedie", "anime")]
            states[0].complete("comedie_source:10", 11, 12)
            states[0].complete("comedie_source:11", 13, 14)
            self.assertEqual(len(states[0].data["completed"]), 2)
            self.assertEqual(len(states[1].data["completed"]), 0)
            self.assertEqual(
                due(DesirPromotionsState(states[0]), "-100public", 2), 0
            )
            self.assertIsNone(
                due(DesirPromotionsState(states[1]), "-100public", 0)
            )

    def test_image_without_caption_and_mkv_without_duration(self):
        video = NS(id=32, photo=None, document=NS(id=57, mime_type="application/octet-stream"),
                   file=NS(name="Episode_01.mkv", duration=None), noforwards=False, raw_text="")
        poster = NS(id=31, photo=object(), document=None, noforwards=False, raw_text="")
        self.assertTrue(is_supported_video(video))
        pairs = pair_items([video, poster])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].poster.id, 31)

    def test_no_new_media_copied_during_invalid_config(self):
        with patch.dict("os.environ", {"COMEDIE_SOURCE_CHANNEL": "",
                                       "COMEDIE_PUBLIC_CHANNEL": "",
                                       "COMEDIE_PRIVATE_CHANNEL": ""}, clear=True):
            with self.assertRaises(ValueError):
                asyncio.run(run(category="comedie", publish=True))

    def test_manual_workflows_no_schedule_and_share_bot(self):
        root = Path(__file__).resolve().parents[2]
        main = (root / ".github/workflows/telegram-film-relay.yml").read_text()
        for cat in ("comedie", "anime"):
            data = (root / f".github/workflows/cinex-{cat}-test.yml").read_text()
            self.assertIn("workflow_dispatch:", data)
            self.assertNotIn("  schedule:", data)
            self.assertIn("mrx-telegram-personal-account", data)
            self.assertIn("DESIR_BOT_TOKEN || secrets.FOOTBALL_NEWS_BOT_TOKEN", data)
            self.assertIn(f"--category {cat}", data)
            self.assertIn("default: false", data)
            self.assertIn("merge_desir_state.py", data)
            self.assertIn("@Torrent9SeriesFilms", data)
            self.assertIn(f"{cat}_state.json", data)
        self.assertNotIn("category_runner", main)


if __name__ == "__main__":
    unittest.main()
