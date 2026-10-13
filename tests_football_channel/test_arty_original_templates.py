"""Regression tests for the 10 optional original Arty Football designs."""
import importlib.util
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import arty_football_templates as at
import arty_original_templates as premium
from install_arty_originals import BY_NUMBER, identify, import_archive


def sample_image():
    image = Image.new("RGB", (1122, 1402), "#061522")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 1102, 1382), outline="#e2ba61", width=5)
    return image


def example():
    return {
        "home": "Borussia Mönchengladbach",
        "away": "Jagiellonia Białystok",
        "home_players": [f"Joueur de l'équipe domicile numéro {i}" for i in range(1, 12)],
        "away_players": [f"Joueur de l'équipe visiteuse numéro {i}" for i in range(1, 12)],
        "home_logo": "https://example.invalid/home",
        "away_logo": "https://example.invalid/away",
        "competition": "Championnat international de démonstration",
        "scores": [12, 10],
        "minute": "90+5'",
        "source": "Simulation",
        "headline": "Statistique avancée et vérifiée",
        "value": "82 %",
        "lines": ["Possession: 82 %", "Tirs cadrés : 21", "Fautes : 15", "Corners : 8"],
        "question": "Quel est votre choix pour cette rencontre ?",
        "options": ["Équipe domicile", "Match nul", "Équipe visiteuse", "Autre"],
        "goal": {"player": "Prénom Nom très long", "minute_text": "90+5'"},
        "reaction": "Une réaction après match volontairement longue pour contrôler les retours à la ligne.",
        "summary": "Résumé de démonstration factuelle. " * 10,
    }


class OriginalArtworkTests(unittest.TestCase):
    def test_image_numbers(self):
        for n, category in BY_NUMBER.items():
            self.assertEqual(identify(f"image-gen-{n}(20261013-103811).png"), category)

    def test_text_slot_stays_within_image(self):
        pic = sample_image().convert("RGBA")
        result = premium.text(pic, "W" * 300, (95, 230, 350, 304), size=65, min_size=16)
        self.assertTrue(result)
        self.assertEqual(pic.size, (1122, 1402))

    def test_render_original_ten(self):
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "original.png"
            sample_image().save(original)
            payload = example()
            def dummy_logo(image, url, bounds, required=False):
                return True
            with patch.object(premium, "logo", side_effect=dummy_logo):
                for category in BY_NUMBER.values():
                    with self.subTest(category=category):
                        rendered = premium.render_premium(category, payload, original)
                        self.assertEqual(rendered.size, (1080, 1350))

    def test_missing_composition_lineup_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "art.png"
            sample_image().save(path)
            item = example()
            item["away_players"] = ["One player"]
            with self.assertRaises(ValueError):
                premium.render_premium("composition", item, path)

    def test_import_rejects_incomplete_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stream = io.BytesIO()
            sample_image().save(stream, "PNG")
            archive = root / "archive.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("image-gen-1.png", stream.getvalue())
            with self.assertRaisesRegex(ValueError, "incomplète"):
                import_archive(archive, root / "output")
            self.assertFalse((root / "output").exists())

    def test_archive_mapping_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stream = io.BytesIO()
            sample_image().save(stream, "PNG")
            archive = root / "archive.zip"
            with zipfile.ZipFile(archive, "w") as z:
                for n in BY_NUMBER:
                    z.writestr(f"image-gen-{n}(original).png", stream.getvalue())
            result = import_archive(archive, root / "output", dry_run=True)
            self.assertEqual(len(result), 10)
            self.assertFalse((root / "output").exists())

    def test_existing_fallback_when_no_original(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(at, "ORIGINAL_DIR", Path(temp)):
                pic = at.overlay("quiz", example())
            self.assertEqual(pic.size, (1080, 1350))


if __name__ == "__main__":
    unittest.main()
