"""Offline protections for TOP 5 des baisses, no HTTP or Telegram needed."""
import unittest
from crypto.export_losers_v2 import validate_losers, select_real_losers

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

    def test_retry_next_real_loser_when_first_has_no_historical_series(self):
        rows = self.rows + [{"symbol":"COIN5","name":"Coin 5","price":8,
                              "rank":6,"volume":2_000_000,"change":-6}]
        seen=[]
        def fetch(symbol):
            seen.append(symbol)
            if symbol=="COIN0":
                return None
            return [10 + j * 0.01 for j in range(49)]
        result=select_real_losers(rows,fetch_history=fetch,max_candidates=6)
        self.assertEqual([x["symbol"] for x in result],
                         ["COIN1","COIN2","COIN3","COIN4","COIN5"])
        self.assertEqual(len(result),5)
        self.assertEqual(len(seen),6)

    def test_missing_real_histories_fail_closed(self):
        with self.assertRaises(RuntimeError):
            select_real_losers(self.rows,fetch_history=lambda symbol:None)

    def test_short_synthetic_sized_chart_rejected(self):
        with self.assertRaises(RuntimeError):
            select_real_losers(self.rows,fetch_history=lambda symbol:[10.0+j for j in range(12)])

if __name__=="__main__":
    unittest.main()
