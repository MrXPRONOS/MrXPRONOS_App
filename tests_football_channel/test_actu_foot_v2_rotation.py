import base64
import os
import unittest
from unittest.mock import MagicMock,patch
from scripts.actu_foot_v2_store import COLLECTIONS, append_audit, decrypt, VaultError, VaultConflict
from scripts.actu_foot_v2_atomic_rotation import rotate_all
from scripts.actu_foot_v3_atomic import FileState

class RotationTests(unittest.TestCase):
    def setUp(self):
        p=patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V1":base64.b64encode(bytes(32)).decode(),
            "ACTU_FOOT_V2_KEY_B64_V2":base64.b64encode(bytes([1])*32).decode()})
        p.start()
        self.addCleanup(p.stop)
        self.store=MagicMock()
        self.store.head.return_value=("a"*40,"b"*40)
        self.store.load_collection.side_effect=lambda name,commit: FileState(
            append_audit({},"init",{}) if name=="audit" else {},1,1,True)
    def test_preview_all_without_write(self):
        self.assertEqual(rotate_all(self.store)["status"],"preview_verified")
        self.store.commit.assert_not_called()
    def test_stale_approval_refused(self):
        with self.assertRaises(VaultConflict):
            rotate_all(self.store,execute=True,expected_commit="c"*40,confirmation="ROTATE_ALL_ENCRYPTED_V2")
        self.store.commit.assert_not_called()
    def test_all_seven_atomically_and_verified(self):
        self.store.commit.return_value="d"*40
        original=self.store.load_collection.side_effect
        def read(name,commit):
            if commit=="a"*40:return original(name,commit)
            entries=self.store.commit.call_args.args[2]
            payload=next(v for k,v in entries.items() if k.endswith("/"+name+".aes.json"))
            records,header=decrypt(name,payload)
            return FileState(records,header["generation"],header["key_version"],True)
        self.store.load_collection.side_effect=read
        self.assertEqual(rotate_all(self.store,execute=True,expected_commit="a"*40,confirmation="ROTATE_ALL_ENCRYPTED_V2")["status"],"rotated_verified")
        self.store.commit.assert_called_once()
        self.assertEqual(len(self.store.commit.call_args.args[2]),7)
    def test_missing_dedicated_key(self):
        with patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V2":""}):
            with self.assertRaises(VaultError):rotate_all(self.store)
