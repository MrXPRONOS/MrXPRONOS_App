"""Quality regression checks across premium Actu Crypto 01..10.

Offline fixtures only; no Telegram or external APIs.
"""
from __future__ import annotations
import math
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from crypto.financial_sanity import validate_global_usd
from crypto.test_channel_premium import get_global_metrics
from crypto.production_seed_v1 import price_caption
from crypto.export_alerts_v2 import threshold
from crypto.export_exchanges_v2 import parse_entry, category_of
from crypto.export_regulation_v2 import demo_report, validate_candidate
from crypto.export_breaking_v2 import demo_report as breaking_demo, validate_real as breaking_validate

UTC = timezone.utc


class GlobalMetricRegressionTests(unittest.TestCase):
    def test_coinlore_usd_values_stay_in_usd_not_billion_times_larger(self):
        class Response:
            def raise_for_status(self):
                return None
            def json(self):
                return [{
                    "total_mcap": 2_718_295_617_920,
                    "total_volume": 84_134_511_488,
                    "mcap_change": 1.37,
                }]
        with patch("crypto.test_channel_premium.requests.get", return_value=Response()):
            d = get_global_metrics()
        self.assertEqual(d["market_cap_total"], 2_718_295_617_920)
        self.assertEqual(d["global_volume_24h"], 84_134_511_488)
        self.assertEqual(validate_global_usd(d["market_cap_total"], d["global_volume_24h"]),
                         (2_718_295_617_920, 84_134_511_488))

    def test_scaled_x_billion_rejected(self):
        with self.assertRaises(ValueError):
            validate_global_usd(2.72e21, 84e18)

    def test_nonfinite_and_zero_rejected(self):
        for cap, vol in [(float("nan"), 9e10), (2e12, 0), (float("inf"), 1e11)]:
            with self.assertRaises(ValueError):
                validate_global_usd(cap, vol)

    def test_micro_price_caption_does_not_round_to_zero(self):
        self.assertEqual(price_caption(0.000004123456), "0.000004123456")
        self.assertNotEqual(price_caption(0.000000049), "0.00")

    def test_alert_paliers_are_observed_not_intraday_crossings(self):
        self.assertEqual(threshold(4.99), 0)
        self.assertEqual(threshold(-5.01), 5)
        self.assertEqual(threshold(10.44), 10)


class NewsEditorialRegressionTests(unittest.TestCase):
    def test_original_wrong_sec_okx_article_no_longer_qualifies_as_exchange_news(self):
        bad = ("SEC tokenized stock framework faces issuer pushback as "
               "Broadcom, Verizon object to OKX-ICE listing")
        self.assertIsNone(category_of(bad))
        with self.assertRaises(ValueError):
            parse_entry({
                "title": bad,
                "link": "https://www.coindesk.com/news/2026/10/18/sec-okx-ice-listing",
                "published_parsed": datetime.now(UTC).timetuple(),
            }, "CoinDesk", datetime.now(UTC))

    def test_real_platform_actions_still_qualify(self):
        now = datetime.now(UTC)
        d = parse_entry({
            "title": "OKX introduces additional wallet payment services for customers",
            "link": "https://www.coindesk.com/news/2026/10/18/okx-wallet-payments",
            "published_parsed": (now - timedelta(hours=1)).timetuple(),
        }, "CoinDesk", now)
        self.assertEqual(d["exchange"], "OKX")
        self.assertEqual(d["category"], "INNOVATION")

    def test_multiple_exchanges_are_not_blindly_attributed(self):
        now = datetime.now(UTC)
        with self.assertRaises(ValueError):
            parse_entry({
                "title": "Binance and OKX announce new wallet payment integration",
                "link": "https://www.coindesk.com/news/2026/10/18/binance-okx",
                "published_parsed": now.timetuple(),
            }, "CoinDesk", now)

    def test_breaking_demos_must_not_be_sent_as_verified(self):
        with self.assertRaises(ValueError):
            breaking_validate(breaking_demo())

    def test_regulation_remains_human_review_only(self):
        with self.assertRaises(ValueError):
            validate_candidate(demo_report())


if __name__ == "__main__":
    unittest.main()
