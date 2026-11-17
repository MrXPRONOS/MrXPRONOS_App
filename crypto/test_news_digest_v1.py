"""Offline tests: actual source/verification rules, no network and no Telegram."""
import copy
import unittest
from datetime import datetime, timedelta, timezone

from crypto import news_digest_v1 as n

NOW = datetime(2026, 11, 17, 20, tzinfo=timezone.utc)


def item(title, source="CoinDesk", hours=1, url=None):
    obj = {
        "title": title, "source": source,
        "published_at": (NOW - timedelta(hours=hours)).isoformat(),
        "url": url or "https://www.coindesk.com/article/" + source.lower().replace(" ", "-") + "-" + str(hours),
        "french": source == "Journal du Coin",
        "summary": "",
    }
    obj.update(n.signature(obj))
    obj["sensitive"] = bool(n.SENSITIVE.search(n.normalize(title)))
    return obj


class GlobalNewsTests(unittest.TestCase):
    def test_global_sources_are_more_than_original(self):
        self.assertGreaterEqual(len(n.GLOBAL_NEWS_FEEDS), 13)
        self.assertIn("Journal du Coin", n.FRENCH_NEWS_FEEDS)

    def test_tracked_english_and_french_tell_same_story(self):
        en = item("Nigeria approves new stablecoin payments framework for banks")
        fr = item("Nigeria approuve un nouveau cadre stablecoin pour les paiements bancaires",
                  source="Journal du Coin", hours=2)
        self.assertTrue(n.same_event(en, fr))

    def test_unrelated_actions_on_same_platform_not_deduped(self):
        a = item("Coinbase launches a new wallet payment service in France")
        b = item("Coinbase announces a major legal fine for wallet users in France",
                 hours=2)
        self.assertFalse(n.same_event(a, b))

    def test_different_countries_not_conflated(self):
        a = item("Nigeria approves a new stablecoin payment framework for banking")
        b = item("Ghana approves a new stablecoin payment framework for banking", hours=2)
        self.assertFalse(n.same_event(a, b))

    def test_same_url_fingerprints(self):
        a = item("Binance launches a new wallet payment service in Ghana")
        state = {"sent": {}}
        n.mark_sent(state, {"main": a, "others": []}, 501, NOW)
        self.assertTrue(n.already_sent(a, state))
        self.assertIn("news_stories", state)
        self.assertTrue(all(h in state["news_fingerprints"] for h in n.hashes(a["url"])))

    def test_different_publisher_same_story_is_blocked(self):
        a = item("Nigeria approves new stablecoin payments framework for banks")
        b = item("Nigeria approuve un nouveau cadre stablecoin pour les paiements bancaires",
                 source="Journal du Coin", hours=2)
        state = {"sent": {}}
        n.mark_sent(state, {"main": a, "others": []}, 506, NOW)
        self.assertTrue(n.already_sent(b, state))

    def test_single_source_sensitive_is_held(self):
        sensitive = item("Binance hacked after major wallet breach exposes funds")
        def fetcher(source, url, now):
            return ([sensitive], True) if source == "CoinDesk" else ([], True)
        self.assertEqual(n.collect({"sent": {}}, NOW, fetcher), [])

    def test_multiple_independent_sources_allow_sensitive_report(self):
        a = item("Binance hacked after major wallet breach exposes funds", source="CoinDesk")
        b = item("Binance hack: major wallet breach exposes customer funds",
                 source="Journal du Coin", hours=2)
        def fetcher(source, url, now):
            return ([a], True) if source == "CoinDesk" else ([b], True) if source == "Journal du Coin" else ([], True)
        candidates = n.collect({"sent": {}}, NOW, fetcher)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(candidates[0]["others"]), 1)

    def test_only_recent_articles(self):
        entry = {
            "title": "Binance launches a new wallet payment service in Ghana",
            "link": "https://www.coindesk.com/news/crypto-wallet-ghana",
            "published": (NOW - timedelta(hours=38)).isoformat(),
        }
        with self.assertRaises(ValueError):
            n.parse_entry(entry, "CoinDesk", NOW)

    def test_arbitrary_article_domains_rejected(self):
        with self.assertRaises(ValueError):
            n.canonical_url("https://example.net/evil-story", "coindesk.com")
        with self.assertRaises(ValueError):
            n.canonical_url("http://www.coindesk.com/news/article", "coindesk.com")

    def test_disabled_sources_cause_publish_hold(self):
        def broken(source, url, now):
            return [], False
        with self.assertRaises(RuntimeError):
            n.collect({"sent": {}}, NOW, broken)

    def test_nonnews_prediction_held(self):
        self.assertFalse(n.is_relevant("Bitcoin price prediction for tomorrow", ""))

    def test_daily_limit(self):
        s = {"sent": {}}
        for k in range(3):
            s["sent"]["news:11:"+str(k)] = {
                "number": 11,
                "sent_at": NOW.isoformat(),
                "message_id": 55+k,
            }
        self.assertEqual(n.day_count(s, NOW), 3)

    def test_caption_bounded_and_sourced(self):
        a = item("Nigeria approves new stablecoin payments framework for banks")
        c = n.caption({"main": a, "others": []})
        self.assertIn(a["url"], c)
        self.assertLessEqual(len(c), 1024)

    def test_legacy_fingerprints_prevent_repost(self):
        a = item("Binance launches a new wallet payment service in Ghana")
        state = {"sent": {}, "news_fingerprints": {n.hashes(a["url"])[0]: {"number": 9}}}
        self.assertTrue(n.already_sent(a, state))


if __name__ == "__main__":
    unittest.main()
