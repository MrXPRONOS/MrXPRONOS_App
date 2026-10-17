"""Tests hors réseau pour publication crypto #06."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from crypto.export_dominance_v2 import (
    parse_paprika, parse_coinlore, validate_real, demo_data
)

UTC = timezone.utc


class DominanceV2Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 17, 20, 0, tzinfo=UTC)
        self.paprika = {
            "market_cap_usd": 2_891_600_157_137,
            "volume_24h_usd": 497_263_991_094,
            "bitcoin_dominance_percentage": 57.3,
            "market_cap_change_24h": -1.23,
            "cryptocurrencies_number": 10833,
            "last_updated": int((self.now - timedelta(minutes=10)).timestamp()),
        }

    def test_paprika_valid_and_sum(self):
        out = parse_paprika(self.paprika, self.now)
        self.assertEqual(out["provider"], "CoinPaprika")
        self.assertAlmostEqual(out["btc_dominance_pct"] + out["other_dominance_pct"], 100)
        self.assertEqual(out["market_cap_change_24h_pct"], -1.23)
        validate_real(out, self.now)

    def test_coinlore_without_false_measurement_time(self):
        out = parse_coinlore([{
            "total_mcap": 2_600_000_000_000,
            "total_volume": 128_000_000_000,
            "btc_d": "59.32",
            "mcap_change": "-2.04",
            "coins_count": 14000
        }], self.now)
        self.assertIsNone(out["source_updated_at"])
        self.assertEqual(out["provider"], "CoinLore")
        validate_real(out, self.now)

    def test_missing_or_corrupt_values_fail(self):
        for broken in (None, "nan", "inf", -1, 0, 101):
            with self.subTest(broken=broken):
                p = dict(self.paprika, bitcoin_dominance_percentage=broken)
                with self.assertRaises(ValueError):
                    parse_paprika(p, self.now)

    def test_stale_paprika_is_not_published(self):
        p = dict(self.paprika, last_updated=int((self.now - timedelta(hours=8)).timestamp()))
        with self.assertRaises(ValueError):
            parse_paprika(p, self.now)

    def test_source_count_changes_not_fabricated(self):
        with self.assertRaises(ValueError):
            parse_paprika(dict(self.paprika, market_cap_change_24h=None), self.now)
        with self.assertRaises(ValueError):
            parse_coinlore([{"total_mcap": 4e12}], self.now)

    def test_demo_and_tamper_rejected(self):
        with self.assertRaises(ValueError):
            validate_real(demo_data(), self.now)
        data = parse_paprika(self.paprika, self.now)
        for key, value in [("other_dominance_pct", 90), ("provider", "SIMULATION"),
                           ("status", "demo"), ("source_url", "https://example.com")]:
            changed = copy.deepcopy(data)
            changed[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    validate_real(changed, self.now)

    def test_very_old_snapshot_rejected(self):
        data = parse_paprika(self.paprika, self.now)
        with self.assertRaises(ValueError):
            validate_real(data, self.now + timedelta(minutes=31))


if __name__ == "__main__":
    unittest.main()
