"""Tests sans connexion Telegram du workflow de découverte quotidienne."""
import unittest
from scripts.discovery_daily import categories, format_report, make_category_cfg

class DailyDiscoveryTests(unittest.TestCase):
    def test_four_categories_in_exact_order(self):
        self.assertEqual([c["id"] for c in categories()],
                         ["films", "desir", "comedie", "anime"])

    def test_daily_digest_has_html_and_visible_links(self):
        record = {"username": "romancecinex2026",
                  "title": "Cinéma & Romance", "format_verified": True}
        secs = [{"id": "desir", "label": "Films romantiques",
                 "channels": [record]}]
        body = format_report("2026-10-17", secs, set())
        self.assertIn("<b>Films romantiques", body)
        self.assertIn("<i>", body)
        self.assertIn("https://t.me/romancecinex2026", body)
        self.assertIn("&amp;", body)
        self.assertIn("CINEX-DECOUVERTE-2026-10-17", body)

    def test_previous_channels_are_identified(self):
        secs = [{"id": "anime", "label": "Animés",
                 "channels": [{"username": "AnimeVF300", "title": "Anime", "format_verified": False}]}]
        body = format_report("2026-10-17", secs, {"animevf300"})
        self.assertIn("↩️", body)
        self.assertIn("non confirmé", body)

    def test_limits_are_conservative(self):
        cfg = make_category_cfg(categories()[3], {
            "results_per_query": 8, "max_channels_per_category": 4,
            "sample_messages": 55, "pause_seconds": 12})
        self.assertEqual(cfg["max_channels_per_run"], 4)
        self.assertGreaterEqual(cfg["request_pause_seconds"], 10)
        self.assertEqual(cfg["min_video_minutes"], 10)
        self.assertTrue(cfg["include_unverified"])

    def test_digest_remains_below_telegram_limit(self):
        sections = [
            {"id":cat, "label": cat.upper(), "channels": [
                {"username": "cinexchannel" + str(i + n*5),
                 "title": "Une chaîne avec un titre très long 1234567" * 2,
                 "format_verified":True} for i in range(4)]}
            for n, cat in enumerate(["films", "desir", "comedie", "anime"])
        ]
        body = format_report("2026-10-17", sections, set())
        self.assertLess(len(body.encode("utf-8")), 3900)

if __name__ == "__main__":
    unittest.main()
