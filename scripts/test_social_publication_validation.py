import importlib.util
import unittest
from pathlib import Path

path=Path(__file__).with_name("verify_social_publications.py")
spec=importlib.util.spec_from_file_location("verify_social_publications",path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
validate=module.validate

class SocialPublicationAuditTest(unittest.TestCase):
    def test_valid(self):
        rows=[{"platform":p,"ok":True,"data":{"id":"media_"+p}}
              for p in ("facebook","instagram","threads","youtube")]
        self.assertEqual(validate("facebook,instagram,threads,youtube",rows)["checked"],4)
    def test_bluesky_success(self):
        rows=[{"platform":"facebook","ok":True,"data":{"id":"123"}},
              {"platform":"bluesky","ok":True,"data":{"id":"at://did:plc:valid/app.bsky.feed.post/abc"}}]
        result=validate("facebook,bluesky",rows)
        self.assertEqual(result["checked"],2)
        self.assertIn("bluesky",result["verified_platforms"])

    def test_bluesky_requires_real_post_uri(self):
        with self.assertRaisesRegex(ValueError,"SOCIAL_INVALID_BLUESKY_URI"):
            validate("bluesky",[{"platform":"bluesky","ok":True,"data":{"id":"dedup-fake-id"}}])

    def test_missing(self):
        with self.assertRaises(ValueError):
            validate("facebook,youtube",[{"platform":"facebook","ok":True,"data":{"id":"1"}}])
    def test_failure(self):
        with self.assertRaises(ValueError):
            validate("facebook",[{"platform":"facebook","ok":False,"data":{"id":"1"}}])
    def test_no_remote_id(self):
        with self.assertRaises(ValueError):
            validate("facebook",[{"platform":"facebook","ok":True,"data":{}}])
    def test_duplicate(self):
        with self.assertRaises(ValueError):
            validate("facebook",[{"platform":"facebook","ok":True,"data":{"id":"1"}},
                                 {"platform":"facebook","ok":True,"data":{"id":"2"}}])
    def test_unknown(self):
        with self.assertRaises(ValueError):
            validate("other",[{"platform":"other","ok":True,"data":{"id":"1"}}])

if __name__=="__main__":
    unittest.main()
