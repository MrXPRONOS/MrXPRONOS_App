"""Complete offline safety tests of MTProto-free Anime Bot API pipeline."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from film_relay.anime_bot_matching import (
    associate_anime_messages, consolidate_source_candidates,
    select_bot_anime_batches,
)
from film_relay.anime_bot_publisher import AnimeBotPublisher
from film_relay.anime_bot_state import BotStateStore, require_durable_store
from film_relay.anime_bot_transport import verify_anime_bot_guard
from scripts.anime_bot_v2 import prepare


SOURCE = "-1001234567890"
PRIVATE = "-1002222222222"
PUBLIC = "-1003333333333"


def record(message_id, kind, *, text="", name="", file_unique_id=None,
           source_id=SOURCE, status="pending"):
    return {
        "source_id": source_id, "message_id": message_id,
        "kind": kind, "text": text, "filename": name,
        "file_id": "FILE" if kind != "text" else "",
        "file_unique_id": file_unique_id or str(message_id),
        "date": message_id * 100,
        "status": status,
    }


def messages(*items):
    return {f"{row['source_id']}:{row['message_id']}": row for row in items}


class AnimeBotMatchingTests(unittest.TestCase):
    def test_source_poster_gif_text_and_bare_episodes(self):
        data = messages(
            record(1, "poster", text="Naruto S02 complète 3 épisodes"),
            record(2, "animation", text="Hebdomadaire", name="weekly.gif"),
            record(3, "text", text="Nouvelles infos bientôt"),
            record(4, "video", text="Episode 01", name="Episode_01.mp4"),
            record(5, "video", text="Episode 02", name="Episode_02.mp4"),
            record(6, "video", text="Episode 03", name="Episode_03.mp4"),
        )
        found, review, cadence, full = associate_anime_messages(data)
        self.assertFalse(review)
        self.assertEqual([(row["season"], row["episode"])
                          for row in found], [(2, 1), (2, 2), (2, 3)])
        self.assertEqual({row["series"] for row in found}, {"naruto"})
        self.assertEqual({row["title"] for row in found}, {"Naruto"})
        self.assertEqual(cadence["naruto"], "weekly")
        self.assertEqual(full[("naruto", 2)], 3)
        selected, diag = consolidate_source_candidates(found)
        self.assertFalse(diag)
        picked = select_bot_anime_batches(selected, {}, full)
        self.assertEqual([(x["episode"]) for x in picked[0][1]], [1, 2, 3])
        self.assertTrue(picked[0][2])

    def test_new_title_without_new_artwork_is_quarantined(self):
        entries = messages(
            record(1, "poster", text="Naruto"),
            record(2, "text", text="Titre: Bleach"),
            record(3, "video", name="Episode_01.mkv"),
        )
        found, review, _, _ = associate_anime_messages(entries)
        self.assertEqual(found, [])
        self.assertIn("ambiguous_series_or_poster", {r["reason"] for r in review})

    def test_special_release_not_misclassified(self):
        entries = messages(
            record(1, "poster", text="Naruto"),
            record(2, "video", name="Naruto_OVA_E01.mp4"),
        )
        found, review, _, _ = associate_anime_messages(entries)
        self.assertFalse(found)
        self.assertEqual(review[0]["reason"], "special_release")

    def test_conflicting_media_across_two_authorized_sources_requires_review(self):
        rows = [
            {"series": "naruto", "season": 1, "episode": 7,
             "source_key": "a:2", "file_unique_id": "a", "date": 1},
            {"series": "naruto", "season": 1, "episode": 7,
             "source_key": "b:2", "file_unique_id": "b", "date": 2},
        ]
        unique, quarantined = consolidate_source_candidates(rows)
        self.assertFalse(unique)
        self.assertEqual(quarantined[0]["reason"], "conflicting_source_media")
        unique, quarantined = consolidate_source_candidates(
            rows, reviewed_variants={"naruto:S01E07": "a"})
        self.assertEqual(unique[0]["source_key"], "a:2")
        self.assertFalse(quarantined)

    def test_one_bot_video_mislabeled_as_multiple_episodes_is_quarantined(self):
        rows = [
            {"series": "naruto", "season": 1, "episode": 1,
             "source_key": "a:1", "file_unique_id": "exact-video"},
            {"series": "naruto", "season": 1, "episode": 2,
             "source_key": "a:2", "file_unique_id": "exact-video"},
        ]
        selected, review = consolidate_source_candidates(rows)
        self.assertFalse(selected)
        self.assertEqual(len(review), 2)
        self.assertEqual({x["reason"] for x in review},
                         {"one_video_labeled_as_distinct_episodes"})

    def test_only_four_different_ongoing_anime(self):
        source = []
        for index in range(6):
            source += [
                record(100 * index + 1, "poster", text=f"Animetest {index}"),
                record(100 * index + 2, "video", name="Episode_01.mp4"),
                record(100 * index + 3, "video", name="Episode_02.mp4"),
            ]
        state = {"messages": messages(*source)}
        picked, report = prepare(state)
        self.assertEqual(len(picked), 4)
        self.assertEqual(report["selected_episodes"], 4)
        self.assertEqual(len({key for key, _, _ in picked}), 4)
        self.assertTrue(all(len(rows) == 1 and not full
                            for _, rows, full in picked))

    def test_published_episode_prevents_reposting(self):
        state = {"series": {"naruto": {
            "episodes": {"1": {"1": {"message_id": 30}}},
            "public_episode_posts": {"S01E01": {"poster": 80, "video": 81}},
        }}}
        rows = [{"series": "naruto", "season": 1, "episode": 1,
                 "date": 2, "source_key": "a:2"}]
        self.assertEqual(select_bot_anime_batches(rows, state, {}), [])

    def test_complete_30_episode_season_resumes_after_first_25(self):
        rows = [{"series": "naruto", "season": 1, "episode": n,
                 "source_key": f"source:{n}", "date": n}
                for n in range(1, 31)]
        full = {("naruto", 1): 30}
        initial = select_bot_anime_batches(rows, {}, full)
        self.assertEqual(len(initial), 1)
        self.assertEqual(len(initial[0][1]), 25)
        self.assertTrue(initial[0][2])
        saved = {"series": {"naruto": {
            "episodes": {"1": {
                str(n): {"message_id": 1000+n} for n in range(1, 26)
            }},
            "public_episode_posts": {
                f"S01E{n:02d}": {"poster": 200+n, "video": 300+n}
                for n in range(1, 26)
            },
        }}}
        continuation = select_bot_anime_batches(rows, saved, full)
        self.assertEqual([r["episode"] for r in continuation[0][1]],
                         [26, 27, 28, 29, 30])
        self.assertTrue(continuation[0][2])

    def test_missing_episode_1_blocks_episode_2(self):
        state = {}
        rows = [{"series": "naruto", "season": 1, "episode": 2,
                 "date": 2, "source_key": "a:2"}]
        self.assertEqual(select_bot_anime_batches(rows, state, {}), [])


class AnimeBotStorageTests(unittest.TestCase):
    def test_atomic_private_roundtrip_and_locked_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hidden" / "state.json"
            store = BotStateStore(path)
            state = store.load()
            state["messages"]["private"] = {"file_id": "SECRET_FILE_ID"}
            store.save(state)
            self.assertEqual(store.load(), state)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with store.exclusive():
                with self.assertRaises(BlockingIOError):
                    with store.exclusive():
                        pass

    def test_production_requires_attested_storage_and_rights(self):
        with self.assertRaises(RuntimeError):
            require_durable_store("/tmp/episode-state.json", {
                "CINEX_ANIME_PRIVATE_PERSISTENCE_ATTESTED": "true"})
        with self.assertRaises(RuntimeError):
            verify_anime_bot_guard({})
        token = verify_anime_bot_guard({
            "CINEX_ANIME_BOT_ENABLE": "true",
            "ANIME_RIGHTS_ATTESTED": "true",
            "CINEX_ANIME_SOURCE_BOT_TOKEN": "123:token",
        })
        self.assertEqual(token, "123:token")


class AnimeBotPublisherTests(unittest.TestCase):
    def _setup(self):
        source_video = record(2, "video", name="Episode_01.mp4")
        source_poster = record(1, "poster", text="Naruto")
        state = BotStateStore(self.tmp / "store.json").load()
        state["messages"] = messages(source_poster, source_video)
        row = {"series": "naruto", "title": "Naruto", "season": 1,
               "episode": 1, "source_key": f"{SOURCE}:2",
               "source_id": SOURCE, "poster_source_key": f"{SOURCE}:1",
               "cadence_hint": "weekly"}
        bot = type("Bot", (), {})()
        bot.copy_message = AsyncMock(side_effect=[
            21, 31, 32, 33,
        ])
        bot.send_message = AsyncMock(side_effect=[41, 42])
        bot.edit_message = AsyncMock()
        bot.edit_buttons = AsyncMock()
        store = BotStateStore(self.tmp / "store.json")
        store.save(state)
        publisher = AnimeBotPublisher(bot, store, state, private_id=PRIVATE,
                                      public_id=PUBLIC, pause=0)
        return bot, store, state, row, publisher

    def setUp(self):
        self.ctx = tempfile.TemporaryDirectory()
        self.tmp = Path(self.ctx.name)

    def tearDown(self):
        self.ctx.cleanup()

    def test_one_series_one_episode_idempotent_no_new_media(self):
        bot, store, state, row, publisher = self._setup()
        async def exercise():
            first = await publisher.publish_episode(row)
            second = await publisher.publish_episode(row)
            return first, second
        first, second = asyncio.run(exercise())
        self.assertEqual(first, second)
        self.assertEqual(len(state["series"]), 1)
        self.assertIn("S01E01", state["series"]["naruto"]["public_episode_posts"])
        self.assertEqual(bot.copy_message.await_count, 4)
        self.assertEqual(bot.send_message.await_count, 2)
        self.assertEqual(store.load(), state)

    def test_episode_26_is_reachable_from_first_season_index(self):
        bot, store, state, row, publisher = self._setup()
        series = publisher._series(row)
        series["episodes"] = {"1": {
            str(n): {"message_id": 1000 + n}
            for n in range(1, 27)
        }}
        bot.send_message = AsyncMock(side_effect=[151, 152])
        asyncio.run(publisher._season_index(row, series))
        self.assertEqual(series["index_pages"]["1"], {"1": 151, "2": 152})
        self.assertEqual(bot.send_message.await_count, 2)
        first_edit = bot.edit_message.await_args_list[0].args[2]
        last_edit = bot.edit_message.await_args_list[1].args[2]
        self.assertIn("/152", first_edit)
        self.assertIn("/151", last_edit)
        self.assertIn("Épisode 26", last_edit)

    def test_uncertain_send_never_retries_after_restart(self):
        bot, store, state, row, publisher = self._setup()
        bot.copy_message = AsyncMock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError):
            asyncio.run(publisher.publish_episode(row))
        self.assertEqual(bot.copy_message.await_count, 1)
        restarted = AnimeBotPublisher(bot, store, store.load(),
                                      private_id=PRIVATE, public_id=PUBLIC,
                                      pause=0)
        with self.assertRaisesRegex(RuntimeError, "incertain"):
            asyncio.run(restarted.publish_episode(row))
        self.assertEqual(bot.copy_message.await_count, 1)


if __name__ == "__main__":
    unittest.main()
