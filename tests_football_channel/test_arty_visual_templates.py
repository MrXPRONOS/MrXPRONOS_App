"""Premium Arty graphic validation; offline, no Telegram or sports API required."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import arty_football_templates as a
import template_cards as cards
import programme_styles

BG = (18,26,36)

class ArtyVisualTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "home":"Borussia Mönchengladbach", "away":"Atlético de Madrid",
            "home_logo":"https://fake/home.png","away_logo":"https://fake/away.png",
            "league":"UEFA Champions League","competition":"UEFA Champions League",
            "time":"20h45","minute":45,"score":"1-1","scores":(1,1),
            "source":"ESPN Live","goal":{"player":"Exemple de buteur","minute_text":"45'"},
            "question":"Quel joueur a remporté le titre de meilleur buteur ?",
            "headline":"35 buts inscrits en saison",
            "summary":"Analyse basée sur des données vérifiées et un championnat bien identifié.",
            "options":["Équipe domicile","Match nul","Équipe extérieure","Autre réponse"],
            "lines":["35 buts","20 matches","15 points","5 victoires"],
            "home_players":[f"Titulaire domicile {i}" for i in range(1,12)],
            "away_players":[f"Titulaire extérieur {i}" for i in range(1,12)],
        }

    def test_all_blank_assets_exist_and_render_portrait(self):
        self.assertEqual(len(a.SUPPORTED),12)
        for category in a.SUPPORTED:
            with self.subTest(category=category):
                file=a.blank_path(category)
                self.assertTrue(file.is_file(),str(file))
                with Image.open(file) as im:
                    self.assertEqual(im.size,(1080,1350))
                    self.assertEqual(im.mode,"RGB")

    def test_render_all_categories_without_redrawing_frames(self):
        sample=Image.new("RGBA",(350,150),(255,255,255,255))
        with patch.object(programme_styles,"load_logo",return_value=sample):
            for category in a.SUPPORTED:
                with self.subTest(category=category):
                    blank=a.background(category)
                    completed=cards.render(category,self.payload)
                    self.assertEqual(completed.size,(1080,1350))
                    self.assertEqual(completed.mode,"RGB")
                    # Dynamic elements must not touch the structural frame/footer.
                    self.assertEqual(blank.crop((5,5,75,60)).tobytes(),
                                     completed.crop((5,5,75,60)).tobytes())
                    self.assertEqual(blank.crop((0,1312,1080,1350)).tobytes(),
                                     completed.crop((0,1312,1080,1350)).tobytes())
                    self.assertIsNotNone(ImageChops.difference(blank,completed).getbbox())

    def test_composition_11_players_required(self):
        sample=Image.new("RGBA",(300,150),(255,255,255,255))
        with patch.object(programme_styles,"load_logo",return_value=sample):
            image=cards.render("composition",self.payload)
            self.assertEqual(image.size,(1080,1350))
            wrong=dict(self.payload,home_players=self.payload["home_players"][:-1])
            with self.assertRaises(ValueError):
                cards.render("composition",wrong)

    def test_no_legacy_dark_patch_on_composition(self):
        import inspect
        source=inspect.getsource(a.overlay)
        self.assertNotIn("_local_dark_patch",source)
        self.assertNotIn("draw.rounded_rectangle",source)

    def test_unknown_category_is_rejected(self):
        with self.assertRaises(ValueError):
            cards.render("category_not_supported",self.payload)


if __name__=="__main__":
    unittest.main()
