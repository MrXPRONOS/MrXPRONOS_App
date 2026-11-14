"""Checks for the social exact-score Telegram teaser; no network, secrets or posts."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import social_exact_score_telegram_teaser as teaser


def fixture():
    m = {"target": "2026-11-15", "count": 2, "ready_for_video": True,
         "status": "READY", "publication_mode": "flexible", "sha256": "a" * 64,
         "match_ids": ["m1", "m2"]}
    p = {"date_local_africa_lome": "2026-11-15", "ready_for_video": True,
         "selected": [{"id": "m1", "home": "AFC Alpha", "away": "Beta United",
                       "league": "Test League", "forecast": {"most_likely_score": "2:1"}},
                      {"id": "m2", "home": "City", "away": "Sporting",
                       "league": "Test League", "forecast": {"most_likely_score": "0:1"}}]}
    r = [{"platform": "youtube", "ok": True, "data": {"id": "aBcdEfGh123"},
          "target": m["target"], "count": m["count"],
          "publication_mode": "flexible", "video_sha256": m["sha256"]},
         {"platform": "facebook", "ok": False, "data": {"id": "12345"},
          "target": m["target"], "count": m["count"],
          "publication_mode": "flexible", "video_sha256": m["sha256"]}]
    return m, p, r


class TeaserTests(unittest.TestCase):
    def test_sanitized_verified_links_only(self):
        m, p, r = fixture()
        self.assertEqual(len(teaser.check_inputs(m, p)), 2)
        self.assertEqual(teaser.links_from_receipts(r, m),
                         {"youtube": "https://www.youtube.com/shorts/aBcdEfGh123"})
        self.assertEqual(len(teaser.keyboard(teaser.links_from_receipts(r, m))["inline_keyboard"]), 1)
        r[0]["video_sha256"] = "wrong"
        self.assertEqual(teaser.links_from_receipts(r, m), {})

    def test_no_profile_or_unsafe_redirect(self):
        self.assertIsNone(teaser.safe_link("youtube", "https://youtube.com/@mrxpronos"))
        self.assertIsNone(teaser.safe_link("youtube", "http://youtube.com/shorts/aBcdEfGh123"))
        self.assertIsNone(teaser.safe_link("instagram", "https://evil.example/reel/abc"))
        self.assertIsNone(teaser.safe_link("threads", "https://threads.net/@a"))
        self.assertIsNone(teaser.safe_link("bluesky", "https://bsky.app/profile/me"))
        self.assertIsNotNone(teaser.safe_link("facebook", "https://www.facebook.com/watch/?v=123456"))

    @patch.object(teaser, "logo_image", return_value=None)
    def test_masked_image_does_not_include_prediction_text(self, _):
        m, p, r = fixture()
        p["selected"][0]["forecast"]["most_likely_score"] = "SECRET_9_8"
        with tempfile.TemporaryDirectory() as folder:
            path = teaser.render(Path(folder) / "teaser.png", m, p, test=True)
            from PIL import Image
            image = Image.open(path)
            self.assertEqual(image.size, (1200, 1600))
            self.assertGreater(path.stat().st_size, 10_000)
        caption = teaser.make_caption(m, {"youtube": "https://youtube.com/shorts/aBcdEfGh123"}, test=True)
        self.assertNotIn("SECRET_9_8", caption)
        self.assertNotIn("2:1", caption)

    def test_refuse_mismatched_ids(self):
        m, p, _ = fixture()
        m["match_ids"] = ["m2", "m1"]
        with self.assertRaises(ValueError):
            teaser.check_inputs(m, p)


if __name__ == "__main__":
    unittest.main()
