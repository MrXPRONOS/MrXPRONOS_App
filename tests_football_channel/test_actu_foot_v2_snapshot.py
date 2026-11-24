"""Immutable snapshot, completeness, and recovery provenance regression tests."""
import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.actu_foot_v2_store import COLLECTIONS, encrypt, VaultError
from scripts.actu_foot_v2_operations import snapshot, verify_directory
from scripts.actu_foot_v2_cloudflare_recovery import verify_payload
from scripts.actu_foot_v2_oidc_backup import push

COMMIT = "a" * 40
KEY = base64.b64encode(bytes(range(32))).decode()


class ImmutableSnapshotTests(unittest.TestCase):
    def setUp(self):
        p = patch.dict(os.environ, {"ACTU_FOOT_V2_KEY_B64_V1": KEY, "GITHUB_SHA": COMMIT})
        p.start()
        self.addCleanup(p.stop)

    def fake_vault(self, collection, branch):
        vault = MagicMock()
        response = vault.session.get.return_value
        response.status_code = 200
        blob = encrypt(collection, {})
        response.json.return_value = {"type": "file", "encoding": "base64",
            "sha": "b" * 40, "content": base64.b64encode(blob.encode()).decode()}
        return vault

    @patch("scripts.actu_foot_v2_operations.CollectionVault")
    def test_one_immutable_commit_for_all_seven(self, factory):
        vaults = [self.fake_vault(name, "main") for name in COLLECTIONS]
        factory.side_effect = vaults
        with tempfile.TemporaryDirectory() as td:
            result = snapshot(Path(td))
            self.assertEqual(result["source_commit"], COMMIT)
            self.assertEqual(set(result["collections"]), set(COLLECTIONS))
            self.assertEqual(verify_directory(Path(td)), result)
            for v in vaults:
                self.assertEqual(v.session.get.call_args.kwargs["params"], {"ref": COMMIT})

    @patch("scripts.actu_foot_v2_operations.CollectionVault")
    def test_missing_collection_no_manifest(self, factory):
        vaults = [self.fake_vault(name, "main") for name in COLLECTIONS]
        vaults[-1].session.get.return_value.status_code = 404
        factory.side_effect = vaults
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(VaultError, "Incomplete"):
                snapshot(Path(td))
            self.assertFalse((Path(td) / "manifest.json").exists())

    def payload(self):
        files = {name: encrypt(name, {}) for name in COLLECTIONS}
        index = {"format": "actufoot-v2-backup-v2", "source_commit": COMMIT,
                 "collections": {name: {"filename": name + ".aes.json",
                    "sha256": hashlib.sha256(value.encode()).hexdigest(),
                    "generation": 1, "key_version": 1, "record_count": 0}
                    for name, value in files.items()}}
        return {"ok": True, "files": files, "manifest": json.dumps(index),
                "provenance": {"repository": "MrXPRONOS/MrXPRONOS_App",
                               "run": "1", "attempt": "1", "commit": COMMIT},
                "anchor": {"sequence": 0, "entry_hash": "0"*64, "audit_generation": 1}}

    def test_provenance_and_anchor_required(self):
        payload = self.payload()
        self.assertEqual(len(verify_payload(payload, 1, 1)[0]), 7)
        payload["provenance"]["commit"] = "c" * 40
        with self.assertRaisesRegex(VaultError, "source commit mismatch"):
            verify_payload(payload, 1, 1)
        payload["provenance"]["commit"] = COMMIT
        payload["anchor"] = None
        with self.assertRaisesRegex(VaultError, "audit anchor"):
            verify_payload(payload, 1, 1)

    def test_upload_refuses_mismatched_workflow_commit(self):
        payload = self.payload()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, blob in payload["files"].items():
                (root / (name + ".aes.json")).write_text(blob)
            (root / "manifest.json").write_text(payload["manifest"])
            transport = MagicMock()
            with patch.dict(os.environ, {"GITHUB_SHA": "c" * 40}):
                with self.assertRaisesRegex(VaultError, "authenticated workflow commit"):
                    push(root, transport)
            transport.get.assert_not_called()
            transport.post.assert_not_called()
