"""Fail-closed tests for one-off Telegram legacy-card recovery."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from film_relay.anime_catalog import repair_legacy_indexes
from scripts.verify_repair_anime_legacy import pending_keys, run


class LegacySafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_only_pending_groups_selected(self):
        self.assertEqual(pending_keys({"series": {
            "mangas-fv-death-parade-ep05": {"index_repair_pending": True},
            "other": {"index_repair_pending": False},
        }}), ["mangas-fv-death-parade-ep05"])

    async def test_unknown_pending_key_cannot_be_modified(self):
        with patch("scripts.verify_repair_anime_legacy.read_catalog", return_value={
            "series": {"unknown-series": {"index_repair_pending": True}}}):
            with self.assertRaises(RuntimeError):
                await run(apply=True)

    async def test_active_batch_blocks_any_repair(self):
        with patch("scripts.verify_repair_anime_legacy.read_catalog", return_value={
            "series": {"mangas-fv-death-parade-ep05": {"index_repair_pending": True}},
            "active_batch": {"key": "unfinished"},
        }):
            self.assertEqual(await run(apply=True), 3)

    async def test_index_marker_failure_cannot_change_public_cards(self):
        key = "mangas-fv-death-parade-ep05"
        catalogue = {"series": {key: {
            "title": "Death Parade",
            "index_repair_pending": True,
            "season_indices": {"1": 107},
            "episodes": {"1": {"5": {"message_id": 108, "url": "https://t.me/c/1/108"}}},
            "main_index_id": 106,
            "legacy_public_ids": [45],
        }}}
        user = NS(get_messages=AsyncMock(return_value=NS(raw_text="wrong original marker")))
        bot = NS(edit_reply_markup=AsyncMock())
        with patch("film_relay.anime_catalog.save_catalog"):
            count = await repair_legacy_indexes(
                user, bot, NS(), NS(), NS(), -100123,
                catalogue, pause=0)
        self.assertEqual(count, 0)
        self.assertTrue(catalogue["series"][key]["index_repair_pending"])
        bot.edit_reply_markup.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
