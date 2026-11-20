"""No-Telegram regression tests for historical Anime title repair."""
import unittest

from film_relay.anime_identity import (
    consolidate_catalog, identity, resolve_series_key,
)


def history():
    return {
        "series": {
            "mangas-fv-death-parade-ep05": {
                "title": "@Mangas fv Death Parade EP05",
                "public_id": 44, "main_index_id": 106,
                "season_indices": {"1": 107},
                "episodes": {"1": {"5": {
                    "message_id": 108, "url": "https://t.me/c/4416009337/108"}}},
                "source_items": {"-100123:13791": 108},
            },
            "mangas-fv-death-parade-ep06": {
                "title": "@Mangas fv Death Parade EP06",
                "public_id": 45, "main_index_id": 109,
                "season_indices": {"1": 110},
                "episodes": {"1": {"6": {
                    "message_id": 111, "url": "https://t.me/c/4416009337/111"}}},
                "source_items": {"-100123:13792": 111},
            },
        }
    }


class IdentityMigrationTests(unittest.TestCase):
    def test_legacy_episode_names_share_safe_identity(self):
        rows = history()["series"]
        self.assertEqual(
            identity("mangas-fv-death-parade-ep05", rows["mangas-fv-death-parade-ep05"]),
            "death-parade")

    def test_merge_preserves_every_private_receipt_and_public_card(self):
        original = history()
        merged, report = consolidate_catalog(original)
        self.assertEqual(report["consolidated_entries"], 1)
        self.assertEqual(len(merged["series"]), 1)
        self.assertEqual(len(original["series"]), 2)
        kept = merged["series"]["mangas-fv-death-parade-ep05"]
        self.assertEqual(kept["title"], "Death Parade")
        self.assertEqual(set(kept["episodes"]["1"]), {"5", "6"})
        self.assertEqual(kept["episodes"]["1"]["6"]["message_id"], 111)
        self.assertEqual(kept["source_items"]["-100123:13792"], 111)
        self.assertEqual(kept["legacy_public_ids"], [45])
        self.assertIn(110, kept["legacy_index_ids"])
        self.assertTrue(kept["index_repair_pending"])
        self.assertEqual(resolve_series_key(merged, "death-parade"),
                         "mangas-fv-death-parade-ep05")
        self.assertEqual(len(merged["legacy_series_records"]), 2)

    def test_repeat_migration_is_idempotent(self):
        once, _ = consolidate_catalog(history())
        twice, report = consolidate_catalog(once)
        self.assertEqual(twice, once)
        self.assertEqual(report["consolidated_entries"], 0)

    def test_collision_is_quarantined_without_deleting_anything(self):
        before = history()
        before["series"]["mangas-fv-death-parade-ep06"]["episodes"] = {
            "1": {"5": {"message_id": 222, "url": "https://t.me/c/1/222"}}
        }
        after, report = consolidate_catalog(before)
        self.assertEqual(after["series"], before["series"])
        self.assertEqual(report["consolidated_entries"], 0)
        self.assertEqual(len(report["skipped_collisions"]), 1)

    def test_active_batch_cannot_be_migrated(self):
        original = history()
        original["active_batch"] = {
            "key": "mangas-fv-death-parade-ep06", "episodes": []}
        after, report = consolidate_catalog(original)
        self.assertEqual(after["series"], original["series"])
        self.assertEqual(report["skipped_active"], ["death-parade"])

    def test_different_shows_do_not_merge(self):
        data = history()
        data["series"]["yu-gi-oh"] = {
            "title": "Yu-Gi-Oh", "episodes": {"1": {"1": {"message_id": 99}}}}
        after, report = consolidate_catalog(data)
        self.assertEqual(len(after["series"]), 2)
        self.assertEqual(report["consolidated_entries"], 1)


if __name__ == "__main__":
    unittest.main()
