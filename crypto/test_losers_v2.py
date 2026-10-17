"""Offline protections for TOP 5 des baisses, no HTTP or Telegram needed."""
import unittest
from crypto.export_losers_v2 import validate_losers

class TestLosersV2(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"symbol": "COIN"+str(i), "name":"Coin", "price":i+1,
             "rank":i+1, "volume":2_000_000, "change":-(11-i)}
            for i in range(5)
        ]

    def test_five_real_negative_sorted(self):
        self.assertEqual(len(validate_losers(self.rows)),5)

    def test_reject_positive_or_zero(self):
        self.rows[3]["change"]=0
        with self.assertRaises(ValueError): validate_losers(self.rows)

    def test_reject_bad_rank_or_volume(self):
        self.rows[1]["rank"]=101
        with self.assertRaises(ValueError): validate_losers(self.rows)
        self.rows[1]["rank"]=2
        self.rows[1]["volume"]=900_000
        with self.assertRaises(ValueError): validate_losers(self.rows)

    def test_reject_unsorted(self):
        self.rows[4]["change"]=-15
        with self.assertRaises(ValueError): validate_losers(self.rows)

    def test_reject_duplicate(self):
        self.rows[4]["symbol"]=self.rows[1]["symbol"]
        with self.assertRaises(ValueError): validate_losers(self.rows)

if __name__=="__main__":
    unittest.main()
