from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("template_cards", SCRIPTS / "template_cards.py")
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)


class TemplateCardsTests(unittest.TestCase):
    def test_logo_respecte_boite_et_ratio(self):
        import programme_styles

        fake = Image.new("RGBA", (400, 200), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=fake):
            logo = tc._load_logo("https://test/logo.png", 60)
        self.assertLessEqual(logo.width, 60)
        self.assertLessEqual(logo.height, 60)
        self.assertEqual(logo.size, (60, 30))

    def test_single_line_reste_dans_la_largeur(self):
        image = Image.new("RGB", (1080, 1080))
        draw = ImageDraw.Draw(image)
        box = (189, 346, 431, 394)
        value, size = tc.draw_single_line(
            draw,
            "Borussia Mönchengladbach International",
            box,
            preferred_size=24,
            min_size=17,
            bold=True,
            max_chars=28,
        )
        face = tc._font(size, True)
        self.assertLessEqual(tc._text_width(draw, value, face), (box[2]-box[0]) - 8)
        self.assertGreaterEqual(size, 17)


    def test_safe_article_frame_preserve_un_ratio_16_9(self):
        source = Image.new("RGB", (1600, 900), (120, 80, 50))
        framed = tc._safe_article_frame(source, (922, 372))
        self.assertEqual(framed.size, (922, 372))

    def test_safe_article_frame_preserve_un_ratio_portrait(self):
        source = Image.new("RGB", (800, 1200), (90, 110, 140))
        framed = tc._safe_article_frame(source, (922, 372))
        self.assertEqual(framed.size, (922, 372))

    def test_flash_titre_max_deux_lignes(self):
        image = Image.new("RGB", (1080, 1080))
        draw = ImageDraw.Draw(image)
        lines, size = tc.draw_multiline(
            draw,
            "Le Portugal annonce officiellement le retour de Cristiano Ronaldo pour les prochaines rencontres internationales",
            tc.FLASH_TITLE_BOX,
            preferred_size=26,
            min_size=22,
            max_lines=2,
            bold=True,
            max_chars=100,
        )
        self.assertLessEqual(len(lines), 2)
        self.assertGreaterEqual(size, 22)

    def test_flash_resume_max_trois_lignes(self):
        image = Image.new("RGB", (1080, 1080))
        draw = ImageDraw.Draw(image)
        lines, _ = tc.draw_multiline(
            draw,
            "Une actualité très longue qui doit être ramenée proprement dans la zone de résumé sans jamais sortir du rectangle préparé par le template et sans créer de quatrième ligne même lorsque la source RSS est particulièrement bavarde.",
            tc.FLASH_SUMMARY_BOX,
            preferred_size=17,
            min_size=14,
            max_lines=3,
            bold=False,
            max_chars=180,
        )
        self.assertLessEqual(len(lines), 3)

    def test_question_sondage_max_deux_lignes(self):
        image = Image.new("RGB", (1080, 1080))
        draw = ImageDraw.Draw(image)
        lines, _ = tc.draw_multiline(
            draw,
            "Paris Saint-Germain contre Manchester City : selon vous quelle équipe remportera cette grande affiche ?",
            tc.POLL_QUESTION_BOX,
            preferred_size=26,
            min_size=24,
            max_lines=2,
            bold=True,
            max_chars=100,
            align="center",
        )
        self.assertLessEqual(len(lines), 2)

    def test_forme_est_decomposee(self):
        values, points = tc._parse_form("V • N • D • V • V  |  10/15 pts")
        self.assertEqual(values, ["V", "N", "D", "V", "V"])
        self.assertEqual(points, "10/15 pts")

    def test_nettoyage_question_sondage(self):
        value = tc._clean_poll_question(
            "🗳️ MR XPRONOS • LE DÉBAT DU JOUR 🔥 PSG vs Le Mans Qui prend les 3 points ?"
        )
        self.assertNotIn("MR XPRONOS", value)
        self.assertNotIn("🗳️", value)
        self.assertIn("PSG", value)

    def test_six_templates_se_generent(self):
        import programme_styles

        fake_logo = Image.new("RGBA", (180, 120), (255, 255, 255, 255))
        fake_photo = Image.new("RGB", (922, 372), (40, 70, 110))
        logo = "https://test/logo.png"

        payloads = {
            "programme": {
                "day": "10/10/2026",
                "matches": [
                    {"home": "Manchester United", "away": "Tottenham Hotspur", "time": "16h30", "home_logo": logo, "away_logo": logo},
                    {"home": "FC Barcelona", "away": "Getafe", "time": "16h30", "home_logo": logo, "away_logo": logo},
                    {"home": "Paris Saint-Germain", "away": "Le Mans", "time": "18h45", "home_logo": logo, "away_logo": logo},
                    {"home": "Real Madrid", "away": "Villarreal", "time": "19h00", "home_logo": logo, "away_logo": logo},
                    {"home": "Borussia Mönchengladbach", "away": "Olympique de Marseille", "time": "20h00", "home_logo": logo, "away_logo": logo},
                ],
            },
            "avant_match": {
                "day": "10/10/2026",
                "home": "Real Madrid",
                "away": "Villarreal",
                "time": "19h00",
                "home_logo": logo,
                "away_logo": logo,
                "home_form": "D • V • V • V • D | 9/15 pts",
                "away_form": "V • V • D • D • D | 6/15 pts",
            },
            "resultat": {
                "day": "10/10/2026",
                "home": "Chelsea",
                "away": "Bournemouth",
                "scores": (5, 1),
                "home_logo": logo,
                "away_logo": logo,
            },
            "statistique": {
                "day": "10/10/2026",
                "home": "Chelsea",
                "away": "Bournemouth",
                "scores": (5, 1),
                "home_logo": logo,
                "away_logo": logo,
                "stat_value": "6",
                "stat_label": "BUTS",
            },
            "flash": {
                "day": "10/10/2026",
                "title": "Le Portugal annonce le retour de Cristiano Ronaldo en novembre",
                "source": "Foot Mercato",
                "summary": "Une actualité courte et propre qui tient dans les trois lignes prévues par le template.",
                "image_url": "https://test/photo.jpg",
            },
            "sondage": {
                "day": "10/10/2026",
                "image_question": "PSG vs Le Mans : qui va gagner ?",
                "image_options": ["Paris Saint-Germain", "Match nul", "Le Mans"],
                "home_logo": logo,
                "away_logo": logo,
            },
        }

        with patch.object(programme_styles, "load_logo", return_value=fake_logo),              patch.object(tc, "remote_photo", return_value=fake_photo):
            for category, payload in payloads.items():
                with self.subTest(category=category):
                    image = tc.render(category, payload)
                    self.assertEqual(image.size, (1080, 1080))
                    self.assertEqual(image.mode, "RGB")


if __name__ == "__main__":
    unittest.main()
