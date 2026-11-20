import importlib.util
from pathlib import Path
from unittest import TestCase, mock
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT))
spec = importlib.util.spec_from_file_location("individual_series", SCRIPT / "publish_individual_series_bot.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class IndividualSeriesPublishTest(TestCase):
    def test_season_and_expected_episodes(self):
        self.assertEqual(mod.parse_season("BLACK DOVES Saison 1 VF"), 1)
        self.assertEqual(mod.parse_season("S03 | VF"), 3)
        self.assertIsNone(mod.parse_season("Sans numéro"))
        self.assertEqual(mod.parse_expected("Saison 2 : 10 épisodes"), 10)
        self.assertIsNone(mod.parse_expected("Saison complète"))

    def test_season_counts_and_invalid(self):
        self.assertEqual(mod.parse_season_counts("-1001234567890:3 -1009876543210:1"),
                         {"-1001234567890":3, "-1009876543210":1})
        with self.assertRaises(ValueError):
            mod.parse_season_counts("-1001234567890:99")

    def test_buttons(self):
        token = "abcdefghijklmnopqrstuvwx"
        buttons = mod.keyboard(token,"https://t.me/+abcdefghijkL","https://t.me/addlist/ABCDEFGHIJK")
        self.assertEqual([row[0]["style"] for row in buttons["inline_keyboard"]],
                         ["success","danger","primary"])
        self.assertIn("sr_"+token,buttons["inline_keyboard"][0][0]["url"])

    def test_catalogue_requires_all_seasons_and_episodes(self):
        def query(sql, params):
            if "expected_seasons" in sql:
                return [{"expected_seasons":2}]
            if "cine_series_seasons" in sql:
                return [{"season":1,"expected_episodes":2},{"season":2,"expected_episodes":1}]
            if "cine_series_posters" in sql:
                return [{"season":1,"source_message_id":4},{"season":2,"source_message_id":20}]
            if "cine_series_episodes" in sql:
                return [{"season":1,"episode":1,"source_message_id":7},
                        {"season":1,"episode":2,"source_message_id":8},
                        {"season":2,"episode":1,"source_message_id":21}]
            raise AssertionError(sql)
        with mock.patch.object(mod,"d1",side_effect=query):
            result = mod.catalogue_complete("-1001234567890")
        self.assertTrue(result["ready"])
        self.assertEqual(result["main_poster"],4)
        with mock.patch.object(mod,"d1",side_effect=lambda sql,p:
             [{"expected_seasons":3}] if "expected_seasons" in sql else query(sql,p)):
            result = mod.catalogue_complete("-1001234567890")
        self.assertFalse(result["ready"])
