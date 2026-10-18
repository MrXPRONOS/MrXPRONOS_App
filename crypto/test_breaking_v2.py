"""Tests isolés #08 : aucun appel réseau, aucun envoi Telegram."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from crypto.export_breaking_v2 import (
    demo_report, build_report, validate_real, parse_entry, corroborates,
    newsworthy, canonical_url, load_state, already_published,
    fingerprint, candidate_pairs, iso_time,
)

UTC = timezone.utc


class BreakingNewsTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 18, 9, tzinfo=UTC)
        self.a = {"source": "CoinDesk",
                  "title": "Bitcoin ETF receives approval after regulator review",
                  "url": "https://www.coindesk.com/news/btc-etf-one",
                  "published_at": (self.now - timedelta(hours=3)).isoformat(),
                  "topic": "bitcoin"}
        self.b = {"source": "The Block",
                  "title": "Bitcoin ETF approval announced following regulator review",
                  "url": "https://www.theblock.co/news/btc-etf-two",
                  "published_at": (self.now - timedelta(hours=2)).isoformat(),
                  "topic": "bitcoin"}

    def real(self):
        return build_report((self.a, self.b), self.now)

    def test_valid_two_source_report(self):
        validate_real(self.real(), self.now)

    def test_demo_can_never_publish(self):
        with self.assertRaises(ValueError):
            validate_real(demo_report(), self.now)

    def test_one_source_cannot_confirm_itself(self):
        duplicate = {**self.a, "url": "https://www.coindesk.com/news/another"}
        self.assertFalse(corroborates(self.a, duplicate))

    def test_ethereum_not_compatible_with_bitcoin(self):
        x = {**self.b, "topic": "ethereum",
             "title": "Ethereum ETF approval announced following regulator review"}
        self.assertFalse(corroborates(self.a, x))

    def test_different_events_do_not_match(self):
        x = {**self.b, "title": "Bitcoin network suffers major outage after upgrade"}
        self.assertFalse(corroborates(self.a, x))

    def test_sponsored_and_predictions_rejected(self):
        self.assertFalse(newsworthy("Sponsored Bitcoin ETF approval article"))
        self.assertFalse(newsworthy("Bitcoin price prediction: ETF approval"))

    def test_no_invented_timestamp(self):
        with self.assertRaises(ValueError):
            iso_time(None, self.now)
        with self.assertRaises(ValueError):
            iso_time((self.now - timedelta(hours=13)).isoformat(), self.now)

    def test_source_domain_allowlist(self):
        with self.assertRaises(ValueError):
            canonical_url("https://coindesk.com.evil.example/a", "coindesk.com")
        with self.assertRaises(ValueError):
            canonical_url("http://www.coindesk.com/a", "coindesk.com")
        self.assertEqual(canonical_url("https://www.coindesk.com/news/a?utm_source=x", "coindesk.com"),
                         "https://www.coindesk.com/news/a")

    def test_no_repeat_url_across_runs(self):
        self.assertTrue(already_published([self.a, self.b], {"sent_urls": [fingerprint(self.b)]}))
        self.assertEqual(candidate_pairs([self.a, self.b], {"sent_urls": [fingerprint(self.a)]}), [])

    def test_invalid_state_stops(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "state.json"
            p.write_text('{"sent_urls": "oops"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_state(p)

    def test_tampered_fingerprint_rejected(self):
        report = self.real()
        report["fingerprints"] = ["wrong", "wrong"]
        with self.assertRaises(ValueError):
            validate_real(report, self.now)

    def test_report_expires(self):
        with self.assertRaises(ValueError):
            validate_real(self.real(), self.now + timedelta(hours=13))

    def test_rss_record_extraction(self):
        from time import gmtime
        entry = {"title": self.a["title"],
                 "link": self.a["url"],
                 "published_parsed": gmtime((self.now - timedelta(hours=3)).timestamp())}
        x = parse_entry(entry, "CoinDesk", self.now)
        self.assertEqual(x["topic"], "bitcoin")
        self.assertEqual(x["url"], self.a["url"])


if __name__ == "__main__":
    unittest.main()
