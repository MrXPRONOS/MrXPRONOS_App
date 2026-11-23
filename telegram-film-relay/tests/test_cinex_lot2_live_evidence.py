"""Offline safety and shape checks for the Lot 2 live Telegram evidence reader."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
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


if __name__ == "__main__":
    unittest.main()
