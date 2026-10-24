"""Offline Cloudflare KV media upload tests: never contact Neon/Supabase."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import cloudflare_public_media as media


class FakeResponse:
    def __init__(self, *, payload=None, status_code=200, headers=None):
        self.payload=payload or {}
        self.status_code=status_code
        self.headers=headers or {}
    def raise_for_status(self):
        if not 200 <= self.status_code < 300:
            raise RuntimeError("HTTP "+str(self.status_code))
    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, digest, size):
        self.digest=digest
        self.size=size
        self.uploaded=None
        self.head_calls=0
    def get(self,url,**kwargs):
        assert "token" in url
        return FakeResponse(payload={"value":"valid-test-oidc"})
    def put(self,url,*,data,headers,timeout):
        self.uploaded={"url":url,"body":data.read(),"headers":headers}
        key=url.split("key=",1)[1]
        return FakeResponse(payload={
            "ok":True,"key":key,"size":self.size,
            "sha256":self.digest,"url":media.HOST+"/"+key,
        })
    def head(self,url,**kwargs):
        self.head_calls+=1
        return FakeResponse(headers={"Content-Type":"image/jpeg","Content-Length":str(self.size)})


class MediaUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"sample.jpg"
        self.path.write_bytes(b"testjpeg"*300)
        self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.key="images/mrxpronos-combine/2026-10-24/"+self.sha[:24]+".jpg"

    def test_upload_uses_only_cloudflare_and_oidc(self):
        fake=FakeSession(self.sha,self.path.stat().st_size)
        with patch.dict(os.environ,{
            "ACTIONS_ID_TOKEN_REQUEST_URL":"https://github.example/token",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN":"mock",
        }):
            url=media.upload_public_media(self.path,self.key,session=fake)
        self.assertEqual(url,media.HOST+"/"+self.key)
        self.assertEqual(fake.uploaded["body"],self.path.read_bytes())
        self.assertEqual(fake.uploaded["headers"]["Authorization"],"Bearer valid-test-oidc")
        self.assertEqual(fake.head_calls,1)
        self.assertNotIn("neon",url)
        self.assertNotIn("supabase",url)

    def test_refuse_unmatched_hash_without_network(self):
        with self.assertRaises(media.PublicMediaError):
            media.upload_public_media(self.path,self.key.replace(self.sha[:24],"0"*24))

    def test_refuse_missing_oidc_without_fallback(self):
        with patch.dict(os.environ,{"ACTIONS_ID_TOKEN_REQUEST_URL":"","ACTIONS_ID_TOKEN_REQUEST_TOKEN":""}):
            with self.assertRaises(media.PublicMediaError):
                media.upload_public_media(self.path,self.key)

    def test_invalid_media_key(self):
        with self.assertRaises(media.PublicMediaError):
            media.upload_public_media(self.path,"../../../.git/config")


if __name__=="__main__":
    unittest.main()
