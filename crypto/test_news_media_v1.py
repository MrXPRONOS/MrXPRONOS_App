"""No-network tests for publisher photography and Telegram HTML formatting."""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from PIL import Image
from crypto import news_media_v1 as media
from crypto import news_digest_v1 as digest

NOW = datetime(2026, 11, 17, 21, tzinfo=timezone.utc)


def story():
    row = {
        "source": "CoinDesk",
        "title": "Coinbase announces <new> crypto wallet payment service for Ghana",
        "summary": "A new & verified announcement concerning the Coinbase payment service.",
        "published_at": NOW.isoformat(),
        "url": "https://www.coindesk.com/news/coinbase-ghana-wallet",
        "category": "PAIEMENTS & ADOPTION",
        "french": False,
        "image_candidates": ["https://images.coindesk.com/coinbase-ghana.jpg"],
    }
    return {"main": row, "others": []}


class MediaTests(TestCase):
    def test_rss_media_and_html_image_extracted(self):
        ent = {
            "media_content": [{"url": "https://cdn.coindesk.com/a.jpg", "type": "image/jpeg"}],
            "media_thumbnail": [{"url": "https://cdn.coindesk.com/b.jpg"}],
            "summary": '<div><img src="/article_photo.jpg"/></div>',
            "enclosures": [{"href": "https://cdn.coindesk.com/c.png", "type": "image/png"}],
        }
        candidates = media.images_from_rss(ent, "https://www.coindesk.com/news/example")
        self.assertIn("https://cdn.coindesk.com/a.jpg", candidates)
        self.assertIn("https://cdn.coindesk.com/b.jpg", candidates)
        self.assertIn("https://cdn.coindesk.com/c.png", candidates)
        self.assertIn("https://www.coindesk.com/article_photo.jpg", candidates)

    def test_html_open_graph(self):
        raw = '<meta property="og:image" content="https://cdn.coindesk.com/article.jpg">'
        self.assertEqual(
            media.og_images(raw, "https://www.coindesk.com/news/story"),
            ["https://cdn.coindesk.com/article.jpg"]
        )

    def test_no_private_or_insecure_urls(self):
        for uri in (
            "http://coindesk.com/a.jpg",
            "https://127.0.0.1/a.jpg",
            "https://localhost/a.jpg",
            "https://router.internal/a.jpg",
            "https://user:pass@example.com/a.jpg",
            "https://example.com:8080/a.jpg",
        ):
            self.assertFalse(media.safe_https_shape(uri), uri)
        self.assertTrue(media.safe_https_shape("https://cdn.coindesk.com/a.jpg"))

    def test_html_caption_formats_and_escapes_without_links(self):
        cap = media.caption(story())
        self.assertIn("<blockquote>", cap)
        self.assertIn("</blockquote>", cap)
        self.assertIn("<b>", cap)
        self.assertIn("<i>", cap)
        self.assertIn("&lt;new&gt;", cap)
        self.assertIn("&amp;", cap)
        self.assertNotIn("https://", cap)
        self.assertNotIn("http://", cap)
        self.assertNotIn("www.", cap)
        self.assertLess(len(cap), 1024)

    def test_caption_omits_publication_time_and_date(self):
        cap = media.caption(story())
        self.assertNotIn("🕒", cap)
        self.assertNotIn("21:00", cap)
        self.assertNotIn("17/11/2026", cap)
        self.assertNotIn("UTC", cap)
        self.assertTrue(cap.endswith("</i>"))
        self.assertIn("Source : CoinDesk", cap)

    def test_caption_strips_link_from_headline_and_summary(self):
        c = story()
        c["main"]["title"] += " https://foo.example/image"
        c["main"]["summary"] += " www.foo.example/example"
        cap = media.caption(c)
        self.assertNotIn("http", cap)
        self.assertNotIn("www.", cap)

    def test_photo_fallback_when_rss_thumbnail_fails(self):
        c = story()
        with TemporaryDirectory() as td:
            dest = Path(td) / "result.jpg"
            with mock.patch.object(media, "fetch_photo", side_effect=[None, dest]) as fetch:
                with mock.patch.object(media, "from_article_og", return_value=["https://cdn.coindesk.com/article.jpg"]):
                    self.assertEqual(media.photo_for(c, dest), (dest, "CoinDesk"))
                    self.assertEqual(fetch.call_count, 2)

    def test_no_verified_image_means_no_publishable_photo(self):
        with mock.patch.object(media, "fetch_photo", return_value=None):
            with mock.patch.object(media, "from_article_og", return_value=[]):
                self.assertIsNone(media.photo_for(story()))

    def test_rss_parse_retains_photo_candidates(self):
        entry = {
            "title": "Coinbase launches a new crypto payment service in Ghana",
            "link": "https://www.coindesk.com/news/payment-ghana-coinbase",
            "published": NOW.isoformat(),
            "media_content": [{"url": "https://images.coindesk.com/ghana.jpg", "type": "image/jpeg"}],
        }
        parsed = digest.parse_entry(entry, "CoinDesk", NOW)
        self.assertEqual(parsed["image_candidates"], ["https://images.coindesk.com/ghana.jpg"])

    def test_exact_same_news_still_deduplicated(self):
        c = story()
        state = {"sent": {}}
        digest.mark_sent(state, c, 901, NOW)
        self.assertTrue(digest.already_sent(c["main"], state))

    def test_photo_is_not_fabricated_from_generic_poster(self):
        with mock.patch.object(media, "fetch_photo", return_value=None), \
             mock.patch.object(media, "from_article_og", return_value=[]):
            self.assertIsNone(media.photo_for(story()))


if __name__ == "__main__":
    import unittest
    unittest.main()
