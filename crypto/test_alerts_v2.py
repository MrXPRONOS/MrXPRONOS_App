"""Tests déterministes des seuils d'alerte, sans accès réseau ni bot."""
import unittest
from crypto.export_alerts_v2 import threshold, select_alert, demo_data


def row(symbol, pct, rank):
    return {"symbol": symbol, "rank": rank, "price": 200, "change": pct, "name": symbol}


class AlertV2Tests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(threshold(4.99), 0)
        self.assertEqual(threshold(-4.99), 0)
        self.assertEqual(threshold(5), 5)
        self.assertEqual(threshold(-5), 5)
        self.assertEqual(threshold(-9.99), 5)
        self.assertEqual(threshold(10), 10)
        self.assertEqual(threshold(-14.99), 10)

    def test_no_alert_under_five(self):
        self.assertIsNone(select_alert([row("BTC", 4.9, 1), row("ETH", -2, 2)]))

    def test_prioritizes_highest_level(self):
        chosen = select_alert([row("BTC", 6, 1), row("ETH", -12.7, 2), row("SOL", 10.2, 5)])
        self.assertEqual(chosen["symbol"], "ETH")
        self.assertEqual(chosen["direction"], "down")
        self.assertEqual(chosen["level"], 10)

    def test_invalid_rank_and_price(self):
        self.assertIsNone(select_alert([row("BTC", 11, 101), {**row("ETH", 7, 2), "price": -1}]))

    def test_watch_only_and_dedup(self):
        chosen = select_alert([row("DOGE", 30, 10), row("BTC", 5.2, 1), row("BTC", 40, 60)])
        self.assertEqual((chosen["symbol"], chosen["level"]), ("BTC", 5))

    def test_bad_data_not_alert(self):
        self.assertIsNone(select_alert([row("ETH", float("nan"), 2), row("BTC", 5001, 1)]))

    def test_demo_cannot_claim_real(self):
        fixture = demo_data()
        self.assertTrue(fixture["is_demo"])
        self.assertEqual(fixture["status"], "demo")
        self.assertEqual(fixture["row"]["level"], 10)


if __name__ == "__main__":
    unittest.main()