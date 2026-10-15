import os
import unittest
from unittest.mock import Mock, patch

import fetch_foot_news as news


class EspnNewsCorroborationTests(unittest.TestCase):
    def test_espn_corroboration_matches_entities_and_preserves_metadata(self):
        index = [{
            "id": "50171789",
            "title": "Transfer rumors: Barcelona and Real Madrid scout Erling Haaland",
            "url": "https://www.espn.com/soccer/story/_/id/50171789/example",
            "tokens": news._verification_tokens(
                "Transfer rumors: Barcelona and Real Madrid scout Erling Haaland"
            ),
            "published": "2026-10-13T08:09:42Z",
            "topics": ["soccer transfers"],
            "teams": ["Barcelona", "Real Madrid", "Manchester City"],
            "athletes": ["Erling Haaland"],
            "leagues": ["English Premier League", "Spanish LALIGA"],
            "is_transfer": True,
        }]
        found = news.espn_corroboration(
            "Mercato : le Real Madrid et le Barça surveillent Erling Haaland",
            index,
        )
        self.assertEqual(found["provider"], "ESPN")
        self.assertTrue(found["is_transfer"])
        self.assertIn("Erling Haaland", found["athletes"])
        self.assertIn("Real Madrid", found["teams"])
        self.assertGreater(found["score"], 0)

    def test_espn_corroboration_rejects_unrelated_story(self):
        index = [{
            "id": "1",
            "title": "Arsenal win in London",
            "url": "https://www.espn.com/soccer/story/_/id/1/example",
            "tokens": news._verification_tokens("Arsenal win in London"),
            "published": "",
            "topics": [],
            "teams": ["Arsenal"],
            "athletes": [],
            "leagues": ["Premier League"],
            "is_transfer": False,
        }]
        self.assertEqual(
            news.espn_corroboration("Le Sénégal dévoile sa liste pour la CAN", index),
            {},
        )


class PublicNewsSnapshotTests(unittest.TestCase):
    def test_snapshot_prefere_image_source_distante(self):
        rows = news.public_snapshot_records([{
            "title": "Test",
            "image": "assets/images/footnews/test.webp",
            "source_image": "https://cdn.example.org/test.jpg",
        }])
        self.assertEqual(rows[0]["image"], "https://cdn.example.org/test.jpg")

    @patch.dict(os.environ, {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service",
    }, clear=True)
    @patch("fetch_foot_news.requests.post")
    def test_persist_snapshot_upsert_latest(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        post.return_value = response
        ok = news.persist_public_news_snapshot([{
            "title": "Test",
            "image": "assets/images/footnews/test.webp",
            "source_image": "https://cdn.example.org/test.jpg",
        }])
        self.assertTrue(ok)
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertTrue(url.endswith("/rest/v1/actu_foot_news_snapshot"))
        self.assertEqual(kwargs["json"]["id"], "latest")
        self.assertEqual(kwargs["json"]["payload"][0]["image"], "https://cdn.example.org/test.jpg")


if __name__ == "__main__":
    unittest.main()
