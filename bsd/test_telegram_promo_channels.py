"""Offline tests: promotions always target both channels and report failures."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"scripts"))
from telegram_promo_channels import promo_channels, deliver_to_both

class PromoChannelsTests(unittest.TestCase):
    def test_two_distinct_destinations(self):
        self.assertEqual(promo_channels("-100111","@other"),(
            ("primary","-100111"),("secondary","@other")))

    def test_reject_missing_or_duplicate_secondary(self):
        for secondary in (None,"","   ","-100111"):
            with self.subTest(secondary=secondary):
                with self.assertRaises(ValueError):
                    promo_channels("-100111",secondary)

    def test_second_sent_even_if_first_fails(self):
        called=[]
        def send(cid):
            called.append(cid)
            if cid=="a":raise RuntimeError("403")
        with self.assertRaises(RuntimeError):
            deliver_to_both(promo_channels("a","b"),send)
        self.assertEqual(called,["a","b"])

    def test_both_errors_reported(self):
        def send(cid):raise RuntimeError("fail "+cid)
        with self.assertRaisesRegex(RuntimeError,"primary.*secondary"):
            deliver_to_both(promo_channels("a","b"),send)

    def test_success_count(self):
        ids=[]
        self.assertEqual(deliver_to_both(promo_channels("a","b"),ids.append),2)
        self.assertEqual(ids,["a","b"])

if __name__=="__main__":
    unittest.main()
