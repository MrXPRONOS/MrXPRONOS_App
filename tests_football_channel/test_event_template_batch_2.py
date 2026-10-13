"""Offline validation for the second audited 1122x1402 Actu Foot event batch."""
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


BATCH2 = (
    "carton_rouge_full",
    "carton_rouge_unknown",
    "remplacement_full",
    "remplacement_entrant",
    "remplacement_sortant",
)


class ActuFootEventBatch2Tests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "home": "Olympique de Marseille",
            "away": "Paris Saint-Germain",
            "home_logo": "https://fake/home.png",
            "away_logo": "https://fake/away.png",
            "competition": "Ligue 1",
            "score": "1-2",
            "minute": "73",
            "source": "ESPN Live",
            "player": "Joueur Expulsé Exemple",
            "reason": "Faute empêchant une occasion manifeste",
            "entrant": "Joueur Entrant Exemple",
            "sortant": "Joueur Sortant Exemple",
        }

    def test_exactly_five_batch2_assets_exist_at_native_size(self):
        for category in BATCH2:
            with self.subTest(category=category):
                path = events.template_path(category, self.payload)
                self.assertTrue(path.is_file(), str(path))
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertIn(image.mode, {"RGB", "RGBA"})

    def test_all_batch2_render_without_rescaling(self):
        dummy = Image.new("RGBA", (300, 150), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in BATCH2:
                with self.subTest(category=category):
                    image = template_cards.render(category, self.payload)
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertEqual(image.mode, "RGB")

    def test_red_card_alias_selects_full_or_unknown(self):
        dummy = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            full = template_cards.render("carton_rouge", self.payload)
            unknown_payload = dict(self.payload)
            unknown_payload["player"] = ""
            unknown_payload["card_player"] = ""
            unknown_payload["booked_player"] = ""
            unknown_payload["sent_off_player"] = ""
            unknown = template_cards.render("carton_rouge", unknown_payload)
            self.assertEqual(
                events.template_path("carton_rouge", self.payload).name,
                "carton_rouge_full.png",
            )
            self.assertEqual(
                events.template_path("carton_rouge", unknown_payload).name,
                "carton_rouge_unknown.png",
            )
            self.assertIsNotNone(ImageChops.difference(full, unknown).getbbox())

    def test_replacement_alias_selects_three_real_layouts(self):
        both = dict(self.payload)
        incoming_only = dict(self.payload, sortant="")
        outgoing_only = dict(self.payload, entrant="")
        self.assertEqual(
            events.template_path("remplacement", both).name,
            "remplacement_full.png",
        )
        self.assertEqual(
            events.template_path("remplacement", incoming_only).name,
            "remplacement_entrant.png",
        )
        self.assertEqual(
            events.template_path("remplacement", outgoing_only).name,
            "remplacement_sortant.png",
        )

    def test_replacement_without_verified_player_is_rejected(self):
        payload = dict(self.payload, entrant="", sortant="")
        payload["incoming"] = ""
        payload["outgoing"] = ""
        payload["player_in"] = ""
        payload["player_out"] = ""
        with self.assertRaises(ValueError):
            template_cards.render("remplacement", payload)

    def test_partial_replacement_templates_do_not_have_second_player_slot(self):
        self.assertIn("player", events.SPECS["remplacement_entrant"])
        self.assertNotIn("sortant", events.SPECS["remplacement_entrant"])
        self.assertIn("player", events.SPECS["remplacement_sortant"])
        self.assertNotIn("entrant", events.SPECS["remplacement_sortant"])

    def test_missing_score_stays_blank_on_red_card(self):
        payload = dict(self.payload)
        payload.pop("score", None)
        blank = events.background("carton_rouge_full", payload)
        rendered = events.render_event("carton_rouge_full", payload)
        for key in ("score_home", "score_away"):
            box = events.SPECS["carton_rouge_full"][key]
            self.assertEqual(blank.crop(box).tobytes(), rendered.crop(box).tobytes())


if __name__ == "__main__":
    unittest.main()
