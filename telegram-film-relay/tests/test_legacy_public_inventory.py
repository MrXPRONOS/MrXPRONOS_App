import unittest
from types import SimpleNamespace as NS
from film_relay.legacy_public_inventory import analyze, urls


class TestPublicInventory(unittest.TestCase):
    def test_no_media(self):
        self.assertEqual(analyze([], "films", -1001234567890,
                                 "https://t.me/addlist/example")["older"], 0)

    def test_valid_url_buttons_only(self):
        p=NS(buttons=[[NS(text="⬇️ TÉLÉCHARGER", url="https://t.me/test"),
                       NS(text="callback", url=None)]])
        self.assertEqual(list(urls(p)), [("⬇️ TÉLÉCHARGER","https://t.me/test")])


if __name__=="__main__":
    unittest.main()
