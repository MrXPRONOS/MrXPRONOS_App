"""Offline T04 round-trip tests. Synthetic data only; NEVER open production D1."""
import importlib.util
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "cinex_backup_crypto.py"
spec = importlib.util.spec_from_file_location("cinex_backup_crypto", SOURCE)
crypto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crypto)

DUMP = b"""BEGIN TRANSACTION;
CREATE TABLE channels(id INTEGER PRIMARY KEY,title TEXT);
CREATE TABLE cine_series_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER);
CREATE TABLE cine_owner_vault(source_chat_id TEXT,source_message_id INTEGER,owner_chat_id INTEGER);
INSERT INTO channels VALUES(1,'Test');
INSERT INTO cine_series_jobs VALUES(10,12345678);
INSERT INTO cine_owner_vault VALUES('-100456789321',22,8765432);
COMMIT;
"""


class BackupCryptoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.private = X25519PrivateKey.generate()
        self.other_private = X25519PrivateKey.generate()
        self.private_path = self.base / "recovery.pem"
        self.public_path = self.base / "recipient.txt"
        self.sql_path = self.base / "snapshot.sql"
        self.archive_path = self.base / "backup.enc"
        self.private_path.write_bytes(self.private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ))
        import base64
        pub = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.public_path.write_text(
            "x25519:" + base64.urlsafe_b64encode(pub).decode().rstrip("=") + "\n",
            encoding="utf8"
        )
        self.sql_path.write_bytes(DUMP)

    def call(self, *args):
        return subprocess.run(
            [sys.executable, str(SOURCE), *map(str, args)],
            capture_output=True, text=True, check=False
        )

    def encrypt(self):
        r = self.call("encrypt", "--sql", self.sql_path,
                      "--public-key", self.public_path, "--out", self.archive_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.archive_path.is_file())
        self.assertTrue(self.archive_path.read_bytes().startswith(crypto.MAGIC))

    def test_encrypted_full_snapshot_decrypts_to_matching_local_database(self):
        self.encrypt()
        raw = self.archive_path.read_bytes()
        self.assertNotIn(b"12345678", raw)
        self.assertNotIn(b"cine_owner_vault", raw)
        self.assertNotIn(b"-100456789321", raw)
        out = self.base / "restored.sqlite"
        r = self.call("restore-local", "--archive", self.archive_path,
                      "--private-key", self.private_path, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with sqlite3.connect(out) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT telegram_chat_id FROM cine_series_jobs").fetchone()[0], 12345678)
            self.assertEqual(db.execute("SELECT owner_chat_id FROM cine_owner_vault").fetchone()[0], 8765432)
        again = self.call("restore-local", "--archive", self.archive_path,
                          "--private-key", self.private_path, "--out", out)
        self.assertNotEqual(again.returncode, 0, "Refuse overwriting existing databases")
        self.assertIn("T04_BACKUP_ERROR", again.stderr)

    def test_ciphertext_tamper_fails_closed(self):
        self.encrypt()
        blob = bytearray(self.archive_path.read_bytes())
        blob[-1] ^= 0x20
        self.archive_path.write_bytes(blob)
        result = self.call("verify-local", "--archive", self.archive_path,
                           "--private-key", self.private_path)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("12345678", result.stderr)

    def test_wrong_private_key_refused(self):
        self.encrypt()
        other = self.base / "other.pem"
        other.write_bytes(self.other_private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ))
        result = self.call("restore-local", "--archive", self.archive_path,
                           "--private-key", other, "--out", self.base / "bad.sqlite")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / "bad.sqlite").exists())

    def test_incomplete_or_corrupted_export_is_rejected_before_upload(self):
        self.sql_path.write_text("CREATE TABLE temporary_notes(x TEXT);", encoding="utf8")
        bad = self.call("encrypt", "--sql", self.sql_path,
                        "--public-key", self.public_path, "--out", self.archive_path)
        self.assertNotEqual(bad.returncode, 0)
        self.assertFalse(self.archive_path.exists())

    def test_backup_is_private_key_only_and_never_restores_cloudflare_directly(self):
        workflow = (ROOT.parent / ".github" / "workflows" / "cinex-t04-backup.yml").read_text()
        self.assertIn("upload-artifact@v4", workflow)
        self.assertIn("retention-days: 90", workflow)
        self.assertIn("d1 export cinecanaux-directory --remote", workflow)
        self.assertIn("path: ${{ runner.temp }}/cinex-t04-sealed/backup.enc", workflow)
        self.assertNotIn("--private-key", workflow)
        source = SOURCE.read_text()
        self.assertNotIn("wrangler d1 execute", source)
        self.assertNotIn("CLOUDFLARE_API_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
