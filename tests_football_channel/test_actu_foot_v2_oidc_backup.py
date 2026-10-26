"""OIDC backup transport test; no actual GitHub or Cloudflare calls."""
import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.actu_foot_v2_store import COLLECTIONS,encrypt
from scripts.actu_foot_v2_oidc_backup import push,oidc_token,AUDIENCE

KEY=base64.b64encode(bytes(range(32))).decode()
class Resp:
    def __init__(self,data):self.data=data
    def raise_for_status(self):pass
    def json(self):return self.data
class Transport:
    def __init__(self):self.payload=None
    def get(self,url,headers,timeout):
        assert "audience="+AUDIENCE in url
        return Resp({"value":"abc.def.ghi"})
    def post(self,url,json,headers,timeout):
        assert headers["Authorization"]=="Bearer abc.def.ghi"
        self.payload=json
        return Resp({"ok":True,"count":7,"run":"1234"})
class Tests(unittest.TestCase):
    def test_oidc_ciphertext_only(self):
        with patch.dict(os.environ,{"ACTU_FOOT_V2_KEY_B64_V1":KEY,
           "ACTIONS_ID_TOKEN_REQUEST_URL":"https://oidc.example/?foo=bar",
           "ACTIONS_ID_TOKEN_REQUEST_TOKEN":"fake"}):
            with tempfile.TemporaryDirectory() as td:
                root=Path(td)
                manifest={"format":"actufoot-v2-backup-v2","collections":{}}
                for collection in COLLECTIONS:
                    records={} if collection!="audit" else {}
                    payload=encrypt(collection,records)
                    filename=collection+".aes.json"
                    (root/filename).write_text(payload)
                    manifest["collections"][collection]={"filename":filename,
                        "sha256":hashlib.sha256(payload.encode()).hexdigest(),
                        "generation":1,"key_version":1,"record_count":0}
                (root/"manifest.json").write_text(json.dumps(manifest))
                fake=Transport()
                status=push(root,fake)
                self.assertEqual(status["collections"],7)
                self.assertEqual(len(fake.payload["files"]),7)
                self.assertNotIn("home_team",json.dumps(fake.payload))
if __name__=="__main__":unittest.main()
