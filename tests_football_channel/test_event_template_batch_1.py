"""Offline validation for the first audited 1122x1402 Actu Foot event batch."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import actu_foot_event_templates as events
import programme_styles
import template_cards


class ActuFootEventBatch1Tests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "home": "Borussia Mönchengladbach",
            "away": "Atlético de Madrid",
            "home_logo": "https://fake/home.png",
            "away_logo": "https://fake/away.png",
            "competition": "UEFA Champions League",
            "score": "2-1",
            "minute": "67",
            "source": "ESPN Live",
            "player": "Alexandre Exemple",
            "player_team": "Borussia Mönchengladbach",
            "goalkeeper": "Gardien Exemple",
            "goalkeeper_team": "Atlético de Madrid",
            "reason": "Faute tactique",
            "commentary": "Action confirmée par les données live.",
        }

    def test_five_assets_exist_at_native_size(self):
        batch1 = (
            "poteau",
            "occasion_manquee",
            "arret_decisif",
            "carton_jaune_full",
            "carton_jaune_unknown",
        )
        for category in batch1:
            with self.subTest(category=category):
                path = events.template_path(category, self.payload)
                self.assertTrue(path.is_file(), str(path))
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1122, 1402))

    def test_all_five_render_without_rescaling(self):
        batch1 = (
            "poteau",
            "occasion_manquee",
            "arret_decisif",
            "carton_jaune_full",
            "carton_jaune_unknown",
        )
        dummy = Image.new("RGBA", (300, 150), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in batch1:
                with self.subTest(category=category):
                    image = template_cards.render(category, self.payload)
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertEqual(image.mode, "RGB")

    def test_carton_jaune_alias_selects_complete_or_unknown_variant(self):
        dummy = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            full = template_cards.render("carton_jaune", self.payload)
            unknown_payload = dict(self.payload)
            unknown_payload["player"] = ""
            unknown_payload["card_player"] = ""
            unknown_payload["booked_player"] = ""
            unknown = template_cards.render("carton_jaune", unknown_payload)
            self.assertEqual(full.size, (1122, 1402))
            self.assertEqual(unknown.size, (1122, 1402))
            self.assertIsNotNone(ImageChops.difference(full, unknown).getbbox())

    def test_missing_score_stays_blank_instead_of_assuming_zero_zero(self):
        payload = dict(self.payload)
        payload.pop("score", None)
        payload.pop("scores", None)
        payload.pop("home_score", None)
        payload.pop("away_score", None)
        blank = events.background("poteau", payload)
        rendered = events.render_event("poteau", payload)
        spec = events.SPECS["poteau"]
        for key in ("score_home", "score_away"):
            box = spec[key]
            self.assertEqual(blank.crop(box).tobytes(), rendered.crop(box).tobytes())

    def test_structural_header_is_untouched(self):
        batch1 = (
            "poteau",
            "occasion_manquee",
            "arret_decisif",
            "carton_jaune_full",
            "carton_jaune_unknown",
        )
        dummy = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in batch1:
                with self.subTest(category=category):
                    blank = events.background(category, self.payload)
                    rendered = events.render_event(category, self.payload)
                    self.assertEqual(
                        blank.crop((0, 0, 1122, 330)).tobytes(),
                        rendered.crop((0, 0, 1122, 330)).tobytes(),
                    )


if __name__ == "__main__":
    unittest.main()
