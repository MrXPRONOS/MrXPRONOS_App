"""Historical receipts must be imported without reposting old episodes."""
from __future__ import annotations

import unittest

from film_relay.anime_bot_migration import migrate_legacy_catalogue
from film_relay.anime_bot_matching import select_bot_anime_batches


def previous_catalogue():
    return {"series": {"naruto": {
        "title": "Naruto", "public_id": 77,
        "main_index_id": 55, "season_indices": {"1": 33},
        "episodes": {"1": {
            "1": {"message_id": 101},
            "2": {"message_id": 102},
        }},
        "public_episode_posts": {
            "S01E01": {"poster": 90, "video": 91, "private_video": 101}
        },
    }}}


class LegacyBotMigrationTests(unittest.TestCase):
    def test_import_keeps_public_card_without_reupload(self):
        new, report = migrate_legacy_catalogue(
            {"schema_version": 1, "series": {}},
            previous_catalogue())
        self.assertEqual(report["imported_series"], 1)
        self.assertEqual(report["imported_private_episodes"], 2)
        self.assertEqual(report["imported_public_pairs"], 1)
        self.assertEqual(report["legacy_unverified_episodes"], 1)
        entry = new["series"]["naruto"]
        self.assertEqual(entry["public_id"], 77)
        self.assertEqual(entry["legacy_main_index_id"], 55)
        self.assertEqual(entry["legacy_season_index_ids"]["1"], 33)
        self.assertNotIn("main_index_id", entry)
        self.assertEqual(entry["legacy_unverified_episode_keys"], ["S01E02"])

    def test_unverified_legacy_episode_never_republished(self):
        migrated, _ = migrate_legacy_catalogue(
            {"schema_version": 1, "series": {}},
            previous_catalogue())
        rows = [
            {"series": "naruto", "season": 1, "episode": n,
             "source_key": f"src:{n}", "date": n}
            for n in (1, 2, 3)
        ]
        picked = select_bot_anime_batches(rows, migrated, {})
        self.assertEqual([(x["episode"]) for _, group, _ in picked
                          for x in group], [3])

    def test_existing_v2_receipts_cannot_be_overwritten(self):
        original = {"schema_version": 1,
                    "series": {"naruto": {"episodes": {
                        "1": {"1": {"message_id": 999}}
                    }}}}
        updated, report = migrate_legacy_catalogue(
            original, previous_catalogue())
        self.assertEqual(updated, original)
        self.assertEqual(report["collisions"], ["naruto"])

    def test_unfinished_legacy_batch_is_blocked(self):
        old = previous_catalogue()
        old["active_batch"] = {"key": "naruto", "episodes": [{"source_key": "a"}]}
        with self.assertRaisesRegex(RuntimeError, "unfinished"):
            migrate_legacy_catalogue({"schema_version": 1, "series": {}}, old)


if __name__ == "__main__":
    unittest.main()
