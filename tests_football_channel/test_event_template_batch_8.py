"""Offline validation for the eighth audited 1122x1402 Actu Foot event batch."""
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


BATCH8 = (
    "score_live_one_logo",
    "score_live_no_logos",
    "score_live_no_minute",
    "but_full",
    "but_scorer_only",
)


class ActuFootEventBatch8Tests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "home": "Arsenal",
            "away": "Chelsea",
            "home_logo": "https://fake/home.png",
            "away_logo": "https://fake/away.png",
            "competition": "Premier League",
            "score": "2-1",
            "minute": "67",
            "source": "ESPN Live",
            "status": "LIVE",
            "info": "Action confirmée par la source live.",
            "scorer": "Buteur Exemple",
            "assist": "Passeur Exemple",
        }

    def test_five_batch8_backgrounds_build_at_native_size(self):
        for category in BATCH8:
            with self.subTest(category=category):
                image = events.background(category, self.payload)
                self.assertEqual(image.size, (1122, 1402))
                self.assertEqual(image.mode, "RGB")

    def test_all_batch8_render_without_rescaling(self):
        dummy = Image.new("RGBA", (280, 140), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            payloads = {
                "score_live_one_logo": dict(self.payload, away_logo=""),
                "score_live_no_logos": dict(self.payload, home_logo="", away_logo=""),
                "score_live_no_minute": dict(self.payload, minute="", time=""),
                "but_full": dict(self.payload),
                "but_scorer_only": dict(self.payload, assist=""),
            }
            for category in BATCH8:
                with self.subTest(category=category):
                    image = template_cards.render(category, payloads[category])
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertEqual(image.mode, "RGB")

    def test_score_live_alias_selects_all_four_data_layouts(self):
        two = dict(self.payload)
        one = dict(self.payload, away_logo="")
        none = dict(self.payload, home_logo="", away_logo="")
        no_minute = dict(self.payload, minute="", time="")

        self.assertEqual(
            events.template_path("score_live_confirme", two).name,
            "score_live_two_logos.png",
        )
        self.assertEqual(
            events.template_path("score_live_confirme", one).name,
            "score_live_one_logo.png",
        )
        self.assertEqual(
            events.template_path("score_live_confirme", none).name,
            "score_live_no_logos.png",
        )
        self.assertEqual(
            events.template_path("score_live_confirme", no_minute).name,
            "score_live_no_minute.png",
        )

    def test_one_logo_variant_does_not_draw_an_empty_second_logo(self):
        payload = dict(self.payload, away_logo="")
        dummy = Image.new("RGBA", (220, 120), (255, 255, 255, 255))
        blank = events.background("score_live_one_logo", payload)
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            rendered = events.render_event("score_live_one_logo", payload)

        spec = events.SPECS["score_live_one_logo"]
        self.assertIsNotNone(
            ImageChops.difference(
                blank.crop(spec["logo_home"]),
                rendered.crop(spec["logo_home"]),
            ).getbbox()
        )
        self.assertEqual(
            blank.crop(spec["logo_away"]).tobytes(),
            rendered.crop(spec["logo_away"]).tobytes(),
        )

    def test_no_logo_layout_has_no_logo_boxes(self):
        spec = events.SPECS["score_live_no_logos"]
        self.assertNotIn("logo_home", spec)
        self.assertNotIn("logo_away", spec)

    def test_no_minute_layout_has_no_minute_box(self):
        spec = events.SPECS["score_live_no_minute"]
        self.assertNotIn("minute", spec)
        payload = dict(self.payload, minute="", time="")
        image = template_cards.render("score_live_no_minute", payload)
        self.assertEqual(image.size, (1122, 1402))

    def test_direct_score_live_variants_enforce_their_data_shape(self):
        with self.assertRaises(ValueError):
            template_cards.render("score_live_one_logo", self.payload)

        with self.assertRaises(ValueError):
            template_cards.render(
                "score_live_no_logos",
                dict(self.payload, home_logo="https://fake/home.png", away_logo=""),
            )

        with self.assertRaises(ValueError):
            template_cards.render("score_live_no_minute", self.payload)

    def test_goal_alias_selects_full_or_scorer_only(self):
        full = dict(self.payload)
        scorer_only = dict(self.payload, assist="", assister="", passeur="", assistant="")

        self.assertEqual(events.template_path("but", full).name, "but_full.png")
        self.assertEqual(
            events.template_path("but", scorer_only).name,
            "but_scorer_only.png",
        )

    def test_goal_full_requires_assist_and_scorer_only_has_no_assist_slot(self):
        scorer_only = dict(self.payload, assist="", assister="", passeur="", assistant="")
        with self.assertRaises(ValueError):
            template_cards.render("but_full", scorer_only)

        self.assertNotIn("assist", events.SPECS["but_scorer_only"])
        with self.assertRaises(ValueError):
            template_cards.render("but_scorer_only", self.payload)

    def test_goal_alias_rejects_unknown_scorer_until_unknown_variant_exists(self):
        payload = dict(
            self.payload,
            scorer="",
            goal_scorer="",
            buteur="",
            player="",
            assist="",
        )
        with self.assertRaises(ValueError):
            template_cards.render("but", payload)

    def test_batch8_backgrounds_are_visually_distinct(self):
        payloads = {
            "score_live_one_logo": dict(self.payload, away_logo=""),
            "score_live_no_logos": dict(self.payload, home_logo="", away_logo=""),
            "score_live_no_minute": dict(self.payload, minute="", time=""),
            "but_full": dict(self.payload),
            "but_scorer_only": dict(self.payload, assist=""),
        }
        images = [events.background(cat, payloads[cat]) for cat in BATCH8]
        for i in range(len(images)):
            for j in range(i + 1, len(images)):
                with self.subTest(a=BATCH8[i], b=BATCH8[j]):
                    self.assertIsNotNone(
                        ImageChops.difference(images[i], images[j]).getbbox()
                    )


if __name__ == "__main__":
    unittest.main()
