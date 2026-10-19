"""Snapchat Spotlight packaging safety and real ffmpeg smoke tests."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import snapchat_spotlight_pack as snap


class SpotlightPackagingTests(unittest.TestCase):
    def test_source_rejects_external_urls(self):
        for value in (
            "http://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object/public/videos/snapchat/a.mp4",
            "https://evil.example/snapchat/a.mp4",
            "https://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object/public/videos/shorts/a.mp4",
            "https://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object/public/videos/snapchat/../shorts/a.mp4",
            "https://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object/public/videos/snapchat/a.mp4?token=fake",
        ):
            with self.subTest(value=value):
                with self.assertRaises(snap.PreparationError):
                    snap.parse_source_url(value)

    def test_only_snapchat_public_storage_is_accepted(self):
        allowed = "https://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object/public/videos/snapchat/match-news.mp4"
        self.assertEqual(snap.parse_source_url(allowed), allowed)

    def test_betting_metadata_rejected(self):
        for value in ("1XBET promotion", "Code promo foot", "Analyse casino", "https://mrxpronos.test/"):
            with self.subTest(value=value):
                with self.assertRaises(snap.PreparationError):
                    snap.check_title(value)
        self.assertEqual(snap.check_title("Résultats du football africain"),
                         "Résultats du football africain")

    def test_review_is_mandatory_before_touching_source(self):
        with self.assertRaisesRegex(snap.PreparationError, "Revue humaine"):
            snap.prepare(Path("missing.mp4"), Path("output"), "Actualité football", "")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "ffmpeg/ffprobe required for integration test")
    def test_real_video_produces_ready_mp4_but_never_publishes(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "football_clean.mp4"
            out = Path(root) / "snapchat"
            cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
                   "-f", "lavfi", "-i", "color=c=blue:s=540x960:r=12:d=6",
                   "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                   "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=90)
            manifest = snap.prepare(src, out, "Foot : résultats de la journée",
                                    snap.REVIEW_CONFIRMATION)
            self.assertEqual(manifest["status"], "READY_FOR_HUMAN_UPLOAD_ONLY")
            self.assertIs(manifest["published"], False)
            target = out / manifest["video_filename"]
            self.assertTrue(target.is_file())
            self.assertEqual(manifest["video_sha256"], snap.sha256_file(target))
            self.assertEqual(snap.video_metadata(target)["width"], 1080)
            self.assertEqual(snap.video_metadata(target)["height"], 1920)
            self.assertTrue((out / "LIRE_AVANT_PUBLICATION.txt").is_file())
            self.assertEqual(json.loads((out / "snapchat_manifest.json").read_text())["published"],
                             False)


if __name__ == "__main__":
    unittest.main()
