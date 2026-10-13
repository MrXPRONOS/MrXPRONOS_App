"""Offline validation for the sixth audited 1122x1402 Actu Foot event batch."""
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


BATCH6 = (
    "tirs_au_but",
    "tir_au_but_marque",
    "tir_au_but_manque",
    "fin_tirs_au_but",
    "composition_probable_full",
)


class ActuFootEventBatch6Tests(unittest.TestCase):
    def setUp(self):
        self.players = [
            "Gardien Exemple",
            "Défenseur Gauche",
            "Défenseur Centre A",
            "Défenseur Centre B",
            "Défenseur Droit",
            "Milieu Défensif",
            "Milieu Relayeur",
            "Milieu Créatif",
            "Ailier Gauche",
            "Avant Centre",
            "Ailier Droit",
        ]
        self.payload = {
            "home": "Real Madrid",
            "away": "Manchester City",
            "home_logo": "https://fake/home.png",
            "away_logo": "https://fake/away.png",
            "competition": "UEFA Champions League",
            "score": "1-1",
            "shootout_score": "4-3",
            "source": "ESPN Live",
            "player": "Joueur Exemple",
            "player_team": "Real Madrid",
            "winner": "Real Madrid",
            "team": "Real Madrid",
            "team_logo": "https://fake/team.png",
            "players": self.players,
            "formation": "4-3-3",
            "coach": "Coach Exemple",
            "info": "Séance en cours.",
        }

    def test_five_batch6_backgrounds_build_at_native_size(self):
        for category in BATCH6:
            with self.subTest(category=category):
                image = events.background(category, self.payload)
                self.assertEqual(image.size, (1122, 1402))
                self.assertEqual(image.mode, "RGB")

    def test_all_batch6_render_without_rescaling(self):
        dummy = Image.new("RGBA", (280, 140), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in BATCH6:
                with self.subTest(category=category):
                    image = template_cards.render(category, self.payload)
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertEqual(image.mode, "RGB")

    def test_shootout_score_is_separate_from_match_score(self):
        payload = dict(self.payload)
        payload.pop("score", None)
        payload.pop("scores", None)
        payload.pop("home_score", None)
        payload.pop("away_score", None)
        blank = events.background("tirs_au_but", payload)
        rendered = events.render_event("tirs_au_but", payload)
        spec = events.SPECS["tirs_au_but"]

        for key in ("score_home", "score_away"):
            self.assertEqual(
                blank.crop(spec[key]).tobytes(),
                rendered.crop(spec[key]).tobytes(),
            )
        for key in ("shootout_home", "shootout_away"):
            self.assertIsNotNone(
                ImageChops.difference(
                    blank.crop(spec[key]),
                    rendered.crop(spec[key]),
                ).getbbox()
            )

    def test_shootout_score_is_not_invented(self):
        payload = dict(self.payload)
        payload.pop("shootout_score", None)
        payload.pop("shootout_scores", None)
        payload.pop("shootout_home", None)
        payload.pop("shootout_away", None)
        payload.pop("penalty_score", None)
        payload.pop("penalty_scores", None)
        blank = events.background("tir_au_but_marque", payload)
        rendered = events.render_event("tir_au_but_marque", payload)
        spec = events.SPECS["tir_au_but_marque"]
        for key in ("shootout_home", "shootout_away"):
            self.assertEqual(blank.crop(spec[key]).tobytes(), rendered.crop(spec[key]).tobytes())

    def test_full_probable_xi_requires_exact_minimum_of_eleven_verified_players(self):
        payload = dict(self.payload)
        payload["players"] = self.players[:10]
        with self.assertRaises(ValueError):
            template_cards.render("composition_probable_full", payload)
        # Since batch 7, the generic alias correctly routes 1–10 verified
        # players to the dedicated partial-composition layout.
        self.assertEqual(
            events.template_path("composition_probable", payload).name,
            "composition_probable_partial.png",
        )

    def test_full_probable_xi_uses_eleven_independent_slots(self):
        spec = events.SPECS["composition_probable_full"]
        for idx in range(1, 12):
            self.assertIn(f"p{idx}", spec)
        self.assertEqual(len([k for k in spec if k.startswith("p") and k[1:].isdigit()]), 11)

    def test_unicode_aliases_are_supported(self):
        aliases = {
            "tir_au_but_marqué": "tir_au_but_marque.png",
            "tir_au_but_manqué": "tir_au_but_manque.png",
            "fin_des_tirs_au_but": "fin_tirs_au_but.png",
            "composition_probable": "composition_probable_full.png",
        }
        for alias, filename in aliases.items():
            with self.subTest(alias=alias):
                self.assertEqual(events.template_path(alias, self.payload).name, filename)

    def test_batch6_backgrounds_are_visually_distinct(self):
        images = [events.background(cat, self.payload) for cat in BATCH6]
        for i in range(len(images)):
            for j in range(i + 1, len(images)):
                with self.subTest(a=BATCH6[i], b=BATCH6[j]):
                    self.assertIsNotNone(ImageChops.difference(images[i], images[j]).getbbox())


if __name__ == "__main__":
    unittest.main()
