"""Offline validation for the fifth audited 1122x1402 Actu Foot event batch."""
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


BATCH5 = (
    "fin_1re_mi_temps",
    "debut_2e_mi_temps",
    "fin_temps_reglementaire",
    "prolongation",
    "mi_temps_prolongation",
)


class ActuFootEventBatch5Tests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "home": "Real Madrid",
            "away": "FC Barcelona",
            "home_logo": "https://fake/home.png",
            "away_logo": "https://fake/away.png",
            "competition": "LaLiga",
            "score": "2-2",
            "minute": "90",
            "source": "ESPN Live",
            "status": "Phase du match confirmée",
            "info": "Mise à jour en direct.",
        }

    def test_five_batch5_backgrounds_build_at_native_size(self):
        for category in BATCH5:
            with self.subTest(category=category):
                image = events.background(category, self.payload)
                self.assertEqual(image.size, (1122, 1402))
                self.assertEqual(image.mode, "RGB")

    def test_all_batch5_render_without_rescaling(self):
        dummy = Image.new("RGBA", (280, 140), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in BATCH5:
                with self.subTest(category=category):
                    image = template_cards.render(category, self.payload)
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertEqual(image.mode, "RGB")

    def test_unicode_phase_aliases_are_supported(self):
        aliases = {
            "fin_de_la_1re_mi_temps": "fin_1re_mi_temps.png",
            "début_de_la_2e_mi_temps": "debut_2e_mi_temps.png",
            "fin_du_temps_réglementaire": "fin_temps_reglementaire.png",
            "mi_temps_de_la_prolongation": "mi_temps_prolongation.png",
        }
        for alias, filename in aliases.items():
            with self.subTest(alias=alias):
                self.assertEqual(events.template_path(alias, self.payload).name, filename)
                self.assertEqual(events.background(alias, self.payload).size, (1122, 1402))

    def test_end_of_regulation_is_not_a_final_result_layout(self):
        spec = events.SPECS["fin_temps_reglementaire"]
        self.assertIn("status", spec)
        self.assertNotIn("winner", spec)
        self.assertNotIn("verdict", spec)
        self.assertNotIn("result", spec)

    def test_missing_score_stays_blank(self):
        payload = dict(self.payload)
        payload.pop("score", None)
        blank = events.background("fin_1re_mi_temps", payload)
        rendered = events.render_event("fin_1re_mi_temps", payload)
        for key in ("score_home", "score_away"):
            box = events.SPECS["fin_1re_mi_temps"][key]
            self.assertEqual(blank.crop(box).tobytes(), rendered.crop(box).tobytes())

    def test_phase_backgrounds_are_visually_distinct(self):
        images = [events.background(cat, self.payload) for cat in BATCH5]
        for i in range(len(images)):
            for j in range(i + 1, len(images)):
                with self.subTest(a=BATCH5[i], b=BATCH5[j]):
                    self.assertIsNotNone(ImageChops.difference(images[i], images[j]).getbbox())

    def test_header_is_static_and_not_overwritten(self):
        dummy = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in BATCH5:
                blank = events.background(category, self.payload)
                rendered = events.render_event(category, self.payload)
                self.assertEqual(
                    blank.crop((0, 0, 1122, 280)).tobytes(),
                    rendered.crop((0, 0, 1122, 280)).tobytes(),
                )


if __name__ == "__main__":
    unittest.main()
