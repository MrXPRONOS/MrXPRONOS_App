import unittest
from scripts import cineradar_standby_bot_menu as bot


class TestStandbyBotMenu(unittest.TestCase):
    def test_health_requires_both_real_d1_and_app(self):
        def healthy(url):
            if url.endswith("/health"):
                return {"status":200,"json":{"service":"cine-radar","database":True},"type":"application/json"}
            return {"status":200,"type":"text/html; charset=utf-8","json":{}}
        self.assertTrue(bot.read_health(healthy))
        def failed(url):
            return {"status":503,"json":{"maintenance":True},"type":"application/json"}
        self.assertFalse(bot.read_health(failed))
        def half(url):
            if url.endswith("/health"):
                return {"status":200,"json":{"service":"cine-radar","database":True}}
            return {"status":1027,"type":"text/html"}
        self.assertFalse(bot.read_health(half))

    def test_identifies_only_main_bot_matching_cineradar_webhook(self):
        registry={"good":{"url":bot.WEBHOOK,"id":321},
                  "duplicate":{"url":bot.WEBHOOK,"id":321},
                  "other":{"url":"https://other.invalid/telegram","id":999}}
        def api(token,method,data):
            if method=="getWebhookInfo":
                return {"url":registry[token]["url"]}
            return {"id":registry[token]["id"],"is_bot":True}
        self.assertEqual(bot.select_active_bot({
            "CINE_RADAR_BOT_TOKEN":"good",
            "TELEGRAM_BOT_TOKEN":"duplicate",
            "CINEX_BOT_TOKEN":"other",
        },api),"good")

    def test_unverified_or_ambiguous_bot_fails_closed(self):
        def api(token,method,data):
            if method=="getWebhookInfo":
                return {"url":bot.WEBHOOK}
            return {"id":1 if token=="first" else 2,"is_bot":True}
        with self.assertRaises(RuntimeError):
            bot.select_active_bot({"CINE_RADAR_BOT_TOKEN":"first","CINEX_BOT_TOKEN":"second"},api)

    def test_fallback_menu_and_profile_auto_restore_with_confirmation(self):
        state={"url":bot.APP,"description":bot.NORMAL_DESCRIPTION}
        operations=[]
        def api(token,method,data):
            operations.append(method)
            if method=="getChatMenuButton":
                return {"type":"web_app","text":"Menu","web_app":{"url":state["url"]}}
            if method=="getMyShortDescription":
                return {"short_description":state["description"]}
            if method=="setChatMenuButton":
                state["url"]=data["menu_button"]["web_app"]["url"]
                return True
            if method=="setMyShortDescription":
                state["description"]=data["short_description"]
                return True
            raise AssertionError(method)
        result=bot.reconcile("token",False,api)
        self.assertEqual(result["mode"],"maintenance")
        self.assertEqual(state["url"],bot.STANDBY)
        self.assertEqual(state["description"],bot.MAINT_DESCRIPTION)
        result2=bot.reconcile("token",False,api)
        self.assertFalse(result2["menu_changed"])
        self.assertFalse(result2["description_changed"])
        restored=bot.reconcile("token",True,api)
        self.assertEqual(restored["mode"],"operational")
        self.assertEqual(state["url"],bot.APP)
        self.assertEqual(state["description"],bot.NORMAL_DESCRIPTION)
        self.assertNotIn("setWebhook",operations)
        self.assertNotIn("deleteWebhook",operations)
        self.assertNotIn("getUpdates",operations)


    def test_http_probe_parses_curl_status_and_body(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess
        output='{"service":"cine-radar","database":true}\n200|application/json'
        with patch.object(bot.subprocess,"run",return_value=CompletedProcess([],0,stdout=output,stderr="")):
            result=bot.http_probe(bot.BASE+"/health")
        self.assertEqual(result["status"],200)
        self.assertEqual(result["json"]["service"],"cine-radar")
        self.assertTrue(result["json"]["database"])

    def test_real_health_classification_does_not_treat_ci_network_block_as_outage(self):
        from unittest.mock import patch
        with patch.object(bot.time,"sleep",return_value=None):
            self.assertIsNone(bot.checked_health(lambda url:{"status":403,"type":"text/html","json":{}}))
            self.assertFalse(bot.checked_health(lambda url:{"status":503,"type":"text/html","json":{}}))
            def healthy(url):
                return ({"status":200,"type":"application/json","json":{"service":"cine-radar","database":True}}
                        if url.endswith("/health") else {"status":200,"type":"text/html","json":{}})
            self.assertTrue(bot.checked_health(healthy))

    def test_custom_menu_is_never_modified(self):
        def api(token,method,data):
            if method=="getChatMenuButton":
                return {"type":"commands"}
            raise AssertionError("Should never modify")
        with self.assertRaises(RuntimeError):
            bot.reconcile("token",False,api)

    def test_custom_description_is_not_overwritten(self):
        state={"url":bot.APP}
        writes=[]
        def api(token,method,data):
            if method=="getChatMenuButton":
                return {"type":"web_app","web_app":{"url":state["url"]}}
            if method=="getMyShortDescription":
                return {"short_description":"Custom text from owner"}
            if method=="setChatMenuButton":
                state["url"]=data["menu_button"]["web_app"]["url"]
                writes.append(method)
                return True
            raise AssertionError("Unexpected Telegram modification "+method)
        bot.reconcile("token",False,api)
        self.assertEqual(writes,["setChatMenuButton"])


if __name__=="__main__":
    unittest.main()
