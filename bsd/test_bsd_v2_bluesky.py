"""Tests sans API externe ni publication pour le connecteur Bluesky BSD V2."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from bsd_v2_bluesky import identity, jpeg_bytes, selections


class BlueskyPublicationTests(unittest.TestCase):
    def sample_data(self, *, generated=None, source="bsd"):
        return {
            "source": source,
            "model_version": "bsd-v2-isolated",
            "generated_at": (generated or datetime.now(timezone.utc)).isoformat(),
            "matches": [],
        }

    def test_only_valid_bsd_v2_feed_is_accepted(self):
        now = datetime.now(timezone.utc)
        with self.assertRaises(ValueError):
            selections(self.sample_data(source="legacy"), now)

    def test_stale_bsd_feed_is_not_published(self):
        now = datetime.now(timezone.utc)
        with self.assertRaises(ValueError):
            selections(self.sample_data(generated=now-timedelta(days=3)), now)

    def test_empty_valid_feed_has_no_publications(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(selections(self.sample_data(generated=now), now), [])

    def test_ledger_uses_distinct_kinds_for_single_and_combo(self):
        item = {"id": "42", "date": "2026-10-20",
                "_telegram_selection_ref": "42:HOME_WIN"}
        single = identity("single", item, "mrxpronos.bsky.social")
        combo = identity("combo", item, "mrxpronos.bsky.social")
        self.assertNotEqual(single[0], combo[0])
        self.assertEqual(single[1], "mrxpronos.bsky.social:42:HOME_WIN")
        self.assertEqual(combo[1], "mrxpronos.bsky.social:42")

    def test_image_compressed_below_blue_sky_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.png"
            Image.new("RGB", (1080, 1580), (220, 225, 230)).save(path)
            data, dims = jpeg_bytes(path)
            self.assertLessEqual(len(data), 950_000)
            self.assertEqual(dims, (1080, 1580))


if __name__ == "__main__":
    unittest.main()
