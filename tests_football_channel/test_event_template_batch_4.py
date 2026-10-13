"""Offline validation for the fourth audited 1122x1402 Actu Foot event batch."""
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


BATCH4 = (
    "match_interrompu_unknown",
    "match_reporte",
    "match_annule",
    "reprise_match",
    "temps_additionnel",
)


class ActuFootEventBatch4Tests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "home": "Manchester City",
            "away": "Liverpool",
            "home_logo": "https://fake/home.png",
            "away_logo": "https://fake/away.png",
            "competition": "Premier League",
            "score": "2-2",
            "minute": "90",
            "source": "ESPN Live",
            "status": "Information confirmée par la source live.",
            "info": "Mise à jour officielle disponible.",
            "new_date": "18 octobre 2026",
            "new_time": "20:00",
            "reason": "Conditions météorologiques",
            "added_time": "7",
        }

    def test_five_batch4_assets_exist_at_native_size(self):
        for category in BATCH4:
            with self.subTest(category=category):
                path = events.template_path(category, self.payload)
                self.assertTrue(path.is_file(), str(path))
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertIn(image.mode, {"RGB", "RGBA"})

    def test_all_batch4_render_without_rescaling(self):
        dummy = Image.new("RGBA", (280, 140), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in BATCH4:
                with self.subTest(category=category):
                    image = template_cards.render(category, self.payload)
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertEqual(image.mode, "RGB")

    def test_match_interrompu_alias_selects_full_or_unknown_variant(self):
        self.assertEqual(
            events.template_path("match_interrompu", self.payload).name,
            "match_interrompu_full.png",
        )
        unknown = dict(self.payload)
        unknown["reason"] = ""
        unknown["detail"] = ""
        unknown["interruption_reason"] = ""
        self.assertEqual(
            events.template_path("match_interrompu", unknown).name,
            "match_interrompu_unknown.png",
        )
        image = template_cards.render("match_interrompu", unknown)
        self.assertEqual(image.size, (1122, 1402))

    def test_unknown_interruption_has_no_reason_slot(self):
        self.assertNotIn("reason", events.SPECS["match_interrompu_unknown"])
        self.assertIn("status", events.SPECS["match_interrompu_unknown"])

    def test_reported_match_does_not_invent_new_schedule(self):
        payload = dict(self.payload)
        payload["new_date"] = ""
        payload["new_time"] = ""
        payload["rescheduled_date"] = ""
        payload["rescheduled_time"] = ""
        blank = events.background("match_reporte", payload)
        rendered = events.render_event("match_reporte", payload)
        for key in ("new_date", "new_time"):
            box = events.SPECS["match_reporte"][key]
            self.assertEqual(blank.crop(box).tobytes(), rendered.crop(box).tobytes())

    def test_added_time_formats_integer_as_plus_minutes(self):
        payload = dict(self.payload)
        payload["added_time"] = "7"
        blank = events.background("temps_additionnel", payload)
        rendered = events.render_event("temps_additionnel", payload)
        box = events.SPECS["temps_additionnel"]["added_time"]
        self.assertIsNotNone(ImageChops.difference(blank.crop(box), rendered.crop(box)).getbbox())

    def test_unicode_aliases_are_supported(self):
        self.assertEqual(events.template_path("match_reporté", self.payload).name, "match_reporte.png")
        self.assertEqual(events.template_path("match_annulé", self.payload).name, "match_annule.png")
        self.assertEqual(events.template_path("reprise_du_match", self.payload).name, "reprise_match.png")

    def test_new_backgrounds_are_visually_distinct(self):
        images = [events.background(cat, self.payload) for cat in BATCH4]
        for i in range(len(images)):
            for j in range(i + 1, len(images)):
                with self.subTest(a=BATCH4[i], b=BATCH4[j]):
                    self.assertIsNotNone(ImageChops.difference(images[i], images[j]).getbbox())


if __name__ == "__main__":
    unittest.main()
