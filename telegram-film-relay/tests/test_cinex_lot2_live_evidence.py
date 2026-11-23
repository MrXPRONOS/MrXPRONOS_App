"""Offline safety and shape checks for the Lot 2 live Telegram evidence reader."""
import unittest
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock
from scripts import cinex_lot2_live_evidence as app


def button(text, url):
    return NS(button=NS(text=text, url=url))


class Lot2EvidenceTests(unittest.TestCase):
    def test_private_fiche_three_buttons(self):
        photo = NS(
            photo=object(),
            buttons=[
                [button("📢 REJOINDRE LE CANAL", "https://t.me/cinexfilms_vf")],
                [button("📁 Rejoindre le dossier", "https://t.me/addlist/testing")],
                [button("⬇️ TÉLÉCHARGER",
                        "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24)],
            ],
        )
        with patch.object(app, "film_folder_url", return_value="https://t.me/addlist/testing"):
            self.assertTrue(app.is_private_fiche(photo, "@cinexfilms_vf"))
            self.assertFalse(app.is_private_fiche(photo, "@cinexanimefr"))

    def test_private_fiche_rejects_extra_button(self):
        message = NS(
            photo=object(), buttons=[
                [button("a", "https://t.me/1")] for _ in range(4)
            ]
        )
        self.assertFalse(app.is_private_fiche(message, "@cinexfilms_vf"))

    def test_public_media_validation_requires_exact_four(self):
        media = NS(buttons=[[button("🎬 VOIR", "https://t.me/c/1/1")]])
        self.assertFalse(app.validate_public_sample(media, "@cinexfilms_vf"))

    def test_public_media_label_must_match_category(self):
        media = NS(buttons=[
            [button("📺 VOIR LA SÉRIE", "https://t.me/c/123/4")],
            [button("⬇️ TÉLÉCHARGER LES VIDÉOS",
                    "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24)],
            [button("🛟 Rejoindre le canal secours", "https://t.me/+abcdefghijklmno")],
            [button("📁 Rejoindre le dossier", "https://t.me/addlist/foo")],
        ])
        self.assertFalse(app.validate_public_sample(
            media, "@cinexfilms_vf", category="films"))

    def test_public_media_validation_never_invents_receipts(self):
        buttons = [
            [button("🎬 VOIR LE FILM", "https://t.me/c/123/45")],
            [button("⬇️ TÉLÉCHARGER LA VIDÉO",
                    "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24)],
            [button("🛟 Rejoindre le canal secours", "https://t.me/+abcdefghijklmno")],
            [button("📁 Rejoindre le dossier", "https://t.me/addlist/foo")],
        ]
        with patch.object(app, "verify_complete_public_video_keyboard", return_value=False):
            self.assertFalse(app.validate_public_sample(NS(buttons=buttons), "@cinexfilms_vf"))


    def test_private_message_id_is_exact_archive(self):
        self.assertEqual(app.private_message_id("https://t.me/c/1234567890/58",
                                                -1001234567890), 58)
        self.assertIsNone(app.private_message_id("https://t.me/c/888888888/58",
                                                 -1001234567890))
        self.assertIsNone(app.private_message_id("https://t.me/c/1234567890/0",
                                                 -1001234567890))
        self.assertIsNone(app.private_message_id("https://t.me/c/1234567890/58?x=1",
                                                 -1001234567890))

    def test_batch_index_requires_exact_category_and_four_buttons(self):
        from film_relay.season_batches_v4 import batch_public_rows
        p = -1001234567890
        public = NS(username="seriesvf_cinex")
        watch = "https://t.me/c/1234567890/145"
        index = "https://t.me/c/1234567890/120"
        with patch("film_relay.season_batches_v4.rescue_link_for",
                   return_value="https://t.me/+VerifiedAnimeRescue123"), \
             patch("film_relay.season_batches_v4.film_folder_url",
                   return_value="https://t.me/addlist/testing"):
            expected = batch_public_rows(public, watch, index, kind="series")
            video = NS(buttons=[[button(label, url)]
                                for row in expected for label, url in row])
            self.assertTrue(app.validate_public_sample(video, public, "series", p))
            self.assertFalse(app.validate_public_sample(video, public, "anime", p))
            wrong_index = "https://t.me/c/9999999999/120"
            forged = NS(buttons=[
                [button(label, wrong_index if i == 1 else url)]
                for i, row in enumerate(expected) for label, url in row
            ])
            self.assertFalse(app.validate_public_sample(forged, public, "series", p))

    def test_private_index_link_must_point_into_same_library(self):
        message = NS(photo=object(), buttons=[
            [button("📢 REJOINDRE LE CANAL", "https://t.me/seriesvf_cinex")],
            [button("📁 Rejoindre le dossier", "https://t.me/addlist/testing")],
            [button("⬇️ TÉLÉCHARGER LES VIDÉOS", "https://t.me/c/1234567890/99")]
        ])
        with patch.object(app, "film_folder_url",
                          return_value="https://t.me/addlist/testing"):
            self.assertTrue(app.is_private_fiche(message, "@seriesvf_cinex",
                                                 -1001234567890))
            self.assertFalse(app.is_private_fiche(message, "@seriesvf_cinex",
                                                  -1009999999999))
            self.assertFalse(app.is_private_fiche(message, "@seriesvf_cinex"))

    def test_batch_episode_d1_verified_by_actual_index_line(self):
        p = -1001234567890
        link = "https://t.me/c/1234567890/210"
        url = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        client = NS(get_messages=AsyncMock(return_value=NS(
            raw_text="S01E01 — " + url + "\\nS01E02 — " + url)))
        video = NS(raw_text="🌸 Titre — S01E02\\n#CINEX_VIDEO_24H_V1")
        with patch.object(app, "check_receipt", return_value=True) as receipt:
            ok = asyncio.run(app.check_download_target(
                client, p, p, video, link))
        self.assertTrue(ok)
        receipt.assert_called_once_with(url)
        client.get_messages.assert_awaited_once_with(p, ids=210)

    def test_batch_download_cannot_use_a_different_episode_receipt(self):
        p = -1001234567890
        link = "https://t.me/c/1234567890/210"
        url = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        client = NS(get_messages=AsyncMock(return_value=NS(
            raw_text="S01E01 — " + url)))
        video = NS(raw_text="S01E02\\n#CINEX_VIDEO_24H_V1")
        with patch.object(app, "check_receipt", return_value=True):
            self.assertFalse(asyncio.run(
                app.check_download_target(client, p, p, video, link)))

    def test_d1_receipt_requires_approved_central_stock(self):
        url = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        class Registry:
            def _query(self, sql, params):
                self.sql = sql
                self.params = params
                return {"results": [{"source_message_id": 123}]}
        registry = Registry()
        with patch.object(app, "RadarRegistry", return_value=registry):
            self.assertTrue(app.check_receipt(url))
        self.assertIn("JOIN cine_private_stock_config", registry.sql)
        self.assertIn("l.status='published'", registry.sql)
        self.assertEqual(registry.params, ["A"*24])


if __name__ == "__main__":
    unittest.main()
