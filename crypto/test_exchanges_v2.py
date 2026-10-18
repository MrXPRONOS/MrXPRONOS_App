"""Offline correctness checks for Mr XPRONOS Actu Crypto #09."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto import export_exchanges_v2 as ex

UTC = timezone.utc


class ExchangeNewsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(UTC)

    def item(self, title="Binance introduces a new wallet payment service for users",
             source="CoinDesk", offset=2):
        return ex.parse_entry({
            "title": title,
            "link": "https://" + ex.FEEDS[source][1] + "/post/exchange-news-example-" + source.lower().replace(" ", ""),
            "published_parsed": (self.now - timedelta(hours=offset)).timetuple()
        }, source, self.now)

    def test_demo_never_validates_as_real(self):
        with self.assertRaises(ValueError):
            ex.validate_real(ex.demo_report(), self.now)

    def test_exchange_detection_exact_not_similar(self):
        self.assertEqual(ex.exchange_of("OKX to launch a new service"), "OKX")
        self.assertIsNone(ex.exchange_of("FauxOKXPay introduces a wallet"))
        self.assertIsNone(ex.exchange_of("Binance and OKX launch wallets"))

    def test_recognises_all_named_exchanges(self):
        for name in ex.EXCHANGES:
            self.assertEqual(ex.exchange_of(name + " launches a new service"), name)

    def test_category_rejects_price_predictions_and_marketing(self):
        self.assertIsNone(ex.category_of("Binance price prediction with token listing"))
        self.assertIsNone(ex.category_of("Sponsored: Coinbase launches a wallet"))
        self.assertIsNotNone(ex.category_of("OKX suspends withdrawals for maintenance"))

    def test_eight_free_press_sources_and_two_official_apis(self):
        self.assertGreaterEqual(len(ex.FEEDS), 8)
        self.assertEqual(len(ex.OFFICIAL_STATUS_APIS), 2)
        self.assertEqual(len(set(x[1] for x in ex.FEEDS.values())), len(ex.FEEDS))
        self.assertTrue(all(x[0].startswith("https://") for x in ex.FEEDS.values()))

    def test_official_incident_selected_without_press_confirmation(self):
        raw = {"id": "abc12345def9", "name": "USDT withdrawals temporarily delayed",
               "status": "investigating", "impact": "minor",
               "created_at": (self.now - timedelta(hours=1)).isoformat()}
        event = ex.parse_official_incident(raw, "Kraken Status", self.now)
        self.assertTrue(event["official"])
        self.assertEqual(event["exchange"], "KRAKEN")
        self.assertEqual(event["category"], "ACCÈS & SERVICES")
        d = ex.select_report([event], {"sent_urls": []}, self.now)
        self.assertEqual(d["verification"], "official_notice")
        self.assertEqual(d["main"]["incident_id"], "abc12345def9")
        ex.validate_real(d, self.now)

    def test_official_impact_and_status_must_be_valid(self):
        raw = {"id": "abc12345def9", "name": "USD withdrawals are delayed",
               "status": "resolved", "impact": "minor",
               "created_at": (self.now - timedelta(hours=1)).isoformat()}
        with self.assertRaises(ValueError):
            ex.parse_official_incident(raw, "Coinbase Status", self.now)
        raw["status"] = "investigating"
        raw["impact"] = "none"
        with self.assertRaises(ValueError):
            ex.parse_official_incident(raw, "Coinbase Status", self.now)

    def test_official_status_cannot_impersonate_another_exchange(self):
        raw = {"id": "abc12345def9", "name": "USDT withdrawals temporarily delayed",
               "status": "investigating", "impact": "major",
               "created_at": (self.now - timedelta(hours=1)).isoformat()}
        d = ex.select_report([ex.parse_official_incident(raw, "Kraken Status", self.now)],
                             {"sent_urls": []}, self.now)
        d["main"]["exchange"] = "COINBASE"
        with self.assertRaises(ValueError):
            ex.validate_real(d, self.now)

    def test_official_incident_fingerprints_are_individual(self):
        raw = {"id": "abc12345def9", "name": "USDT withdrawals temporarily delayed",
               "status": "investigating", "impact": "minor",
               "created_at": (self.now - timedelta(hours=1)).isoformat()}
        a = ex.parse_official_incident(raw, "Kraken Status", self.now)
        raw["id"] = "def12345abc9"
        b = ex.parse_official_incident(raw, "Kraken Status", self.now)
        self.assertNotEqual(ex.fingerprint(a), ex.fingerprint(b))

    def test_untrusted_urls_rejected(self):
        for bad in ("http://www.coindesk.com/post/article",
                    "https://coindesk.com.evil.org/post/article",
                    "https://example.com/post/article",
                    "https://coindesk.com/"):
            with self.assertRaises(ValueError):
                ex.canonical_url(bad, "coindesk.com")

    def test_no_undated_future_or_stale_articles(self):
        base = "Binance launches a new payment integration for users"
        for hours in (49, -2):
            with self.assertRaises(ValueError):
                self.item(base, offset=hours)
        with self.assertRaises(ValueError):
            ex.parse_entry({"title": base,
                            "link": "https://coindesk.com/post/news-example"},
                           "CoinDesk", self.now)

    def test_regular_source_with_attribution_can_be_selected(self):
        row = self.item()
        d = ex.select_report([row], {"sent_urls": []}, self.now)
        self.assertEqual(d["verification"], "attributed_report")
        self.assertEqual(d["exchange"], "BINANCE")
        self.assertIsNone(d["confirmation"])
        ex.validate_real(d, self.now)

    def test_sensitive_event_requires_second_independent_source(self):
        row = self.item("Coinbase hacked after severe security breach in trading platform")
        self.assertTrue(row["severe"])
        self.assertIsNone(ex.select_report([row], {"sent_urls": []}, self.now))

    def test_sensitive_event_with_two_publishers_can_be_selected(self):
        a = self.item("Coinbase reports security breach following wallet hack", source="CoinDesk")
        b = self.item("Coinbase wallet hack tied to security breach", source="The Block", offset=1)
        self.assertTrue(ex.corroborates(a, b))
        d = ex.select_report([a, b], {"sent_urls": []}, self.now)
        self.assertEqual(d["verification"], "cross_reported")
        self.assertEqual({d["main"]["source"], d["confirmation"]["source"]}, {"CoinDesk", "The Block"})
        ex.validate_real(d, self.now)

    def test_corroboration_rejects_same_publisher(self):
        one = self.item("Coinbase wallet hack prompts security breach response", "CoinDesk")
        another = self.item("Coinbase wallet hack prompts security breach response", "CoinDesk")
        self.assertFalse(ex.corroborates(one, another))

    def test_unrelated_events_do_not_correlate(self):
        a = self.item("Binance launches a new wallet payment service for users")
        b = self.item("Binance introduces new USDC spot trading fees", "The Block")
        self.assertFalse(ex.corroborates(a, b))

    def test_previously_sent_news_is_not_republished(self):
        item = self.item()
        self.assertIsNone(ex.select_report([item],
                                            {"sent_urls": [ex.fingerprint(item)]},
                                            self.now))

    def test_invalid_anti_duplicate_state_stops(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / "state.json"
            state.write_text('{"sent_urls": [3]}')
            with self.assertRaises(ValueError):
                ex.load_state(state)

    def test_fingerprint_tampering_rejected(self):
        d = ex.select_report([self.item()], {"sent_urls": []}, self.now)
        d["fingerprints"] = ["wrong"]
        with self.assertRaises(ValueError):
            ex.validate_real(d, self.now)

    def test_nonmatching_second_source_rejected(self):
        d = ex.select_report([self.item()], {"sent_urls": []}, self.now)
        d["confirmation"] = self.item("OKX launches new trading service", "The Block")
        d["verification"] = "cross_reported"
        with self.assertRaises(ValueError):
            ex.validate_real(d, self.now)

    def test_sensitive_cannot_be_forged_as_regular(self):
        d = ex.select_report([self.item()], {"sent_urls": []}, self.now)
        d["main"]["title"] = "Binance hacked after a wallet breach"
        with self.assertRaises(ValueError):
            ex.validate_real(d, self.now)


if __name__ == "__main__":
    unittest.main()
