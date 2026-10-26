"""Offline test for encrypted Cloudflare KV backup replication."""
import base64
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.actu_foot_v2_store import encrypt
from scripts.actu_foot_v2_cloudflare_backup import build_payload, upload

SECRET=base64.b64encode(bytes(range(32))).decode()
SHA="a"*40

class FakeResponse:
    def __init__(self,data):
        self.data=data
    def raise_for_status(self):
        return None
    def json(self):
        return self.data

class FakeHTTP:
    def __init__(self):
        self.items={}
    def put(self,url,*,json,headers,timeout):
        for item in json:
            self.items[item["key"]]=item["value"]
        return FakeResponse({"success":True,"result":{"successful_key_count":len(json)}})
    def post(self,url,*,json,headers,timeout):
        return FakeResponse({"success":True,"result":{"values":{k:self.items.get(k) for k in json["keys"]}}})

class CloudflareBackupTests(unittest.TestCase):
    def test_ciphertext_only_snapshot(self):
        with patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V1":SECRET,
                                    "CLOUDFLARE_API_TOKEN":"mock",
                                    "CLOUDFLARE_ACCOUNT_ID":"1"*32,
                                    "CLOUDFLARE_V2_KV_NAMESPACE_ID":"2"*32}):
            with TemporaryDirectory() as td:
                path=Path(td)
                envelope=encrypt("matches",{"m1":{"home_team":"Real Madrid","away_team":"Barcelona"}})
                (path/"matches.aes.json").write_text(envelope)
                (path/"manifest.json").write_text(json.dumps({"format":"actufoot-v2-backup-v2",
                    "collections":{"matches":{"filename":"matches.aes.json",
                    "sha256":hashlib.sha256(envelope.encode()).hexdigest(),
                    "generation":1,"key_version":1,"record_count":1}}}))
                data=build_payload(path,SHA,123)
                self.assertEqual(len(data),2)
                self.assertNotIn("Real Madrid",json.dumps(data))
                remote=FakeHTTP()
                dest=upload(path,commit=SHA,run_id=123,session=remote)
                self.assertTrue(dest.endswith("/manifest.json"))
                self.assertEqual(len(remote.items),2)
if __name__=="__main__":
    unittest.main()
