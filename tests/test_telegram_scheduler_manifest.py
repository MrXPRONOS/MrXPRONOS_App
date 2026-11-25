"""Offline validation: no Telegram/DB/network credentials."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telegram_scheduler.manifest import load_manifest, queue_counts

NOW = datetime(2026, 11, 25, 9, tzinfo=timezone.utc)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/"photo.png").write_bytes(b"pngplaceholder")

    def write(self, posts, hours=168):
        path = self.root/"posts.json"
        path.write_text(json.dumps({"horizon_hours":hours, "posts":posts}),encoding="utf8")
        return path

    def row(self, **overrides):
        item={"peer":-100333, "at":(NOW+timedelta(days=1)).isoformat(),
              "key":"promo:wednesday", "kind":"image", "file":"photo.png","text":"Approved link"}
        item.update(overrides)
        return item

    def test_weekly_media(self):
        hours, posts=load_manifest(self.write([self.row()]), now=NOW,root=self.root)
        self.assertEqual(hours,168)
        self.assertEqual(queue_counts(posts)[-100333],1)

    def test_reject_stale_slot(self):
        with self.assertRaises(ValueError):
            load_manifest(self.write([self.row(at=NOW.isoformat())]),now=NOW,root=self.root)

    def test_reject_outside_horizon(self):
        with self.assertRaises(ValueError):
            load_manifest(self.write([self.row(at=(NOW+timedelta(days=7)).isoformat())]),now=NOW,root=self.root)

    def test_reject_non_utc_naive(self):
        with self.assertRaises(ValueError):
            load_manifest(self.write([self.row(at="2026-11-26T10:00:00")]),now=NOW,root=self.root)

    def test_reject_file_traversal(self):
        with self.assertRaises(ValueError):
            load_manifest(self.write([self.row(file="../../etc/passwd")]),now=NOW,root=self.root)

    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):
            load_manifest(self.write([self.row(),self.row()]),now=NOW,root=self.root)

    def test_text_not_media(self):
        with self.assertRaises(ValueError):
            load_manifest(self.write([self.row(kind="text")]),now=NOW,root=self.root)

    def test_cannot_publish_without_manifest(self):
        with self.assertRaises(ValueError):
            load_manifest(self.root/"does-not-exist.json",now=NOW,root=self.root)
