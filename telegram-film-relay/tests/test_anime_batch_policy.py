"""Targeted checks for Anime: one complete series or two standalone movies."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from film_relay.anime_catalog import (
    all_episodes_uploaded, batch_descriptor, classify, is_anime_movie,
    pending_anime_series, ready_full_batch, recover_active_rows,
)
from film_relay.short_series import short_complete_groups


def sample_series(count, *, caption=None):
    cover = NS(id=10, photo=True, raw_text=caption or "Petite Serie",
               noforwards=False)
    return [
        {"source_key": f"-10012345:{i+100}",
         "season": 1, "episode": i, "title": "Petite Serie",
         "series": "petite-serie",
         "video": NS(
             id=i+100, raw_text=f"Episode {i}",
             document=NS(id=i+100, mime_type="video/mp4"),
             media=object(), photo=None, noforwards=False),
         "poster": cover, "timestamp": float(i)}
        for i in range(1, count+1)
    ]


class AnimeBatchPolicyTests(unittest.TestCase):
    def test_entire_25_episode_series_is_accepted(self):
        rows = sample_series(25, caption="Petite Serie complète 25 épisodes")
        eligible = short_complete_groups(
            {"petite-serie": rows}, {}, maximum=25,
            require_completion_evidence=True)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(len(eligible[0][1]), 25)
        self.assertTrue(ready_full_batch(eligible[0][1]))

    def test_26_episode_series_rejected_without_truncation(self):
        rows = sample_series(26, caption="Petite Serie complète 26 épisodes")
        self.assertEqual(short_complete_groups(
            {"petite-serie": rows}, {}, maximum=25,
            require_completion_evidence=True), [])

    def test_declared_26_episodes_but_only_25_found_is_rejected(self):
        rows = sample_series(25, caption="Petite Serie complète 26 épisodes")
        self.assertEqual(short_complete_groups(
            {"petite-serie": rows}, {}, maximum=25,
            require_completion_evidence=True), [])

    def test_25_episode_files_without_proof_of_end_are_not_uploaded(self):
        self.assertEqual(short_complete_groups(
            {"petite-serie": sample_series(25)}, {}, maximum=25,
            require_completion_evidence=True), [])

    def test_missing_middle_episode_blocks_the_entire_batch(self):
        rows = sample_series(25, caption="Petite Serie complète 25 épisodes")
        rows.pop(9)
        self.assertEqual(short_complete_groups(
            {"petite-serie": rows}, {}, maximum=25,
            require_completion_evidence=True), [])

    def test_active_batch_prevents_selection_of_any_other_series(self):
        rows = sample_series(12, caption="Petite Serie complète 12 épisodes")
        selected = pending_anime_series([("petite-serie", rows)], {"series": {}})
        self.assertEqual(selected[0], "petite-serie")
        catalogue = {"series": {}, "active_batch": {
            "key": "autre-serie", "episodes": []}}
        self.assertIsNone(pending_anime_series([("petite-serie", rows)], catalogue))
        self.assertEqual(len([selected]), 1)

    def test_publication_must_wait_until_all_private_episodes_are_saved(self):
        rows = sample_series(25, caption="Petite Serie complète 25 épisodes")
        catalogue_entry = {"episodes": {"1": {
            str(i): {"message_id": i} for i in range(1, 25)}}}
        self.assertFalse(all_episodes_uploaded(catalogue_entry, rows))
        catalogue_entry["episodes"]["1"]["25"] = {"message_id": 25}
        self.assertTrue(all_episodes_uploaded(catalogue_entry, rows))
        descriptor = batch_descriptor("petite-serie", rows)
        self.assertTrue(ready_full_batch(rows, descriptor))
        descriptor["episodes"].pop()
        self.assertFalse(ready_full_batch(rows, descriptor))

    def test_movie_classification_never_accepts_numbered_episodes(self):
        movie = NS(poster=NS(raw_text="Film Anime Voyage"), video=NS(
            raw_text="Voyage Film", file=NS(name="Voyage.mp4", duration=4200)))
        episode = NS(poster=NS(raw_text="Voyage anime saison 1"), video=NS(
            raw_text="Voyage S01E03", file=NS(name="Voyage_E03.mkv", duration=1400)))
        self.assertTrue(is_anime_movie(movie))
        self.assertFalse(is_anime_movie(episode))

    def test_text_messages_between_episodes_do_not_split_the_series(self):
        now = datetime(2026, 10, 28, tzinfo=timezone.utc)
        cover = NS(id=10, photo=True, document=None, raw_text="Mushishi Série complète 5 épisodes",
                   noforwards=False, date=now)
        messages = [cover]
        for episode in range(1, 6):
            messages.append(NS(id=10 + 2*episode, document=NS(
                id=episode, mime_type="video/mp4"), photo=None,
                raw_text=f"Episode {episode}", file=NS(name=f"Episode_{episode:02d}.mp4"),
                noforwards=False, date=now))
            if episode in (2, 4):
                messages.append(NS(id=11+2*episode, photo=None, document=None,
                                   raw_text="Nouvelles infos bientôt", noforwards=False, date=now))
        results = classify(messages, -10012345)
        self.assertEqual([row["episode"] for row in results], [1, 2, 3, 4, 5])
        self.assertEqual(len({row["series"] for row in results}), 1)


class RecoveryPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_interrupted_batch_recovers_missing_episode_by_source_id(self):
        rows = sample_series(3, caption="Petite Serie complète 3 épisodes")
        active = batch_descriptor("petite-serie", rows)
        class FakeClient:
            async def get_messages(self, peer, ids):
                if ids == 102:
                    return rows[1]["video"]
                if ids == 10:
                    return rows[1]["poster"]
                return None
        # A real Telethon peer resolves to a numeric source ID.
        peer = NS(id=12345)
        # Telethon utils.get_peer_id requires its channel type; patch just the
        # ID extraction for this isolated ID-based recovery check.
        from unittest.mock import patch
        with patch("film_relay.anime_catalog.utils.get_peer_id", return_value=-10012345):
            restored = await recover_active_rows(
                FakeClient(), [peer], [rows[0], rows[2]], active)
        self.assertEqual({row["episode"] for row in restored}, {1, 2, 3})


if __name__ == "__main__":
    unittest.main()
