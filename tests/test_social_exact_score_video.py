"""Safety tests for the independent Dixon-Coles social video pipeline."""
import importlib.util
import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SocialExactVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.render = load("create_social_exact_score_video")
        cls.publish = load("publish_social_exact_score_video")

    def test_safe_layout_does_not_overlap_last_score_card(self):
        self.render.check_layout()
        x, y, w, h = self.render.VIDEO_BOX
        assert self.render.CTA_BOX[1] > y + (1145/1280) * h + 25
        assert self.render.CTA_BOX[2] <= 920
        assert self.render.CTA_BOX[3] <= 1570

    def test_overlay_contains_correct_telegram_account(self):
        from PIL import Image
        self.assertEqual(self.render.CTA_LINES, (
            "Rejoins-nous sur Telegram pour plus de coupons",
            "Compte Telegram : Mr XPRONOS",
            "@mr_xpronos",
        ))
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "overlay.png"
            self.render.make_cta(path)
            with Image.open(path) as im:
                self.assertEqual(im.size, (1080, 1920))
                self.assertEqual(im.mode, "RGBA")
                self.assertEqual(im.getpixel((0, 0))[3], 0)
                self.assertNotEqual(im.getpixel((400, 1450))[3], 0)

    def test_ten_real_matches_required(self):
        report = {"date_local_africa_lome": "2026-11-10", "status": "READY",
                  "ready_for_video": True, "selected_count": 10,
                  "selected": [{"id": str(i)} for i in range(10)]}
        storyboard = {"date_local_africa_lome": "2026-11-10",
                      "status": "READY", "ready_for_video": True,
                      "selected_count": 10, "clips": [{"match_id": str(i)} for i in range(10)]}
        self.render.verify_ready(report, storyboard, "2026-11-10")
        report["selected"][1]["id"] = "0"
        with self.assertRaises(ValueError):
            self.render.verify_ready(report, storyboard, "2026-11-10")
        report["selected"][1]["id"] = "1"
        storyboard["ready_for_video"] = False
        with self.assertRaises(ValueError):
            self.render.verify_ready(report, storyboard, "2026-11-10")

    def test_flexible_manifest_and_caption_use_actual_count(self):
        import hashlib
        from datetime import timedelta
        with tempfile.TemporaryDirectory() as folder:
            video=Path(folder)/"video.mp4"
            video.write_bytes(b"V"*100100)
            now=datetime(2026,11,11,20,tzinfo=ZoneInfo("Africa/Lome"))
            manifest={
                "schema":"mrx-dixon-coles-social-flex-v2",
                "publication_mode":"flexible","status":"READY",
                "ready_for_video":True,"target":"2026-11-12",
                "count":4,"telegram_username":"@mr_xpronos",
                "sha256":hashlib.sha256(video.read_bytes()).hexdigest(),
            }
            self.assertEqual(self.publish.validate_manifest(manifest,video,now),
                             "2026-11-12")
            title,desc,caption=self.publish.build_copy("2026-11-12",4)
            self.assertIn("4 scores exacts",title)
            self.assertIn("4 rencontres",desc)
            self.assertIn("4 scores exacts",caption)
            manifest["publication_mode"]="strict"
            with self.assertRaises(ValueError):
                self.publish.validate_manifest(manifest,video,now)
            manifest["publication_mode"]="flexible"
            manifest["count"]=11
            with self.assertRaises(ValueError):
                self.publish.validate_manifest(manifest,video,now)

    def test_flexible_renderer_verifier_refuses_mismatched_clip_counts(self):
        report={"date_local_africa_lome":"2026-11-12","status":"READY",
                "ready_for_video":True,"selected_count":4,
                "publication_mode":"flexible",
                "selected":[{"id":str(i)} for i in range(4)]}
        video={"date_local_africa_lome":"2026-11-12","status":"READY",
               "ready_for_video":True,"selected_count":4,
               "publication_mode":"flexible",
               "clips":[{"match_id":str(i)} for i in range(4)]}
        self.render.verify_ready(report,video,"2026-11-12",
                                 publication_mode="flexible")
        with self.assertRaises(ValueError):
            self.render.verify_ready(report,video,"2026-11-12",
                                     publication_mode="strict")
        video["clips"].pop()
        with self.assertRaises(ValueError):
            self.render.verify_ready(report,video,"2026-11-12",
                                     publication_mode="flexible")

    def test_publisher_refuses_wrong_day_or_video_hash(self):
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            video = Path(t) / "video.mp4"
            video.write_bytes(b"X" * 100100)
            manifest = {"schema": "mrx-dixon-coles-social-top10-v1",
                        "target": "2026-11-10", "status": "READY",
                        "ready_for_video": True, "count": 10,
                        "telegram_username": "@mr_xpronos",
                        "sha256": hashlib.sha256(video.read_bytes()).hexdigest()}
            now = datetime(2026, 11, 9, 20, tzinfo=ZoneInfo("Africa/Lome"))
            self.assertEqual(self.publish.validate_manifest(manifest, video, now), "2026-11-10")
            manifest["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                self.publish.validate_manifest(manifest, video, now)
            manifest["sha256"] = hashlib.sha256(video.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                self.publish.validate_manifest(manifest, video,
                    datetime(2026, 11, 10, 20, tzinfo=ZoneInfo("Africa/Lome")))

    def test_copy_is_social_only_and_not_guaranteed(self):
        title, description, caption = self.publish.build_copy("2026-11-10")
        self.assertIn("10 scores exacts", title)
        self.assertIn("@mr_xpronos", caption)
        self.assertIn("pas de résultat garanti", caption)
        self.assertIn("Telegram", description)
        self.assertEqual(self.publish.DEFAULT_PLATFORMS,
                         "facebook,youtube,instagram,threads,bluesky")

if __name__ == "__main__":
    unittest.main()
