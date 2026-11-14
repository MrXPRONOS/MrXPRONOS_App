"""Checks for the social exact-score Telegram teaser; no network, secrets or posts."""
import sys
import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dixon-coles"))
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

    def test_plain_colored_network_buttons(self):
        links = {
            "youtube": "https://www.youtube.com/shorts/aBcdEfGh123",
            "facebook": "https://www.facebook.com/watch/?v=123456",
            "instagram": "https://www.instagram.com/reel/abc123/",
            "threads": "https://www.threads.net/@brand/post/abc123",
        }
        rows = teaser.keyboard(links)["inline_keyboard"]
        self.assertEqual([b["text"] for row in rows for b in row],
                         ["YouTube", "Facebook", "Instagram", "Threads"])
        self.assertEqual(len(rows), 2)
        buttons = {b["text"]: b for row in rows for b in row}
        self.assertEqual(buttons["YouTube"]["style"], "danger")
        self.assertEqual(buttons["Facebook"]["style"], "primary")
        self.assertEqual(buttons["Instagram"]["style"], "success")
        self.assertEqual(buttons["Threads"]["style"], "success")
        for name in links:
            self.assertEqual(buttons[teaser.LABELS[name]]["url"], links[name])

    def test_test_caption_is_exact_public_caption(self):
        m, p, _ = fixture()
        copy = teaser.make_caption(m, {}, test=True)
        self.assertEqual(copy, teaser.make_caption(m, {}, test=False))
        self.assertEqual(copy, "<b>TOP 2 SCORES EXACTS SUR NOS RÉSEAUX SOCIAUX</b>")
        self.assertNotIn("TEST VISUEL", copy)
        self.assertNotIn("2:1", copy)
        self.assertEqual(teaser.make_caption({"count": 1}, {}),
                         "<b>TOP 1 SCORE EXACT SUR NOS RÉSEAUX SOCIAUX</b>")

    def test_video_template_telegram_restores_title_and_cta_without_old_banner(self):
        from PIL import Image
        from dcscore import video_grid_neon as neon
        from dcscore.video_render import Crest
        crest = Crest(Image.new("RGBA", (38, 38), (240, 220, 70, 255)), True)
        clips = [{"headline": "Home - Away", "display_score": "2-1"}]
        data = {"date_local_africa_lome": "2026-11-15"}
        original = neon.base_frame(data, clips, [(crest, crest)], False)
        minimal = neon.base_frame(data, clips, [(crest, crest)], False,
                                  telegram_minimal=True)
        self.assertGreater(original.getpixel((360, 45))[3], 0)
        # Both stills share the title artwork from the original video.
        self.assertEqual(minimal.getpixel((360, 45)), original.getpixel((360, 45)))
        self.assertGreater(minimal.getpixel((360, 45))[3], 0)
        # A near-opaque navy card protects both text lines from the stadium.
        self.assertEqual(minimal.getpixel((120, 1035)),
                         neon.TELEGRAM_PANEL_BG)
        self.assertNotEqual(neon.TELEGRAM_CTA_TOP, neon.WHITE)
        self.assertNotEqual(neon.TELEGRAM_CTA_BOTTOM, neon.GOLD)
        # Coral-orange arrow has a strong contrast against the navy card.
        self.assertEqual(minimal.getpixel((360, 1078))[:3],
                         neon.TELEGRAM_ARROW[:3])
        self.assertGreater(sum(neon.TELEGRAM_ARROW[:3]) -
                           sum(neon.TELEGRAM_PANEL_BG[:3]), 250)
        # The old lower marketing/banner area remains unused.
        self.assertEqual(minimal.getpixel((360, 1135))[3], 0)
        self.assertGreater(minimal.getpixel((neon.CARD_X[0] + 8,
                                             neon.CARD_Y0 + 8))[3], 0)

    def test_caption_html_enabled_for_real_telegram_photo(self):
        from pathlib import Path
        from unittest.mock import patch, Mock, mock_open
        import json
        token = "secret"
        dest = {"chat_id": -100987654321, "username": "predict_mrxp"}
        confirmation = {"ok": True, "result": {
            "message_id": 1720, "chat": {"id": dest["chat_id"]}}}
        sent = Mock(status_code=200)
        sent.json.return_value = confirmation
        with patch("telegram_test_guard.validate_test_channel",
                   return_value=dest), patch.object(
                   Path, "open", mock_open(read_data=b"png")), patch.object(
                   teaser.requests, "post", return_value=sent) as post_mock:
            msg = teaser.send_test(Path("test.png"),
                                   "<b>TOP 10 SCORES EXACTS SUR NOS RÉSEAUX SOCIAUX</b>",
                                   {"youtube": "https://www.youtube.com/shorts/aBcdEfGh123"},
                                   token=token, chat="@predict_mrxp")
            args, kwargs = post_mock.call_args
        self.assertEqual(msg["message_id"], 1720)
        self.assertEqual(kwargs["data"]["parse_mode"], "HTML")
        self.assertEqual(kwargs["data"]["caption"],
                         "<b>TOP 10 SCORES EXACTS SUR NOS RÉSEAUX SOCIAUX</b>")

    def test_same_dedupe_key_for_claim_and_mark(self):
        import inspect
        source = inspect.getsource(teaser.main)
        self.assertIn("ledger.claim(\"dcscore_social_teaser_test\", TEASER_VERSION", source)
        self.assertIn("ledger.mark(\"dcscore_social_teaser_test\", TEASER_VERSION", source)

    def test_no_profile_or_unsafe_redirect(self):
        self.assertIsNone(teaser.safe_link("youtube", "https://youtube.com/@mrxpronos"))
        self.assertIsNone(teaser.safe_link("youtube", "http://youtube.com/shorts/aBcdEfGh123"))
        self.assertIsNone(teaser.safe_link("instagram", "https://evil.example/reel/abc"))
        self.assertIsNone(teaser.safe_link("threads", "https://threads.net/@a"))
        self.assertIsNone(teaser.safe_link("bluesky", "https://bsky.app/profile/me"))
        self.assertIsNotNone(teaser.safe_link("facebook", "https://www.facebook.com/watch/?v=123456"))

    def test_masked_telegram_uses_original_video_renderer(self):
        m, p, r = fixture()
        clips = []
        for row in p["selected"]:
            score = row["forecast"]["most_likely_score"]
            clips.append({"match_id": row["id"],
                          "headline": row["home"] + " - " + row["away"],
                          "display_score": score,
                          "home_logo_url": None, "away_logo_url": None})
        storyboard = {"date_local_africa_lome": m["target"], "selected_count": 2,
                      "ready_for_video": True, "status": "READY", "clips": clips}
        raw = json.dumps(storyboard).encode("utf-8")
        m["storyboard_sha256"] = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            path = base / "video_payload.json"
            path.write_bytes(raw)
            target = base / "teaser.png"
            # No alternate designs: the imported video renderer MUST create the image.
            with patch("dcscore.video_grid_neon.render_teaser_still") as original:
                original.return_value = {"count": 2, "scores_visible": False}
                teaser.render(target, m, p, storyboard=storyboard,
                              storyboard_path=path, test=True)
                args, kwargs = original.call_args
                self.assertEqual(args[0], storyboard)
                self.assertEqual(args[1], target)
                self.assertTrue(kwargs["require_real_logos"])
            m["storyboard_sha256"] = "f" * 64
            with self.assertRaises(ValueError):
                teaser.render(target, m, p, storyboard=storyboard,
                              storyboard_path=path, test=True)
        caption = teaser.make_caption(m, {}, test=True)
        self.assertNotIn("2:1", caption)

    def test_centering_uses_same_stadium_without_social_safe_zone(self):
        from PIL import Image, ImageDraw
        from dcscore import video_grid_neon as neon
        frame = Image.new("RGBA", (neon.W, neon.H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)
        draw.rectangle((23, 249, 699, 880), fill=(255, 20, 50, 255))
        out = neon.centered_teaser_frame(frame)
        self.assertEqual(out.size, (neon.W, neon.H))
        # The visible coloured rectangle is horizontally centered instead of
        # following ARTWORK_X/ARTWORK_SCALE (the social-video safe zone).
        points = []
        for y in range(neon.H):
            for x in range(neon.W):
                rr, gg, bb, aa = out.getpixel((x, y))
                if rr > 240 and gg < 60 and bb < 90:
                    points.append((x, y))
        self.assertTrue(points)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        self.assertLessEqual(abs((min(xs) + max(xs)) / 2 - neon.W / 2), 1)
        self.assertLessEqual(abs((min(ys) + max(ys)) / 2 - neon.H / 2), 1)

    def test_refuse_mismatched_ids(self):
        m, p, _ = fixture()
        m["match_ids"] = ["m2", "m1"]
        with self.assertRaises(ValueError):
            teaser.check_inputs(m, p)


if __name__ == "__main__":
    unittest.main()
