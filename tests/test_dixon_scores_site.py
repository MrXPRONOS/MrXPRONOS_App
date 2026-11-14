"""Dixon-Coles video -> website: exact, cryptographically linked public scores."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_dixon_scores_site import SCHEMA, export
from scripts.build_public_site import copy_public_dixon_scores


class DixonVideoWebsiteTests(unittest.TestCase):
    def make_case(self, root: Path):
        video = root / "real-video.mp4"
        video.write_bytes(b"\0" * 100001)
        preds_path = root / "predictions.json"
        board_path = root / "video_payload.json"
        row = {
            "id": "fixture:99", "home": "Club A", "away": "Club B",
            "competition_name": "League", "kickoff_utc": "2026-11-15T15:00:00Z",
            "home_logo_url": "https://crests.football-data.org/1.png",
            "away_logo_url": "https://crests.football-data.org/2.png",
            "forecast": {"most_likely_score": "2-1", "most_likely_probability": .142}
        }
        clip = {
            "match_id": row["id"], "headline": "Club A - Club B",
            "kickoff_utc": row["kickoff_utc"], "display_score": "2-1",
            "home_logo_url": row["home_logo_url"], "away_logo_url": row["away_logo_url"]
        }
        prediction = {
            "status": "READY", "ready_for_video": True,
            "date_local_africa_lome": "2026-11-15", "selected_count": 1,
            "publication_mode": "flexible",
            "generated_at_utc": "2026-11-14T20:00:00Z", "selected": [row]
        }
        storyboard = {
            "status": "READY", "ready_for_video": True,
            "date_local_africa_lome": "2026-11-15", "selected_count": 1,
            "publication_mode": "flexible", "clips": [clip]
        }
        preds_path.write_text(json.dumps(prediction), encoding="utf8")
        board_path.write_text(json.dumps(storyboard), encoding="utf8")
        prediction["_source_path"] = str(preds_path)
        storyboard["_source_path"] = str(board_path)
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        manifest = {
            "target": "2026-11-15", "status": "READY", "ready_for_video": True,
            "count": 1, "publication_mode": "flexible",
            "match_ids": ["fixture:99"],
            "predictions_sha256": digest(preds_path),
            "storyboard_sha256": digest(board_path),
            "sha256": digest(video),
            "render_evidence": {
                "real_logo_instances": 2, "placeholder_logo_instances": 0,
                "resolution": "1080x1920"
            }
        }
        return manifest, prediction, storyboard, video

    def test_matching_video_exports_only_public_match_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, prediction, storyboard, video = self.make_case(Path(tmp))
            output = export(manifest, prediction, storyboard, video)
            self.assertEqual(output["schema_version"], SCHEMA)
            self.assertEqual(output["model"], "dixon_coles_video")
            self.assertEqual(output["count"], 1)
            self.assertEqual(output["matches"][0]["score"], "2:1")
            self.assertEqual(output["video_sha256"], manifest["sha256"])
            self.assertNotIn("selected", output)
            self.assertNotIn("forecast", json.dumps(output))
            self.assertNotIn("grouped", json.dumps(output))

    def test_video_or_prediction_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, prediction, storyboard, video = self.make_case(Path(tmp))
            video.write_bytes(b"\1" * 100001)
            with self.assertRaisesRegex(ValueError, "Video production proof"):
                export(manifest, prediction, storyboard, video)
            video.write_bytes(b"\0" * 100001)
            prediction["selected"][0]["forecast"]["most_likely_score"] = "0-1"
            with self.assertRaisesRegex(ValueError, "Score differs"):
                export(manifest, prediction, storyboard, video)

    def test_dated_feed_is_preserved_only_if_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, prediction, storyboard, video = self.make_case(root)
            receipt = export(manifest, prediction, storyboard, video)
            previous = root / "previous" / "dixon-scores-daily"
            previous.mkdir(parents=True)
            (previous / "2026-11-15.json").write_text(json.dumps(receipt), encoding="utf8")
            destination = root / "out"
            copy_public_dixon_scores(destination, root / "previous")
            target = destination / "dixon-scores-daily" / "2026-11-15.json"
            self.assertTrue(target.is_file())
            self.assertEqual(json.loads(target.read_text())["matches"][0]["score"], "2:1")
            broken = deepcopy(receipt)
            broken["matches"][0]["actual_score"] = "2:1"
            (previous / "2026-11-15.json").write_text(json.dumps(broken), encoding="utf8")
            destination2 = root / "out2"
            copy_public_dixon_scores(destination2, root / "previous")
            self.assertFalse((destination2 / "dixon-scores-daily" / "2026-11-15.json").exists())


if __name__ == "__main__":
    unittest.main()
