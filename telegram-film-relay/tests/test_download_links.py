import os
import unittest
from unittest.mock import patch
from film_relay.download_links import title_key,approved_download_url


class DeepLinkTests(unittest.TestCase):
    def setUp(self):
        approved_download_url.cache_clear()

    def test_title_key_is_stable_and_category_scoped(self):
        self.assertEqual(title_key("series","GIGN S01E02"),
                         title_key("series","GIGN"))
        self.assertNotEqual(title_key("series","GIGN"),title_key("action","GIGN"))
        self.assertIsNone(title_key("anime","GIGN"))

    def test_no_secret_means_no_download_link(self):
        with patch.dict(os.environ,{"CLOUDFLARE_API_TOKEN":"","CF_API_TOKEN":"",
                                    "CLOUDFLARE_ACCOUNT_ID":"","CINERADAR_D1_DATABASE_ID":""}):
            self.assertIsNone(approved_download_url("series","GIGN",1))

    def test_only_approved_telegram_token_exposed(self):
        class Resp:
            ok=True
            def json(self):
                return {"success":True,"result":[{"results":[{"token":"A"*24}]}]}
        with patch.dict(os.environ,{"CLOUDFLARE_API_TOKEN":"fake",
                                    "CLOUDFLARE_ACCOUNT_ID":"fake",
                                    "CINERADAR_D1_DATABASE_ID":"fake"}):
            with patch("requests.post",return_value=Resp()) as req:
                self.assertEqual(
                    approved_download_url("series","GIGN",1),
                    "https://t.me/CineRadarFr_Bot?start=d_"+"A"*24)
                self.assertIn("cine_delivery_enabled",req.call_args.kwargs["json"]["sql"])

if __name__=="__main__":
    unittest.main()
