import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generic_football_banners as banners
import template_cards


class GenericBannerTests(unittest.TestCase):
    def setUp(self):
        self.match = {
            "home": "Manchester United",
            "away": "Paris Saint-Germain",
            "home_logo": "mock://home",
            "away_logo": "mock://away",
            "league": "UEFA Champions League",
            "competition": "UEFA Champions League",
            "score": "2-1",
            "minute": 67,
            "source": "ESPN",
            "goal": {"player": "Kylian Mbappé", "assists": ["Joueur Exemple"]},
        }
        self.club = {
            "team": "Manchester United",
            "team_logo": "mock://club",
            "league": "Premier League",
            "source": "ESPN",
            "player": "Joueur Exemple",
            "reason": "Information confirmée",
            "players": [f"Joueur {i}" for i in range(1, 12)],
        }

    @staticmethod
    def fake_logo(_url, max_px):
        im = Image.new("RGBA", (max_px, max_px), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse((2, 2, max_px - 3, max_px - 3), fill=(30, 70, 120, 255), outline=(245, 199, 91, 255), width=4)
        return im

    def test_source_templates_are_native_1280x500(self):
        for kind in ("match", "club", "general"):
            with self.subTest(kind=kind):
                self.assertEqual(banners.template(kind).size, (1280, 500))

    def test_no_runtime_rectangles_are_drawn(self):
        source = inspect.getsource(banners)
        self.assertNotIn("rounded_rectangle", source)
        self.assertNotIn("draw.rectangle", source)

    def test_match_event_families_render_horizontal(self):
        categories = [
            "kickoff", "goal", "mi_temps", "score_update", "poteau",
            "occasion_manquee", "arret_decisif", "carton_jaune_full",
            "carton_jaune_unknown", "carton_rouge_full", "carton_rouge_unknown",
            "remplacement_full", "remplacement_entrant", "remplacement_sortant",
            "intervention_medicale", "blessure_confirmee", "retour_au_jeu",
            "match_suspendu", "match_interrompu_full", "match_interrompu_unknown",
            "match_reporte", "match_annule", "reprise_match", "temps_additionnel",
            "fin_1re_mi_temps", "debut_2e_mi_temps", "fin_temps_reglementaire",
            "prolongation", "mi_temps_prolongation", "tirs_au_but",
            "tir_au_but_marque", "tir_au_but_manque", "fin_tirs_au_but",
            "score_live_two_logos", "score_live_one_logo", "score_live_no_logos",
            "score_live_no_minute", "but_full", "but_scorer_only",
            "reaction", "community_vote",
        ]
        with patch("programme_styles.load_logo", side_effect=self.fake_logo):
            for category in categories:
                with self.subTest(category=category):
                    image = template_cards.render(category, dict(self.match))
                    self.assertEqual(image.size, (1280, 500))

    def test_club_families_render_horizontal(self):
        categories = [
            "composition_probable_full", "composition_probable_partial",
            "changement_composition", "absence_confirmee", "retour_groupe",
        ]
        with patch("programme_styles.load_logo", side_effect=self.fake_logo):
            for category in categories:
                with self.subTest(category=category):
                    image = template_cards.render(category, dict(self.club))
                    self.assertEqual(image.size, (1280, 500))

    def test_general_families_render_horizontal(self):
        payloads = {
            "statistique_avancee": {"headline": "Arsenal domine les corners", "league": "Premier League"},
            "quiz": {"question": "Quel club a remporté le plus de titres ?", "league": "Football"},
            "debat": {"headline": "Le débat du jour", "source": "Foot Mercato"},
            "sondage": {"question": "Quel championnat préférez-vous ?"},
        }
        for category, payload in payloads.items():
            with self.subTest(category=category):
                image = template_cards.render(category, payload)
                self.assertEqual(image.size, (1280, 500))

    def test_four_core_templates_remain_dedicated(self):
        from generic_football_banners import banner_kind
        for category in ("programme", "avant_match", "resultat", "composition", "flash", "viral"):
            self.assertIsNone(banner_kind(category, self.match))


if __name__ == "__main__":
    unittest.main()
