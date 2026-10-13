import io
import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import football_news_engine as n


class NewsEngineTests(unittest.TestCase):
    def test_classification_editoriale(self):
        category, score = n.classify_news(
            "Officiel : le club annonce sa nouvelle recrue",
            "Le joueur a signé et le transfert est désormais confirmé.",
            "https://www.footmercato.net/flux-rss",
        )
        self.assertIn(category, {"Officiel", "Mercato"})
        self.assertGreaterEqual(score, 2)

        category, _ = n.classify_news(
            "Le Sénégal dévoile sa liste",
            "Le sélectionneur a convoqué vingt-cinq joueurs pour la prochaine rencontre.",
            "https://www.rfi.fr/fr/afrique-foot/rss",
        )
        self.assertIn(category, {"Convocations", "Afrique"})

    def test_resume_et_points_ne_creent_pas_de_faits(self):
        source = (
            "Le club a confirmé le forfait du joueur pour la rencontre de samedi. "
            "Il souffre d'une blessure musculaire. "
            "Aucune date de retour n'a encore été communiquée."
        )
        short = n.short_summary(source, 220)
        points = n.key_points(source)
        self.assertTrue(short)
        self.assertLessEqual(len(short), 220)
        self.assertTrue(points)
        for point in points:
            self.assertIn(point, source)

    def test_resume_conserve_les_listes_numerotees_sans_casser_scores_et_heures(self):
        source=(
            "Les trois points à retenir : 1: Arsenal récupère deux titulaires "
            "2. Chelsea conserve son onze habituel "
            "3) Le coup d'envoi reste confirmé"
        )
        short=n.short_summary(source,330)
        self.assertIn("1: Arsenal",short)
        self.assertIn("\n2. Chelsea",short)
        self.assertIn("\n3) Le coup",short)

        ordinary=n.preserve_numbered_breaks(
            "Arsenal mène 1:0 à la pause et la reprise est prévue à 12:30."
        )
        self.assertNotIn("\n0",ordinary)
        self.assertIn("1:0",ordinary)
        self.assertIn("12:30",ordinary)

    def test_image_portrait_utilise_fond_floute(self):
        source = Image.new("RGB", (500, 1000), (120, 130, 140))
        raw = io.BytesIO()
        source.save(raw, "JPEG")
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "news.webp"
            mode = n.prepare_real_image(raw.getvalue(), out)
            self.assertEqual(mode, "blur-contain")
            with Image.open(out) as rendered:
                self.assertEqual(rendered.size, (1200, 675))
                self.assertEqual(rendered.format, "WEBP")

    def test_news_record_partage_un_seul_slug_site_telegram(self):
        profile = n.SourceProfile("RFI Afrique Foot", 90, "afrique")
        record = n.build_news_record(
            slug="abc123",
            title="Une information football",
            body="Le sélectionneur a communiqué son groupe. Trois nouveaux joueurs ont été appelés.",
            link="https://example.com/article",
            published="2026-10-13T01:00:00+00:00",
            source=profile,
            feed_url="https://www.rfi.fr/fr/afrique-foot/rss",
            image_path="assets/images/footnews/abc123.webp",
            source_image="https://example.com/image.jpg",
            image_mode="smart-crop",
            category="Convocations",
            editorial_score=4,
        )
        self.assertEqual(record["site_url"], n.SITE_BASE + "infos.html?news=abc123")
        self.assertEqual(record["image_origin"], "source")
        self.assertTrue(record["content"])
        self.assertTrue(record["telegram_summary"])


if __name__ == "__main__":
    unittest.main()
