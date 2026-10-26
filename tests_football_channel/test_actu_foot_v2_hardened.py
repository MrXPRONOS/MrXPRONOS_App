"""V2 hardened validation acceptance scenarios, offline only."""
import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.actu_foot_v2_store import VaultError, encrypt, decrypt, append_audit, validate_records
from scripts.actu_foot_v2_operations import verify_directory
from scripts.actu_foot_v2_validation import validate_domain

TEST_KEY=base64.b64encode(bytes(range(32))).decode()


class HardenedTests(unittest.TestCase):
    def setUp(self):
        pp=patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V1":TEST_KEY})
        pp.start()
        self.addCleanup(pp.stop)

    def test_schema(self):
        for item in (
            {"home_team":"Arsenal","away_team":"Chelsea","state":"invalid"},
            {"home_team":"Arsenal","away_team":"Arsenal"},
            {"home_team":"Arsenal","away_team":"Chelsea","event_date":"2026-10-26"},
            {"home_team":"Arsenal","away_team":"Chelsea","home_score":31},
            {"home_team":"Arsenal","away_team":"Chelsea","api_key":"oops"},
        ):
            with self.subTest(item=item),self.assertRaises(VaultError):
                validate_records("matches",{"fixture1":item})
        validate_records("matches",{"fixture1":{"home_team":"Arsenal",
              "away_team":"Chelsea","event_date":"2026-10-26T14:00:00Z",
              "home_score":2,"away_score":1,"state":"finished"}})

    def test_no_plaintext_credentials(self):
        with self.assertRaises(VaultError):
            encrypt("settings",{"settings":{"access_token":"x"}})
        with self.assertRaises(VaultError):
            encrypt("news",{"item":{"source_url":"http://invalid.example"}})

    def test_audit_chain_must_be_coherent(self):
        entries=append_audit({},"init",{"collection":"matches"})
        serialized=encrypt("audit",entries)
        self.assertEqual(decrypt("audit",serialized)[0],entries)
        broken={k:dict(v) for k,v in entries.items()}
        broken["1"]["entry_hash"]="0"*64
        with self.assertRaises(VaultError):
            from scripts.actu_foot_v2_store import verify_audit
            verify_audit(broken)

    def test_empty_manifest_and_corrupted_archive(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)
            (path/"manifest.json").write_text(json.dumps({
                "format":"actufoot-v2-backup-v2","collections":{}
            }))
            with self.assertRaises(VaultError):
                verify_directory(path)
            payload=encrypt("settings",{"k":{"enabled":True}})
            p=path/"settings.aes.json"
            p.write_text(payload)
            (path/"manifest.json").write_text(json.dumps({
                "format":"actufoot-v2-backup-v2",
                "collections":{"settings":{"filename":"settings.aes.json",
                    "sha256":"0"*64,"generation":1,"key_version":1,"record_count":1}}}))
            with self.assertRaises(VaultError):
                verify_directory(path)


if __name__ == "__main__":
    unittest.main()
