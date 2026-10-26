"""Local-only tests for GitHub encrypted state, no API or secret needed."""
import base64
import json
import os
import unittest
from unittest.mock import patch

from scripts.actu_foot_github_vault import (
    GitHubVault, VaultConflict, VaultError, derive_key, seal, unseal
)

SECRET = base64.b64encode(bytes(range(32))).decode("ascii")


class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self.data = status, data
    def json(self):
        return self.data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("API failure")


class FakeGitHub:
    def __init__(self):
        self.content = None
        self.sha = None
        self.conflict_once = False
    def get(self, url, **kwargs):
        if self.content is None:
            return FakeResponse(404, {})
        return FakeResponse(200, {
            "type": "file", "encoding": "base64", "sha": self.sha,
            "content": base64.b64encode(self.content.encode()).decode()
        })
    def put(self, url, json, **kwargs):
        if self.conflict_once:
            self.conflict_once = False
            return FakeResponse(409, {})
        if self.content is not None and json.get("sha") != self.sha:
            return FakeResponse(409, {})
        if self.content is None and "sha" in json:
            return FakeResponse(409, {})
        self.content = base64.b64decode(json["content"]).decode()
        self.sha = "fake-" + str(len(self.content)) + "-" + str(self.content.count("b64"))
        return FakeResponse(200, {"content": {"sha": self.sha}})


class TestVault(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"ML_V2_HISTORY_KEY_B64": SECRET})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_roundtrip_nonce_and_key_isolation(self):
        k = derive_key()
        self.assertNotEqual(k, bytes(range(32)))
        obj = {"version": 1, "history": {"match": {"score": "2-1"}}}
        a, b = seal(obj, k), seal(obj, k)
        self.assertNotEqual(a, b)
        self.assertEqual(unseal(a, k), obj)
        self.assertNotIn("match", a)
        self.assertNotIn("score", a)

    def test_tamper_and_wrong_key_fail_closed(self):
        k = derive_key()
        val = seal({"private": "football"}, k)
        obj = json.loads(val)
        raw = bytearray(base64.b64decode(obj["ciphertext_b64"]))
        raw[-1] ^= 1
        obj["ciphertext_b64"] = base64.b64encode(raw).decode()
        with self.assertRaises(VaultError):
            unseal(json.dumps(obj), k)
        with self.assertRaises(VaultError):
            unseal(val, bytes(32))

    def test_missing_secret_rejected(self):
        with self.assertRaises(VaultError):
            derive_key("not-base64!")
        with self.assertRaises(VaultError):
            derive_key(base64.b64encode(bytes(16)).decode())

    def test_read_update_conflict(self):
        api = FakeGitHub()
        store = GitHubVault(repo="MrXPRONOS/MrXPRONOS_App", branch="main", token="fake", session=api)
        self.assertIsNone(store.read(allow_new=True).sha)
        before = store.change(lambda db: {**db, "history": {"2026-10-26": "ok"}},
                              message="test", allow_new=True)
        self.assertTrue(before.sha)
        self.assertEqual(store.read().data["history"]["2026-10-26"], "ok")
        with self.assertRaises(VaultConflict):
            store.write({"version": 1}, expected_sha="wrong", message="stale")
        api.conflict_once = True
        after = store.change(lambda db: {**db, "publications": {"x": "claimed"}},
                             message="test-retry")
        self.assertEqual(after.data["publications"], {"x": "claimed"})


if __name__ == "__main__":
    unittest.main()
