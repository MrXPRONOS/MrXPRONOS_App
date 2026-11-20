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


    def test_sync_can_index_pinned_poster_without_radar_identity(self):
        class Publisher:
            def __init__(self):
                self.calls=[]
            def call(self, method, params):
                self.calls.append((method,params))
                if method=="getChat":
                    return {"type":"channel","id":-1001234567890,"title":"Une série",
                            "pinned_message":{"message_id":101,"photo":[{"file_id":"photo"}],
                                              "caption":"Saison 1 : 6 épisodes"}}
                if method=="getChatMember":
                    self.assert_self=False
                    return {"status":"administrator"}
                raise AssertionError(method)
        bot=Publisher()
        calls=[]
        with mock.patch.object(mod,"d1",side_effect=lambda sql,params:calls.append((sql,params)) or []):
            report=mod.sync_channel(bot,777,None,"-1001234567890",True)
        self.assertEqual(report["latest_pin_season"],1)
        self.assertIsNone(report["radar_admin"])
        self.assertEqual(len([x for x in bot.calls if x[0]=="getChatMember"]),1)
        self.assertTrue(any("cine_series_channels" in q and p[3]=="unchecked" for q,p in calls))
        self.assertTrue(any("cine_series_posters" in q and p[2]==101 for q,p in calls))

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


    def test_legacy_sync_cannot_remap_pinned_poster_and_uses_available_download_title(self):
        class FakePublisher:
            def call(self,method,params):
                if method=="getChat":
                    return {"id":-1001234567890,"type":"channel","title":"Ma série",
                            "pinned_message":{"message_id":202,"photo":[{"file_id":"x"}],
                                              "caption":"Saison 1 : 10 épisodes"}}
                if method=="getChatMember":return {"status":"administrator"}
                raise AssertionError(method)
        queries=[]
        def query(sql,params):
            queries.append((sql,params))
            if "SELECT source_message_id FROM cine_series_posters" in sql:
                return [{"source_message_id":101}]
            return []
        with mock.patch.object(mod,"d1",side_effect=query):
            result=mod.sync_channel(FakePublisher(),777,None,"-1001234567890",True)
        self.assertTrue(result["poster_conflict"])
        self.assertFalse(any("INSERT INTO cine_series_posters" in sql for sql,_ in queries))
        self.assertFalse(any("INSERT INTO cine_series_seasons" in sql for sql,_ in queries))
        buttons=mod.keyboard("abcdefghijklmnopqrstuvwx","https://t.me/+abcdefghijkL","https://t.me/addlist/ABCDEFGHIJK")
        self.assertEqual(buttons["inline_keyboard"][0][0]["text"],"📥 Télécharger les épisodes disponibles")

    def test_legacy_same_poster_may_update_its_caption_only(self):
        class FakePublisher:
            def call(self,method,params):
                if method=="getChat":
                    return {"id":-1001234567890,"type":"channel","title":"Ma série",
                            "pinned_message":{"message_id":101,"photo":[{"file_id":"x"}],
                                              "caption":"Saison 1 : 10 épisodes"}}
                if method=="getChatMember":return {"status":"administrator"}
                raise AssertionError(method)
        queries=[]
        def query(sql,params):
            queries.append(sql)
            if "SELECT source_message_id FROM cine_series_posters" in sql:
                return [{"source_message_id":101}]
            return []
        with mock.patch.object(mod,"d1",side_effect=query):
            result=mod.sync_channel(FakePublisher(),777,None,"-1001234567890",True)
        self.assertFalse(result["poster_conflict"])
        self.assertTrue(any("INSERT INTO cine_series_posters" in sql and
                            "source_message_id=excluded.source_message_id" not in sql for sql in queries))
