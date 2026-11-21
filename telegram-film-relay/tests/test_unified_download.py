"""Offline tests: all six CineX categories route download to ONE verified channel."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from film_relay.unified_download import UnifiedLibrary, configured_private_id
from film_relay.publication import url_button_rows
from film_relay.radar_download_registry import is_bot_download_url, RadarRegistry


CENTRAL = -1004987123456
BOT_LINK = "https://t.me/CineRadarFr_Bot?start=d_ABCDEFGHIJKLMNOPQRSTUVWX"


class DummyRegistry:
    def __init__(self):
        self.calls = []
    def register(self, **kwargs):
        self.calls.append(kwargs)
        return BOT_LINK



def media(mid, doc, *, title="Un film"):
    return NS(id=mid, raw_text=title, video=object(),
              document=NS(id=doc, attributes=[]), media=object(),
              file=NS(name=title+".mkv"), noforwards=False)


class DummyClient:
    def __init__(self, rows=(), *, verify=True, admin=True, private=True):
        self.rows = list(rows)
        self.sent = []
        self.verify = verify
        self.admin = admin
        self.private = private
        self.target = NS(id=CENTRAL, username=None if private else "public_library",
                         broadcast=True)
    async def get_me(self):
        return NS(id=42)
    async def get_permissions(self, channel, identity):
        return NS(is_creator=self.admin, is_admin=False, post_messages=False)
    async def iter_messages(self, channel, limit=4000):
        for item in self.rows[:limit]:
            yield item
    async def get_messages(self, channel, ids):
        result = next((m for m in self.rows if m.id == ids), None)
        if result is not None and not self.verify and self.sent and ids == self.sent[-1]:
            return media(ids, -1)
        return result
    async def send_file(self, channel, video, *, caption, parse_mode):
        self.sent.append(len(self.rows)+1)
        msg = media(self.sent[-1], self.current_doc)
        self.rows.append(msg)
        return NS(id=msg.id)


class CentralLibraryTests(unittest.TestCase):
    def test_missing_private_id_means_existing_links_unchanged(self):
        self.assertIsNone(configured_private_id({}))
        client = DummyClient()
        library = UnifiedLibrary(client, env={})
        self.assertIsNone(asyncio.run(library.store(
            media(1, 700), category="films", title="Film")))
        self.assertFalse(client.sent)

    def test_malformed_private_id_is_rejected(self):
        for val in ("@my_channel", "-100123", "1004987123456", "https://t.me/c/123"):
            with self.subTest(val=val), self.assertRaises(RuntimeError):
                configured_private_id({"CINEX_UNIFIED_PRIVATE_CHANNEL": val})

    def test_six_categories_use_same_private_destination(self):
        for category in ("films", "desir", "comedie", "anime", "action", "series"):
            with self.subTest(category=category):
                client = DummyClient()
                client.current_doc = 700
                library = UnifiedLibrary(client, env={"CINEX_UNIFIED_PRIVATE_CHANNEL": str(CENTRAL)}, registry=DummyRegistry())
                with (patch("film_relay.runner.resolve_peer", return_value=client.target),
                      patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id)):
                    result = asyncio.run(library.store(
                        media(1, 700), category=category, title="Vidéo test",
                        public=NS(id=-1001234567890, username='CineXFilms_vf')))
                self.assertEqual(result, BOT_LINK)
                self.assertEqual(len(client.sent), 1)

    def test_existing_document_is_reused_without_second_upload(self):
        client = DummyClient(rows=[media(25, 555)])
        library = UnifiedLibrary(client, env={"CINEX_UNIFIED_PRIVATE_CHANNEL": str(CENTRAL)}, registry=DummyRegistry())
        with (patch("film_relay.runner.resolve_peer", return_value=client.target),
              patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id)):
            result = asyncio.run(library.store(
                media(1, 555), category="anime", title="Episode 3", public=NS(id=-1009999999999, username="CineXAnimeFR")))
        self.assertEqual(result, BOT_LINK)
        self.assertEqual(client.sent, [])

    def test_broken_duplicate_receipt_blocks_and_never_guesses(self):
        client = DummyClient(rows=[media(25, 555)])
        library = UnifiedLibrary(client, env={"CINEX_UNIFIED_PRIVATE_CHANNEL": str(CENTRAL)}, registry=DummyRegistry())
        async def bad_get_messages(channel, ids):
            return media(ids, 999)
        client.get_messages = bad_get_messages
        with (patch("film_relay.runner.resolve_peer", return_value=client.target),
              patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id)):
            with self.assertRaisesRegex(RuntimeError, "incohérent"):
                asyncio.run(library.store(
                    media(1, 555), category="films", title="Film", public=NS(id=-1009999999999, username="CineXFilms_vf")))
        self.assertFalse(client.sent)

    def test_private_channel_must_be_admin_accessible(self):
        client = DummyClient(admin=False)
        library = UnifiedLibrary(client, env={"CINEX_UNIFIED_PRIVATE_CHANNEL": str(CENTRAL)}, registry=DummyRegistry())
        with (patch("film_relay.runner.resolve_peer", return_value=client.target),
              patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id)):
            with self.assertRaisesRegex(RuntimeError, "doit pouvoir envoyer"):
                asyncio.run(library.prepare())
        self.assertFalse(client.sent)

    def test_central_must_remain_private(self):
        client = DummyClient(private=False)
        library = UnifiedLibrary(client, env={"CINEX_UNIFIED_PRIVATE_CHANNEL": str(CENTRAL)}, registry=DummyRegistry())
        with (patch("film_relay.runner.resolve_peer", return_value=client.target),
              patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id)):
            with self.assertRaisesRegex(RuntimeError, "rester privée"):
                asyncio.run(library.prepare())

    def test_public_channel_can_never_be_central(self):
        client = DummyClient()
        library = UnifiedLibrary(client, env={"CINEX_UNIFIED_PRIVATE_CHANNEL": str(CENTRAL)}, registry=DummyRegistry())
        with (patch("film_relay.runner.resolve_peer", return_value=client.target),
              patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id)):
            with self.assertRaisesRegex(RuntimeError, "canal public"):
                asyncio.run(library.prepare(public=NS(id=CENTRAL)))

    def test_unverified_upload_is_not_published_as_a_link(self):
        client = DummyClient(verify=False)
        client.current_doc = 700
        library = UnifiedLibrary(client, env={"CINEX_UNIFIED_PRIVATE_CHANNEL": str(CENTRAL)}, registry=DummyRegistry())
        with (patch("film_relay.runner.resolve_peer", return_value=client.target),
              patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id)):
            with self.assertRaisesRegex(RuntimeError, "non vérifiée"):
                asyncio.run(library.store(
                    media(1, 700), category="series", title="Episode", public=NS(id=-1009999999999, username="seriesvf_cinex")))

    def test_download_button_points_to_central_receipt(self):
        main = "https://t.me/c/4392607284/20"
        central = BOT_LINK
        with patch("film_relay.rescue_channels.add_rescue_tuple_row",
                   side_effect=lambda rows, public: rows):
            rows = url_button_rows(main, public_peer="CineX", download_url=central)
        self.assertEqual(rows[0][0][1], main)
        self.assertEqual(rows[1][0][1], central)
        self.assertIn("TÉLÉCHARGER", rows[1][0][0])

    def test_direct_private_link_is_not_download_button(self):
        self.assertFalse(is_bot_download_url("https://t.me/c/4987123456/30"))
        self.assertTrue(is_bot_download_url(BOT_LINK))
        with patch("film_relay.rescue_channels.add_rescue_tuple_row",
                   side_effect=lambda rows, public: rows):
            with self.assertRaisesRegex(ValueError, "CinéRadar"):
                url_button_rows("https://t.me/c/4392607284/20",
                                public_peer="CineX",
                                download_url="https://t.me/c/4987123456/30")

    def test_without_common_channel_no_fake_download_button(self):
        main = "https://t.me/c/4392607284/20"
        with patch("film_relay.rescue_channels.add_rescue_tuple_row",
                   side_effect=lambda rows, public: rows):
            rows = url_button_rows(main, public_peer="CineX")
        self.assertFalse(any("TÉLÉCHARGER" in label for row in rows
                             for label, url in row))


if __name__ == "__main__":
    unittest.main()
