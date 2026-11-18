"""No-network checks for RSS publication volume and link-free Telegram format."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import actu_foot_d1_news as pub

NOW = datetime(2026, 11, 18, 9, 37, tzinfo=timezone.utc)


class ActuFootRssFormatTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        relative = "assets/images/footnews/test.jpg"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 80), "blue").save(path)
        self.path = path
        self.mock_root = patch.object(pub, "ROOT", self.root)
        self.mock_root.start()
        self.addCleanup(self.mock_root.stop)
        self.story = {
            "slug": "news-a", "title": "ACTU FOOT | Un nouveau titre",
            "content": "Voici le résumé réellement fourni par le flux RSS. "
                       "Il contient tous les faits disponibles ici.",
            "summary": "Résumé très court.",
            "telegram_summary": "Résumé trop court.",
            "category": "Mercato",
            "source": "Foot Mercato",
            "published": (NOW - timedelta(minutes=25)).isoformat(),
            "link": "https://example.org/news",
            "image": "assets/images/footnews/test.jpg",
            "image_origin": "source",
        }

    def test_photo_caption_begins_with_actual_headline_and_has_no_links_or_buttons(self):
        post = Mock(return_value=345)
        with patch.object(pub, "post_photo", post):
            result = pub.send_article(Mock(), "token", "-10042", self.story, self.path, self.story["link"])
        self.assertEqual(result, 345)
        caption = post.call_args.args[5]
        self.assertTrue(caption.startswith("<b>Un nouveau titre</b>"))
        self.assertIn("tous les faits disponibles", caption)
        self.assertNotIn("Résumé très court", caption)
        self.assertTrue(caption.endswith("<i>Catégorie : Mercato\nSource : Foot Mercato</i>"))
        self.assertNotIn("https://", caption)
        self.assertNotIn("Lire l", caption)
        self.assertIsNone(post.call_args.args[6])

    def test_long_rss_description_is_delivered_in_followup_text_without_links(self):
        story = {
            **self.story,
            "content": "Détail réellement publié dans le RSS. " * 35
                       + "Plus de contexte en fin d'article https://example.org/full.",
        }
        photo = Mock(return_value=444)
        followup = Mock(return_value=445)
        with patch.object(pub, "post_photo", photo), patch.object(pub, "post_text", followup):
            self.assertEqual(pub.send_article(Mock(), "token", "-10042", story, self.path, story["link"]), 444)
        self.assertGreaterEqual(followup.call_count, 1)
        messages = " ".join(call.args[3] for call in followup.call_args_list)
        self.assertIn("Plus de contexte en fin d'article", messages)
        self.assertIn("Source : Foot Mercato", messages)
        self.assertNotIn("https://", messages)
        self.assertNotIn("Lire l", messages)
        self.assertIsNone(photo.call_args.args[6])

    def test_twice_hourly_dispatchs_two_unique_articles(self):
        second = {**self.story, "slug": "news-b", "title": "Deuxième titre"}
        ledger = Mock()
        ledger.rows.return_value = []
        ledger.claim.return_value = True
        with patch.object(pub, "send_article", side_effect=[100, 101]) as sending:
            report = pub.dispatch([self.story, second], NOW, dry_run=False,
                                  token="token", chat="-10042", ledger=ledger, session=Mock())
        self.assertEqual(report["sent"], 2)
        self.assertEqual(sending.call_count, 2)
        self.assertEqual(ledger.mark.call_count, 6)

    def test_daily_quota_blocks_publication(self):
        ledger = Mock()
        ledger.rows.return_value = [
            {"ref_id": f"-10042:{i:02d}"} for i in range(pub.MAX_POSTS_PER_DAY)
        ]
        with patch.object(pub, "send_article", side_effect=AssertionError("sent")):
            report = pub.dispatch([self.story], NOW, dry_run=False,
                                  token="token", chat="-10042", ledger=ledger, session=Mock())
        self.assertEqual(report["sent"], 0)
        self.assertTrue(report["daily_limit_reached"])

    def test_generated_minor_article_rejected_but_verified_major_banner_allowed(self):
        article = {**self.story, "image_origin": "generated_fallback"}
        self.assertEqual(pub.select_stories([article], NOW), [])
        article["editorial_score"] = 4
        self.assertEqual(len(pub.select_stories([article], NOW)), 1)

    def test_http_urls_removed_even_inside_rss_body(self):
        story = {
            **self.story,
            "title": "Un titre https://example.org/title",
            "content": "Information [originale](https://example.org/item) et www.example.org/test",
        }
        title, body, category, source = pub.story_parts(story)
        self.assertEqual(title, "Un titre")
        self.assertEqual(body, "Information originale et")
        self.assertEqual(category, "Mercato")
        self.assertEqual(source, "Foot Mercato")


if __name__ == "__main__":
    unittest.main()
