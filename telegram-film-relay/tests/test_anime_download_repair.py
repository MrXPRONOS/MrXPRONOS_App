"""Exact-ID existing-episode download repair is bounded and idempotent."""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from film_relay.anime_download_repair import repair_existing_download_links


def movie(doc=123):
    return NS(video=object(), document=NS(id=doc, attributes=[]))


class DownloadRepairTests(unittest.TestCase):
    def test_two_existing_private_receipts_are_registered_once_each(self):
        data = {"series": {"naruto": {
            "title": "Naruto",
            "episodes": {"1": {
                "1": {"message_id": 101},
                "2": {"message_id": 102},
                "3": {"message_id": 103},
            }},
        }}}
        client = NS(get_messages=AsyncMock(side_effect=[
            movie(55), movie(56),
        ]))
        unified = NS(
            target_id=-1001234567890,
            store=AsyncMock(side_effect=[
                "https://t.me/CineRadarFr_Bot?start=1",
                "https://t.me/CineRadarFr_Bot?start=2",
            ]),
        )
        saved = []
        stat = asyncio.run(repair_existing_download_links(
            client, "@private", "@public", unified, data,
            lambda d: saved.append(True), limit=2, pause_seconds=0))
        self.assertEqual(stat["registered"], 2)
        self.assertEqual(len(saved), 2)
        self.assertEqual(client.get_messages.await_count, 2)
        self.assertEqual(data["series"]["naruto"]["episodes"]["1"]["3"],
                         {"message_id": 103})
        self.assertEqual(unified.store.await_count, 2)

    def test_existing_link_is_never_refreshed_or_copied(self):
        data = {"series": {"naruto": {
            "episodes": {"1": {"1": {
                "message_id": 101, "download_url": "existing-url"
            }}},
        }}}
        client = NS(get_messages=AsyncMock())
        unified = NS(target_id=-1001234567890, store=AsyncMock())
        stats = asyncio.run(repair_existing_download_links(
            client, "@private", "@public", unified, data,
            lambda _: None, limit=2, pause_seconds=0))
        self.assertEqual(stats["skipped_existing"], 1)
        client.get_messages.assert_not_awaited()
        unified.store.assert_not_awaited()

    def test_failed_or_uncertain_central_copy_is_not_retried(self):
        data = {"series": {"naruto": {
            "episodes": {"1": {"1": {"message_id": 101}}},
        }}}
        client = NS(get_messages=AsyncMock(return_value=movie(55)))
        unified = NS(target_id=-1001234567890,
                     store=AsyncMock(side_effect=TimeoutError()))
        with self.assertRaises(TimeoutError):
            asyncio.run(repair_existing_download_links(
                client, "@private", "@public", unified, data,
                lambda _: None, limit=2, pause_seconds=0))
        self.assertNotIn("download_url",
                         data["series"]["naruto"]["episodes"]["1"]["1"])
        self.assertEqual(unified.store.await_count, 1)

    def test_opt_in_zero_never_touches_telegram(self):
        client = NS(get_messages=AsyncMock())
        unified = NS(target_id=-1001234567890, store=AsyncMock())
        stats = asyncio.run(repair_existing_download_links(
            client, "@private", "@public", unified, {"series": {}},
            lambda _: None, limit=0))
        self.assertEqual(stats["checked"], 0)
        unified.store.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
