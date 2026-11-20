import importlib.util
from pathlib import Path
from unittest import TestCase, mock
import sys

ROOT=Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location("showcase",ROOT/"publish_series_showcase_bot.py")
showcase=importlib.util.module_from_spec(spec)
spec.loader.exec_module(showcase)

class SeriesShowcaseTests(TestCase):
    def test_buttons_do_not_claim_episodes_available_if_unchecked(self):
        tok="abcdefghijklmnopqrstuvwx"
        link="https://t.me/+abcdefghijkL"
        pending=showcase.markup(tok,link,"",ready=False)["inline_keyboard"]
        self.assertIn("Disponibilité",pending[0][0]["text"])
        self.assertEqual(len(pending),2)
        self.assertEqual(pending[1][0]["url"],link)
        complete=showcase.markup(tok,link,"https://t.me/addlist/ABCDEFGHIJK",ready=True)["inline_keyboard"]
        self.assertEqual(len(complete),3)
        self.assertEqual(complete[0][0]["text"],"📥 Télécharger")
        self.assertEqual([x[0]["style"] for x in complete],["success","danger","primary"])

    def test_plan_selects_earliest_known_poster_even_when_first_season_unavailable(self):
        def query(sql,values):
            if "FROM cine_series_channels" in sql:
                return [{"chat_id":values[0],"title":"Une série","publisher_access":"verified",
                         "radar_access":"verified","rights_attested":1,"enabled":1}]
            if "FROM cine_series_posters" in sql:
                return [{"season":3,"source_message_id":42}]
            if "FROM cine_series_publications" in sql:
                return []
            raise AssertionError(sql)
        with mock.patch.object(showcase,"d1",side_effect=query), mock.patch.object(showcase,"downloadable_index",return_value={"ready":False}):
            found=showcase.plan_one("-1001234567890")
        self.assertEqual(found["season"],3)
        self.assertEqual(found["status"],"READY_TO_POST")
        self.assertFalse(found["ready"])

    def test_pending_receipt_is_not_reposted(self):
        item={"chat_id":"-1001234567890","status":"REQUIRES_MANUAL_REVIEW",
              "existing":{"state":"pending"}}
        with mock.patch.object(showcase,"request_bot") as telegram:
            result=showcase.publish_one("123:token",item,"https://t.me/+abcdefghijkL","")
        self.assertEqual(result["status"],"REQUIRES_MANUAL_REVIEW")
        telegram.assert_not_called()

    def test_published_receipt_updates_buttons_without_copying_poster(self):
        item={"chat_id":"-1001234567890","status":"ALREADY_PUBLISHED","ready":False,
              "existing":{"token":"abcdefghijklmnopqrstuvwx","state":"published","public_post_id":44,"rescue_post_id":55}}
        with mock.patch.object(showcase,"request_bot",return_value=True) as telegram:
            result=showcase.publish_one("123:token",item,"https://t.me/+abcdefghijkL","")
        self.assertEqual(result["status"],"UPDATED_EXISTING")
        self.assertEqual(telegram.call_count,2)
        self.assertTrue(all(call.args[1]=="editMessageReplyMarkup" for call in telegram.call_args_list))


    def test_publisher_needs_both_destination_rights(self):
        ids=["-1001234567890"]
        class FakeBot:
            def __init__(self, token):
                self.token=token
            def call(self,method,data):
                if method=="getMe":return {"id":111,"username":"ExampleBot"}
                if method=="getChat":return {"id":int(data["chat_id"]),"type":"channel","title":"Test"}
                if method=="getChatMember":return {"status":"administrator"}
                raise AssertionError(method)
        def allowed(bot,cid,uid):
            if cid==showcase.RESCUE:raise RuntimeError("Telegram 400")
            return {"id":int(cid),"type":"channel"}
        with mock.patch.dict("os.environ",{"CINEX_PUBLISH_BOT_TOKEN":"111:abc"},clear=True):
            with mock.patch.object(showcase,"BotAPI",FakeBot):
                with mock.patch.object(showcase,"check_publisher",side_effect=allowed):
                    with self.assertRaisesRegex(RuntimeError,"secours"):
                        showcase.find_authorized_publisher(ids)

    def test_downloadable_index_accepts_only_currently_indexed_seasons(self):
        def query(sql, values):
            self.assertIn("FROM cine_series_episodes",sql)
            return [
                {"season":3,"episode":1,"source_message_id":101},
                {"season":3,"episode":2,"source_message_id":102},
            ]
        with mock.patch.object(showcase,"d1",side_effect=query):
            result=showcase.downloadable_index("-1001234567890")
        self.assertTrue(result["ready"])
        self.assertEqual(result["count"],2)
        self.assertEqual(result["seasons"],[{"season":3,"episodes":2}])

    def test_downloadable_index_rejects_gaps_and_empty_catalogue(self):
        for episodes in ([],[
            {"season":1,"episode":1,"source_message_id":10},
            {"season":1,"episode":3,"source_message_id":12},
        ],[{"season":2,"episode":2,"source_message_id":12}]):
            with self.subTest(episodes=episodes):
                with mock.patch.object(showcase,"d1",return_value=episodes):
                    self.assertFalse(showcase.downloadable_index("-1001234567890")["ready"])

    def test_ready_existing_poster_switches_to_download_without_new_publication(self):
        old={"chat_id":"-1001234567890","status":"ALREADY_PUBLISHED","ready":True,
             "existing":{"token":"abcdefghijklmnopqrstuvwx","state":"published","public_post_id":44,"rescue_post_id":55}}
        with mock.patch.object(showcase,"request_bot",return_value=True) as api:
            result=showcase.publish_one("123:token",old,"https://t.me/+abcdefghijkL","https://t.me/addlist/ABCDEFGHIJK")
        self.assertEqual(result["status"],"UPDATED_EXISTING")
        self.assertTrue(result["download_ready"])
        self.assertEqual(api.call_count,2)
        for call in api.call_args_list:
            self.assertEqual(call.args[1],"editMessageReplyMarkup")
            self.assertEqual(call.args[2]["reply_markup"]["inline_keyboard"][0][0]["text"],"📥 Télécharger")
