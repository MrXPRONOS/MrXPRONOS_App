"""V2 security tests: no real secrets, no GitHub network calls."""
import base64
import json
import os
import unittest
from unittest.mock import patch

from scripts.actu_foot_v2_store import (
    VaultError, VaultConflict, encrypt, decrypt, derive, validate_records,
    CollectionVault, append_audit, verify_audit, backup_bundle, verify_backup,
    restore_backup, collection_path
)

KEY1=base64.b64encode(bytes(range(32))).decode()
KEY2=base64.b64encode(bytes(range(32,64))).decode()


class Response:
    def __init__(self, code, data=None):
        self.status_code=code
        self.data=data or {}
    def json(self):
        return self.data
    def raise_for_status(self):
        if self.status_code>=400:
            raise RuntimeError(f"HTTP {self.status_code}")


class MemoryGitHub:
    def __init__(self):
        self.files={}
        self.revision=0
        self.conflict_once=False
    def get(self, url, **kwargs):
        if url not in self.files:
            return Response(404)
        sha, content=self.files[url]
        return Response(200, {"type":"file","encoding":"base64","sha":sha,
                              "content":base64.b64encode(content.encode()).decode()})
    def put(self, url, json=None, **kwargs):
        if self.conflict_once:
            self.conflict_once=False
            return Response(409)
        stored=self.files.get(url)
        if (stored and json.get("sha")!=stored[0]) or (not stored and "sha" in json):
            return Response(409)
        self.revision+=1
        sha=f"sha-{self.revision}"
        self.files[url]=(sha,base64.b64decode(json["content"]).decode())
        return Response(200,{"content":{"sha":sha}})


class V2Tests(unittest.TestCase):
    def setUp(self):
        patcher=patch.dict(os.environ, {"ACTU_FOOT_V2_KEY_B64_V1":KEY1,
            "ACTU_FOOT_V2_KEY_B64_V2":KEY2},clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_crypto_collection_binding(self):
        records={"fixture:1":{"home_team":"Real Madrid","away_team":"Barcelona","home_score":2}}
        a=encrypt("matches",records)
        b=encrypt("matches",records)
        self.assertNotEqual(a,b)
        self.assertEqual(decrypt("matches",a)[0],records)
        with self.assertRaises(VaultError):decrypt("statistics",a)
        modified=json.loads(a)
        modified["generation"]=2
        with self.assertRaises(VaultError):decrypt("matches",json.dumps(modified))
        self.assertNotIn("Real Madrid",a)

    def test_rotation_and_old_version(self):
        records={"n1":{"status":"sent"}}
        old=encrypt("publications",records,key_version=1,generation=1)
        new=encrypt("publications",records,key_version=2,generation=2)
        self.assertEqual(decrypt("publications",new)[1]["key_version"],2)
        self.assertEqual(decrypt("publications",old)[0],records)
        self.assertNotEqual(derive("matches",1),derive("publications",1))

    def test_validation(self):
        with self.assertRaises(VaultError):validate_records("matches",{"x":{"home_score":80}})
        with self.assertRaises(VaultError):validate_records("publications",{"x":{"status":"published"}})
        with self.assertRaises(VaultError):collection_path("../../oops")

    def test_audit_chain(self):
        history=append_audit({},"create",{"module":"matches"})
        history=append_audit(history,"update",{"module":"matches"})
        self.assertTrue(verify_audit(history))
        history["1"]["details"]["module"]="wrong"
        with self.assertRaises(VaultError):verify_audit(history)

    def test_backup_restore_and_conflicts(self):
        backend=MemoryGitHub()
        v=CollectionVault("publications",repo="MrXPRONOS/MrXPRONOS_App",branch="main",
                          token="fake",session=backend)
        first=v.update(lambda _:{"message:1":{"status":"sent"}},allow_new=True)
        db,sha,meta=v.read()
        self.assertEqual(first,sha)
        b=backup_bundle("publications",db,meta["generation"])
        self.assertEqual(verify_backup("publications",b)[0],db)
        backend.conflict_once=True
        v.update(lambda rows:{**rows,"message:2":{"status":"pending"}})
        with self.assertRaises(VaultConflict):
            restore_backup(v,b,expected_sha=sha,confirm=True)
        _,latest,_=v.read()
        with self.assertRaises(VaultError):
            restore_backup(v,b,expected_sha=latest,confirm=False)
        v.restore=restore_backup(v,b,expected_sha=latest,confirm=True,minimum_generation=1)
        self.assertEqual(v.read()[0],db)

    def test_wrong_key_or_invalid_ciphertext(self):
        data=encrypt("settings",{"k":{"enabled":True}})
        with patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V1":KEY2}):
            with self.assertRaises(VaultError):decrypt("settings",data)
        corrupt=json.loads(data)
        corrupt["ciphertext_b64"]=corrupt["ciphertext_b64"][:-4]+"AAAA"
        with self.assertRaises(VaultError):decrypt("settings",json.dumps(corrupt))


if __name__=="__main__":
    unittest.main()
