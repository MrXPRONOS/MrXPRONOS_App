"""Offline validation for the third audited 1122x1402 Actu Foot event batch."""
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


BATCH3 = (
    "intervention_medicale",
    "blessure_confirmee",
    "retour_au_jeu",
    "match_suspendu",
    "match_interrompu_full",
)


class ActuFootEventBatch3Tests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "home": "AS Monaco",
            "away": "Olympique Lyonnais",
            "home_logo": "https://fake/home.png",
            "away_logo": "https://fake/away.png",
            "competition": "Ligue 1",
            "score": "1-1",
            "minute": "61",
            "source": "ESPN Live",
            "player": "Joueur Exemple",
            "player_team": "AS Monaco",
            "treatment": "Soins en cours sur la pelouse",
            "injury_status": "Blessure confirmée",
            "reason": "Incident sur la pelouse",
            "status": "Match arrêté jusqu’à nouvel ordre",
            "info": "Information vérifiée par la source live.",
        }

    def test_five_batch3_assets_exist_at_native_size(self):
        for category in BATCH3:
            with self.subTest(category=category):
                path = events.template_path(category, self.payload)
                self.assertTrue(path.is_file(), str(path))
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertIn(image.mode, {"RGB", "RGBA"})

    def test_all_batch3_render_without_rescaling(self):
        dummy = Image.new("RGBA", (280, 140), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in BATCH3:
                with self.subTest(category=category):
                    image = template_cards.render(category, self.payload)
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertEqual(image.mode, "RGB")

    def test_intervention_medicale_does_not_require_confirmed_injury(self):
        payload = dict(self.payload)
        payload.pop("injury_status", None)
        payload.pop("reason", None)
        payload["player"] = ""
        image = template_cards.render("intervention_medicale", payload)
        self.assertEqual(image.size, (1122, 1402))

    def test_match_interrompu_full_still_requires_verified_reason(self):
        self.assertEqual(
            events.template_path("match_interrompu", self.payload).name,
            "match_interrompu_full.png",
        )
        payload = dict(self.payload)
        payload["reason"] = ""
        payload["detail"] = ""
        payload["interruption_reason"] = ""
        with self.assertRaises(ValueError):
            template_cards.render("match_interrompu_full", payload)

    def test_no_score_is_invented_on_match_suspendu(self):
        payload = dict(self.payload)
        payload.pop("score", None)
        blank = events.background("match_suspendu", payload)
        rendered = events.render_event("match_suspendu", payload)
        for key in ("score_home", "score_away"):
            box = events.SPECS["match_suspendu"][key]
            self.assertEqual(blank.crop(box).tobytes(), rendered.crop(box).tobytes())

    def test_static_header_remains_untouched(self):
        dummy = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in BATCH3:
                with self.subTest(category=category):
                    blank = events.background(category, self.payload)
                    rendered = events.render_event(category, self.payload)
                    self.assertEqual(
                        blank.crop((0, 0, 1122, 280)).tobytes(),
                        rendered.crop((0, 0, 1122, 280)).tobytes(),
                    )

    def test_five_new_backgrounds_are_visually_distinct(self):
        images = [events.background(cat, self.payload) for cat in BATCH3]
        for i in range(len(images)):
            for j in range(i + 1, len(images)):
                with self.subTest(a=BATCH3[i], b=BATCH3[j]):
                    self.assertIsNotNone(ImageChops.difference(images[i], images[j]).getbbox())


if __name__ == "__main__":
    unittest.main()
