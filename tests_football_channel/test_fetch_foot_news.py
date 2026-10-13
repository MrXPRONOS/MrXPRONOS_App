import unittest

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


if __name__ == "__main__":
    unittest.main()
