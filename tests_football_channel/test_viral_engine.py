import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bsd"))

import football_viral_engine as viral
import football_channel as channel


NOW = datetime(2026, 10, 13, 19, 30, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, payload=None, content=b"", content_type="application/json", status=200):
        self._payload = payload or {"ok": True, "result": {"message_id": 91}}
        self.content = content
        self.headers = {"content-type": content_type}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload=None):
        self.payload = payload
        self.posts = []

    def get(self, url, **kwargs):
        return FakeResponse(self.payload or {})

    def post(self, url, data=None, files=None, timeout=None):
        self.posts.append({"url": url, "data": data, "files": files, "timeout": timeout})
        return FakeResponse()


class ViralEngineTests(unittest.TestCase):
    def test_commons_rejects_nonfree_and_accepts_cc(self):
        payload = {
            "query": {
                "pages": {
                    "1": {
                        "title": "File:Bad football.jpg",
                        "imageinfo": [{
                            "mime": "image/jpeg",
                            "thumburl": "https://example.com/bad.jpg",
                            "extmetadata": {
                                "LicenseShortName": {"value": "Fair use"},
                                "NonFree": {"value": "True"},
                            },
                        }],
                    },
                    "2": {
                        "title": "File:Football stadium pitch.jpg",
                        "imageinfo": [{
                            "mime": "image/jpeg",
                            "thumburl": "https://example.com/good.jpg",
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                                "Artist": {"value": "Jane Doe"},
                                "NonFree": {"value": "False"},
                                "Restrictions": {"value": ""},
                            },
                        }],
                    },
                }
            }
        }
        media = viral.fetch_commons_image(FakeSession(payload), "football stadium")
        self.assertEqual(media["provider"], "Wikimedia Commons")
        self.assertEqual(media["credit"], "Jane Doe")
        self.assertIn("CC BY-SA", media["license"])
        self.assertIn("Football_stadium_pitch", media["page_url"])

    @patch("football_viral_engine._licensed_media_for_payload", return_value={})
    def test_match_fou_has_priority(self, _media):
        events = [{
            "id": 10,
            "event_date": (NOW - timedelta(hours=2)).isoformat(),
            "home_team": {"name": "Arsenal"},
            "away_team": {"name": "Chelsea"},
            "home_score": 4,
            "away_score": 3,
            "league_name": "Premier League",
            "status": "finished",
        }]
        payload = viral.build_viral_payload(
            events, [], FakeSession(), NOW, lambda _: 100
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload["kind"], "match_fou")
        self.assertEqual(payload["score"], "4 - 3")
        self.assertIn("7 buts", payload["caption"])

    @patch("football_viral_engine._licensed_media_for_payload", return_value={"url": "https://example.com/generic.jpg"})
    def test_recent_news_used_when_no_spectacular_match(self, _media):
        news = [{
            "slug": "news-x",
            "title": "Une grande décision vient d'être annoncée",
            "summary_short": "Le club a confirmé officiellement sa décision.",
            "published": (NOW - timedelta(hours=1)).isoformat(),
            "source": "RFI",
            "site_url": "https://example.com/news-x",
            "editorial_score": 5,
        }]
        payload = viral.build_viral_payload([], news, FakeSession(), NOW, lambda _: 0)
        self.assertEqual(payload["kind"], "news_pulse")
        self.assertEqual(payload["data_source"], "RFI")
        self.assertEqual(payload["media"], {})
        _media.assert_not_called()

    def test_long_news_title_is_trimmed_and_fits_four_lines(self):
        canvas = Image.new("RGB", (viral.W, viral.H), "black")
        draw = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(canvas)
        title = (
            "Gianni Infantino baigne dans un nouveau scandale à plusieurs millions "
            "de dollars avec une formulation volontairement très longue pour tester "
            "la sécurité typographique du renderer viral"
        )
        trimmed = viral._smart_trim(title, 150)
        font, lines, size = viral._fit_text_layout(
            draw,
            trimmed,
            max_width=522,
            max_height=178,
            max_lines=4,
            max_size=38,
            min_size=25,
            bold=True,
            gap=10,
        )
        self.assertLessEqual(len(trimmed), 150)
        self.assertLessEqual(len(lines), 4)
        self.assertGreaterEqual(size, 25)
        for line in lines:
            box = draw.textbbox((0, 0), line, font=font)
            self.assertLessEqual(box[2] - box[0], 522)

    def test_news_animation_renders_on_brand_background_without_summary_wall(self):
        payload = {
            "kind": "news_pulse",
            "title": "Gianni Infantino baigne dans un nouveau scandale à plusieurs millions de dollars !",
            "summary": "Ce résumé doit rester dans la légende Telegram et non envahir la vidéo.",
            "data_source": "The Times",
            "media": {"url": "https://example.com/irrelevant.jpg"},
        }
        session = FakeSession()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "viral-news.gif"
            viral.render_animation(payload, output, session)
            self.assertTrue(output.is_file())
            with Image.open(output) as image:
                self.assertEqual(image.size, (viral.W, viral.H))
                self.assertTrue(getattr(image, "is_animated", False))
        # Le renderer news ne doit même pas télécharger le fond générique.
        self.assertEqual(session.posts, [])

    def test_animation_renders_without_external_media(self):
        payload = {
            "kind": "match_fou",
            "home": "Arsenal",
            "away": "Chelsea",
            "score": "4 - 3",
            "league": "Premier League",
            "media": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "viral.gif"
            viral.render_animation(payload, output, FakeSession())
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 1000)
            self.assertLess(output.stat().st_size, 14_000_000)
            with Image.open(output) as image:
                self.assertTrue(getattr(image, "is_animated", False))
                self.assertGreaterEqual(getattr(image, "n_frames", 1), 8)
                self.assertEqual(image.size, (viral.W, viral.H))

    @patch("football_channel.build_viral_payload")
    def test_channel_builds_viral_publication_with_credit(self, build):
        build.return_value = {
            "kind": "stat_pulse",
            "key": "viral-stat:test",
            "caption": "📊 <b>STAT QUI CLAQUE</b>",
            "target_url": "https://example.com/more",
            "media": {
                "provider": "Wikimedia Commons",
                "credit": "Jane Doe",
                "license": "CC BY-SA 4.0",
                "page_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
            },
        }
        post = channel.viral_publication([], [], FakeSession(), NOW)
        self.assertIsNotNone(post)
        self.assertEqual(post.category, "viral")
        self.assertIn("Jane Doe", post.text)
        self.assertIsNotNone(post.animation_payload)
        self.assertEqual(len(post.keyboard["inline_keyboard"]), 2)

    def test_telegram_animation_sender(self):
        session = FakeSession()
        with tempfile.TemporaryDirectory() as directory:
            gif = Path(directory) / "tiny.gif"
            frames = [
                Image.new("P", (64, 64), color=i * 15)
                for i in range(3)
            ]
            frames[0].save(
                gif, save_all=True, append_images=frames[1:], duration=120, loop=0
            )
            message_id = channel.post_animation(
                session, "token", "@channel", gif,
                "<b>Animation test</b>", {"inline_keyboard": []},
                timeout=30, mime="image/gif",
            )
        self.assertEqual(message_id, 91)
        self.assertTrue(session.posts[-1]["url"].endswith("/sendAnimation"))
        self.assertEqual(session.posts[-1]["data"]["parse_mode"], "HTML")


if __name__ == "__main__":
    unittest.main()
