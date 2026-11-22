"""Tests hors ligne : classes de canaux administrés et rapport privé."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from telegram_admin_cinema_catalog import (
    classify_channel, exclude, format_catalog, send_private_catalog,
)


class ClassificationTest(unittest.TestCase):
    def test_torrent9_private_and_public_are_excluded(self):
        self.assertTrue(exclude("ToRRenT-9 VF"))
        self.assertIsNone(classify_channel("Torrent9 Films", "torrent9_movies"))
        self.assertIsNone(classify_channel("Bibliothèque", "@torrent9"))
        self.assertIsNone(classify_channel("Torrent 9", None))

    def test_public_film_genres(self):
        row = classify_channel("Films Action Romance VF", "movies_action")
        self.assertEqual(row["visibility"], "public")
        self.assertEqual(row["categories"], ["films"])
        self.assertIn("action", row["genres"])
        self.assertIn("romance", row["genres"])
        self.assertEqual(row["language"], "VF")
        self.assertEqual(row["scope"], "thématique")

    def test_private_anime_subgenre(self):
        row = classify_channel("Mangas Shonen Isekai VOSTFR", None)
        self.assertEqual(row["visibility"], "privé")
        self.assertEqual(row["categories"], ["animes"])
        self.assertEqual(row["language"], "VOSTFR")
        self.assertIn("isekai", row["genres"])

    def test_series_drama(self):
        row = classify_channel("Séries K-Drama romantiques", "k_drama2026")
        self.assertEqual(row["categories"], ["series"])
        self.assertIn("coréen", row["genres"])
        self.assertIn("romance", row["genres"])

    def test_single_anime_remains_separate(self):
        row = classify_channel("One Piece episodes VF", None)
        self.assertEqual(row["categories"], ["animes"])
        self.assertEqual(row["scope"], "dédié à une œuvre")
        self.assertEqual(row["dedicated_title"], "one piece")

    def test_single_series_remains_separate(self):
        row = classify_channel("La Casa de Papel - saison complète", "casadepapel")
        self.assertEqual(row["categories"], ["series"])
        self.assertIsNotNone(row["dedicated_title"])

    def test_single_film_remains_separate(self):
        row = classify_channel("John Wick - le film", "wick_movies")
        self.assertEqual(row["categories"], ["films"])
        self.assertEqual(row["scope"], "dédié à une œuvre")

    def test_description_enriches_genre(self):
        row = classify_channel("Cinéma VF", None, "Uniquement des thrillers et films d'horreur.")
        self.assertIn("thriller", row["genres"])
        self.assertIn("horreur", row["genres"])

    def test_cinex_compound_brand_names(self):
        comedy = classify_channel("CineXComedie", "CineXComedie")
        romance = classify_channel("CineXDesir", None)
        self.assertEqual(comedy["categories"], ["films"])
        self.assertIn("comédie", comedy["genres"])
        self.assertIn("romance", romance["genres"])
        self.assertEqual(romance["visibility"], "privé")

    def test_unknown_not_mistaken_for_film(self):
        row = classify_channel("Bulletin foot du jour", None)
        self.assertEqual(row["categories"], ["autres"])
        self.assertTrue(row["needs_review"])

    def test_public_and_private_only_in_respective_sections(self):
        public = classify_channel("Films action", "cinexfilms")
        private = classify_channel("Anime Shonen", None)
        dedicated = classify_channel("One Piece VF", None)
        body = format_catalog([public, private, dedicated], "2026-11-22")
        public_section, private_section = body.split("===== CANAUX PRIVÉS (2) =====")
        self.assertIn("https://t.me/cinexfilms", public_section)
        self.assertNotIn("Anime Shonen", public_section)
        self.assertNotIn("https://t.me/cinexfilms", private_section)
        self.assertIn("CANAUX RÉSERVÉS À UN TITRE", private_section)
        self.assertIn("one piece", private_section)


class PrivateDeliveryTest(unittest.IsolatedAsyncioTestCase):
    async def test_saved_messages_document_only_and_idempotent(self):
        class Client:
            def __init__(self):
                self.sent = []
            async def iter_messages(self, target, limit):
                assert target == "me"
                if False:
                    yield None
            async def send_file(self, target, document, caption, force_document):
                assert target == "me"
                assert force_document
                assert "CINEX-ADMIN-CATALOG" in caption
                self.sent.append(document.read().decode("utf-8"))
        client = Client()
        rows = [classify_channel("Anime Shonen", None)]
        self.assertTrue(await send_private_catalog(client, rows))
        self.assertIn("Anime Shonen", client.sent[0])


if __name__ == "__main__":
    unittest.main()
