"""CinéX GitHub file backup: synthetic image, catalogue and video fixtures only."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "cinex_github_files_backup.py"
spec = importlib.util.spec_from_file_location("github_assets", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GitHubFileBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "repo"
        self.root.mkdir()
        for name in ("telegram-film-relay/state/anime_catalog.json",
                     "telegram-film-relay/config/channels.json",
                     "telegram-film-relay/assets/promotions/poster.jpg",
                     "cinecanaux/assets/avatars/bot.webp",
                     "cinecanaux/assets/safe_trailer.mp4"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("synthetic-" + name).encode("utf-8"))
        (self.root / "secrets").mkdir()
        (self.root / "secrets/private.pem").write_text("SHOULD_NOT_BE_EXPORTED")
        self.private = X25519PrivateKey.generate()
        self.other = X25519PrivateKey.generate()
        self.archive = base / "github.enc"
        self.restore = base / "restored"

    def pack(self):
        blob, manifest = module.seal(self.root, self.private.public_key())
        module.write_private_file(self.archive, blob)
        return manifest

    def test_private_round_trip_and_integrity(self):
        original = self.pack()
        self.assertEqual(module.summary(original)["video_files"], 1)
        self.assertEqual(len(original["items"]), 5)
        self.assertEqual(self.archive.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(b"synthetic", self.archive.read_bytes())
        self.assertNotIn(b"SHOULD_NOT_BE_EXPORTED", self.archive.read_bytes())
        restored = module.unseal(self.archive.read_bytes(), self.private)
        checked = module.restore_private(restored, self.restore)
        self.assertEqual(checked["items"], original["items"])
        for row in checked["items"]:
            self.assertEqual(
                (self.restore / row["path"]).read_bytes(),
                (self.root / row["path"]).read_bytes()
            )
        self.assertFalse((self.restore / "secrets/private.pem").exists())
        with self.assertRaises(ValueError):
            module.restore_private(restored, self.restore)  # no overwrites

    def test_wrong_key_fails_closed(self):
        self.pack()
        with self.assertRaises(ValueError):
            module.unseal(self.archive.read_bytes(), self.other)
        self.assertFalse(self.restore.exists())

    def test_modified_archive_fails_closed(self):
        self.pack()
        original = bytearray(self.archive.read_bytes())
        original[-1] ^= 1
        with self.assertRaises(ValueError):
            module.unseal(bytes(original), self.private)
        self.assertFalse(self.restore.exists())

    def test_unlisted_media_and_sensitive_paths_are_excluded(self):
        self.pack()
        paths = [row["path"] for row in module.seal(
            self.root, self.private.public_key()
        )[1]["items"]]
        self.assertTrue(all(module.selected_path(name) for name in paths))
        for candidate in ("../../secret.json", "/tmp/film.mp4",
                          "cinecanaux/assets/../private.pem", ".github/keys.pem",
                          "telegram-film-relay/config/token.txt"):
            self.assertFalse(module.selected_path(candidate))

    def test_no_video_sources_are_explicitly_reported(self):
        (self.root / "cinecanaux/assets/safe_trailer.mp4").unlink()
        _, manifest = module.seal(self.root, self.private.public_key())
        self.assertEqual(module.summary(manifest)["video_files"], 0)
        self.assertEqual(len(manifest["items"]), 4)

    def test_symlink_and_excessive_payloads_refused(self):
        link = self.root / "cinecanaux/assets/linked.jpg"
        try:
            link.symlink_to(self.root / "cinecanaux/assets/avatars/bot.webp")
        except (NotImplementedError, OSError):
            self.skipTest("symlinks are unavailable")
        with self.assertRaises(ValueError):
            module.discover(self.root)
        link.unlink()
        large = self.root / "cinecanaux/assets/verybig.mp4"
        with open(large, "wb") as fp:
            fp.truncate(module.MAX_ONE + 1)
        with self.assertRaises(ValueError):
            module.discover(self.root)

    def test_archive_checksum_enforced_after_decryption(self):
        _, manifest = module.seal(self.root, self.private.public_key())
        self.assertTrue(all(row["sha256"] for row in manifest["items"]))
        self.assertTrue(module.selected_path("telegram-film-relay/assets/sample.webm"))
        self.assertFalse(module.selected_path("cinecanaux/worker.mjs"))


if __name__ == "__main__":
    unittest.main()
