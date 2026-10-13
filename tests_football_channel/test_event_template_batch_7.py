"""Offline validation for the seventh audited 1122x1402 Actu Foot event batch."""
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


BATCH7 = (
    "composition_probable_partial",
    "changement_composition",
    "absence_confirmee",
    "retour_groupe",
    "score_live_two_logos",
)


class ActuFootEventBatch7Tests(unittest.TestCase):
    def setUp(self):
        self.players10 = [f"Joueur {i}" for i in range(1, 11)]
        self.players11 = [f"Joueur {i}" for i in range(1, 12)]
        self.payload = {
            "home": "Arsenal",
            "away": "Chelsea",
            "team": "Arsenal",
            "team_logo": "https://fake/team.png",
            "home_logo": "https://fake/home.png",
            "away_logo": "https://fake/away.png",
            "competition": "Premier League",
            "score": "2-1",
            "minute": "73",
            "source": "ESPN Live",
            "status": "Information confirmée",
            "info": "Mise à jour en direct.",
            "players": self.players10,
            "formation": "4-3-3",
            "entrant": "Joueur Entrant",
            "sortant": "Joueur Sortant",
            "player": "Joueur Exemple",
            "reason": "Choix de l'entraîneur",
        }

    def test_five_batch7_backgrounds_build_at_native_size(self):
        for category in BATCH7:
            with self.subTest(category=category):
                image = events.background(category, self.payload)
                self.assertEqual(image.size, (1122, 1402))
                self.assertEqual(image.mode, "RGB")

    def test_all_batch7_render_without_rescaling(self):
        dummy = Image.new("RGBA", (280, 140), (255, 255, 255, 255))
        with patch.object(programme_styles, "load_logo", return_value=dummy):
            for category in BATCH7:
                with self.subTest(category=category):
                    image = template_cards.render(category, self.payload)
                    self.assertEqual(image.size, (1122, 1402))
                    self.assertEqual(image.mode, "RGB")

    def test_probable_composition_alias_selects_partial_or_full(self):
        partial = dict(self.payload, players=self.players10)
        full = dict(self.payload, players=self.players11)
        self.assertEqual(
            events.template_path("composition_probable", partial).name,
            "composition_probable_partial.png",
        )
        self.assertEqual(
            events.template_path("composition_probable", full).name,
            "composition_probable_full.png",
        )

    def test_partial_composition_has_no_individual_empty_player_slots(self):
        spec = events.SPECS["composition_probable_partial"]
        self.assertIn("players_area", spec)
        self.assertFalse(any(k.startswith("p") and k[1:].isdigit() for k in spec))
        payload = dict(self.payload, players=["Seul Joueur Vérifié"])
        image = template_cards.render("composition_probable", payload)
        self.assertEqual(image.size, (1122, 1402))

    def test_probable_composition_without_verified_player_is_rejected(self):
        payload = dict(self.payload, players=[])
        with self.assertRaises(ValueError):
            template_cards.render("composition_probable", payload)

    def test_lineup_change_requires_incoming_and_outgoing_players(self):
        payload = dict(self.payload, entrant="", incoming="", player_in="")
        with self.assertRaises(ValueError):
            template_cards.render("changement_composition", payload)
        payload = dict(self.payload, sortant="", outgoing="", player_out="")
        with self.assertRaises(ValueError):
            template_cards.render("changement_composition", payload)

    def test_absence_and_return_require_identified_player(self):
        absence = dict(self.payload, player="", absent_player="")
        with self.assertRaises(ValueError):
            template_cards.render("absence_confirmee", absence)
        retour = dict(self.payload, player="", returning_player="")
        with self.assertRaises(ValueError):
            template_cards.render("retour_groupe", retour)

    def test_score_live_two_logos_requires_both_logos_score_and_minute(self):
        no_home_logo = dict(self.payload, home_logo="")
        with self.assertRaises(ValueError):
            template_cards.render("score_live_two_logos", no_home_logo)

        no_score = dict(self.payload)
        no_score.pop("score", None)
        no_score.pop("scores", None)
        no_score.pop("home_score", None)
        no_score.pop("away_score", None)
        with self.assertRaises(ValueError):
            template_cards.render("score_live_two_logos", no_score)

        no_minute = dict(self.payload, minute="", time="")
        with self.assertRaises(ValueError):
            template_cards.render("score_live_two_logos", no_minute)

    def test_score_live_two_logo_direct_variant_still_requires_both_logos(self):
        self.assertEqual(
            events.template_path("score_live_confirmé", self.payload).name,
            "score_live_two_logos.png",
        )
        missing = dict(self.payload, away_logo="")
        with self.assertRaises(ValueError):
            template_cards.render("score_live_two_logos", missing)
        # Since batch 8, the generic alias routes one-logo data to its own
        # adapted layout instead of rejecting it.
        self.assertEqual(
            events.template_path("score_live_confirmé", missing).name,
            "score_live_one_logo.png",
        )

    def test_batch7_backgrounds_are_visually_distinct(self):
        images = [events.background(cat, self.payload) for cat in BATCH7]
        for i in range(len(images)):
            for j in range(i + 1, len(images)):
                with self.subTest(a=BATCH7[i], b=BATCH7[j]):
                    self.assertIsNotNone(ImageChops.difference(images[i], images[j]).getbbox())


if __name__ == "__main__":
    unittest.main()
