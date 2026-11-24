"""Offline safety and shape checks for the Lot 2 live Telegram evidence reader."""
import unittest
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import patch, AsyncMock
from scripts import cinex_lot2_live_evidence as app


def button(text, url):
    return NS(button=NS(text=text, url=url))


class Lot2EvidenceTests(unittest.TestCase):
    def test_live_audit_runs_after_main_publication_not_before(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[2] / ".github" /
                    "workflows" / "cinex-lot2-live-evidence.yml").read_text("utf-8")
        self.assertIn("workflow_run:", workflow)
        self.assertIn("types: [completed]", workflow)
        self.assertIn("CineX - Films, Desir, Comedie, Anime et Decouverte (6h)",
                      workflow)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
        self.assertIn("head_repository.full_name == github.repository", workflow)
        self.assertIn("--require-complete", workflow)
        self.assertNotIn("cron: '17 6 * * *'", workflow)

    def test_required_acceptance_rejects_six_missing_live_samples(self):
        categories = ("films", "series", "desir", "comedie", "anime", "action")
        rows = [
            {"category": c, "latest_public_v4": "pending_no_sample",
             "public_photo_four_buttons": "pending_no_sample",
             "private_three_buttons": "pending_no_sample",
             "central_receipt": "pending_no_sample", "errors": 0}
            for c in categories
        ]
        with (patch.object(app, "inspect", new_callable=AsyncMock,
                           return_value=rows),
              patch("sys.argv", ["cinex_lot2_live_evidence.py",
                                 "--require-complete"])):
            with self.assertRaisesRegex(SystemExit, "LOT2_NOT_ACCEPTED"):
                app.main()

    def test_required_acceptance_passes_only_six_verified_categories(self):
        categories = ("films", "series", "desir", "comedie", "anime", "action")
        rows = [
            {"category": c, "latest_public_v4": "verified",
             "public_photo_four_buttons": "verified",
             "private_three_buttons": "verified",
             "central_receipt": "verified", "errors": 0}
            for c in categories
        ]
        with (patch.object(app, "inspect", new_callable=AsyncMock,
                           return_value=rows),
              patch("sys.argv", ["cinex_lot2_live_evidence.py",
                                 "--require-complete"])):
            app.main()
        rows[0]["central_receipt"] = "not_verified"
        with (patch.object(app, "inspect", new_callable=AsyncMock,
                           return_value=rows),
              patch("sys.argv", ["cinex_lot2_live_evidence.py",
                                 "--require-complete"])):
            with self.assertRaisesRegex(SystemExit, "LOT2_NOT_ACCEPTED"):
                app.main()

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
            raw_text="S01E01 — " + url + "\nS01E02 — " + url)))
        video = NS(raw_text="🌸 Titre — S01E02\\n#CINEX_VIDEO_24H_V1")
        with patch.object(app, "check_receipt", new_callable=AsyncMock, return_value=True) as receipt:
            ok = asyncio.run(app.check_download_target(
                client, p, p, video, link))
        self.assertTrue(ok)
        receipt.assert_awaited_once_with(client, video, url)
        client.get_messages.assert_awaited_once_with(p, ids=210)

    def test_batch_download_cannot_use_a_different_episode_receipt(self):
        p = -1001234567890
        link = "https://t.me/c/1234567890/210"
        url = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        client = NS(get_messages=AsyncMock(return_value=NS(
            raw_text="S01E01 — " + url)))
        video = NS(raw_text="S01E02\n#CINEX_VIDEO_24H_V1")
        with patch.object(app, "check_receipt", return_value=True):
            self.assertFalse(asyncio.run(
                app.check_download_target(client, p, p, video, link)))

    def test_d1_receipt_requires_approved_central_stock_and_exact_document(self):
        url = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        stock_id = -1001234567890
        class Registry:
            row = {"source_chat_id": str(stock_id), "source_message_id": 123}
            def _query(self, sql, params):
                self.sql = sql
                self.params = params
                return {"results": [self.row]}
        registry = Registry()
        stock = NS(id=stock_id, broadcast=True, username=None)
        expected = NS(id=10, video=object(), document=NS(id=555))
        stored = NS(id=123, video=object(), document=NS(id=555))
        client = NS(get_messages=AsyncMock(return_value=stored))
        with (patch.object(app, "RadarRegistry", return_value=registry),
              patch.object(app, "configured_private_id", return_value=stock_id),
              patch.object(app, "resolve_peer", new=AsyncMock(return_value=stock)),
              patch("telethon.utils.get_peer_id", return_value=stock_id)):
            self.assertTrue(asyncio.run(app.check_receipt(client, expected, url)))
            stored.document.id = 999
            self.assertFalse(asyncio.run(app.check_receipt(client, expected, url)))
            stored.document.id = 555
            registry.row["source_chat_id"] = "-1009999999999"
            self.assertFalse(asyncio.run(app.check_receipt(client, expected, url)))
        self.assertIn("JOIN cine_private_stock_config", registry.sql)
        self.assertIn("l.status='published'", registry.sql)
        self.assertEqual(registry.params, ["A"*24])

    def test_batch_duplicate_episode_lines_are_not_valid(self):
        p = -1001234567890
        link = "https://t.me/c/1234567890/210"
        url = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        client = NS(get_messages=AsyncMock(return_value=NS(
            raw_text="S01E02 — " + url + "\nS01E02 — " + url)))
        with patch.object(app, "check_receipt", new_callable=AsyncMock, return_value=True) as receipt:
            self.assertFalse(asyncio.run(app.check_download_target(
                client, p, p, NS(raw_text="S01E02"), link)))
            receipt.assert_not_awaited()

    def test_batch_private_cover_must_match_public_video_index(self):
        p = -1001234567890
        index = "https://t.me/c/1234567890/210"
        cover_link = "https://t.me/c/1234567890/211"
        cover = NS(photo=object(), buttons=[
            [button("📢 REJOINDRE LE CANAL", "https://t.me/seriesvf_cinex")],
            [button("📁 Rejoindre le dossier", "https://t.me/addlist/testing")],
            [button("⬇️ TÉLÉCHARGER LES VIDÉOS", index)],
        ])
        video = NS(buttons=[
            [button("📺 VOIR LA SÉRIE", cover_link)],
            [button("⬇️ TÉLÉCHARGER LES VIDÉOS", index)],
            [button("🛟 Rejoindre le canal secours", "https://t.me/+VerifiedAnimeRescue123")],
            [button("📁 Rejoindre le dossier", "https://t.me/addlist/testing")],
        ])
        class Client:
            async def get_messages(self, peer, ids):
                return cover
        with patch.object(app, "film_folder_url",
                          return_value="https://t.me/addlist/testing"):
            self.assertTrue(asyncio.run(app.matching_private_fiche(
                Client(), p, p, "@seriesvf_cinex", video)))

        cover.buttons[2][0].button.url = "https://t.me/c/1234567890/999"
        with patch.object(app, "film_folder_url",
                          return_value="https://t.me/addlist/testing"):
            self.assertFalse(asyncio.run(app.matching_private_fiche(
                Client(), p, p, "@seriesvf_cinex", video)))

    def test_single_video_private_poster_must_have_same_d1_link(self):
        p = -1001234567890
        dl = "https://t.me/CineRadarFr_Bot?start=d_" + "A"*24
        private_video = NS(video=object(), document=NS(id=555))
        public_video = NS(video=object(), document=NS(id=555), buttons=[
            [button("🎬 VOIR LE FILM", "https://t.me/c/1234567890/211")],
            [button("⬇️ TÉLÉCHARGER LA VIDÉO", dl)],
            [button("🛟 Rejoindre le canal secours", "https://t.me/+VerifiedAnimeRescue123")],
            [button("📁 Rejoindre le dossier", "https://t.me/addlist/testing")],
        ])
        cover = NS(photo=object(), buttons=[
            [button("📢 REJOINDRE LE CANAL", "https://t.me/cinexfilms_vf")],
            [button("📁 Rejoindre le dossier", "https://t.me/addlist/testing")],
            [button("⬇️ TÉLÉCHARGER", dl)],
        ])
        class Client:
            async def get_messages(self, peer, ids):
                return private_video
            async def iter_messages(self, peer, limit, max_id):
                yield cover
        with patch.object(app, "film_folder_url",
                          return_value="https://t.me/addlist/testing"):
            self.assertTrue(asyncio.run(app.matching_private_fiche(
                Client(), p, p, "@cinexfilms_vf", public_video)))
            cover.buttons[2][0].button.url = (
                "https://t.me/CineRadarFr_Bot?start=d_" + "B"*24)
            self.assertFalse(asyncio.run(app.matching_private_fiche(
                Client(), p, p, "@cinexfilms_vf", public_video)))


if __name__ == "__main__":
    unittest.main()
