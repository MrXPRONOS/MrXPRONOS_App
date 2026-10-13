"""Test Instagram et mesure A/B hors réseau, sans aucune publication."""
import json
import os
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from scripts import editorial_instagram_assets,editorial_instagram,editorial_attribution,content_studio

NOW=datetime(2026,10,13,12,tzinfo=timezone.utc)

def item(now=NOW):
    return {"id":"abc","kind":"article","title":"Togo vs Ghana",
        "url":editorial_instagram.BASE+"articles/test/",
        "source_date":now.isoformat(),
        "image":"assets/images/editorial/article-test-abcdef-social.webp",
        "platform_status":{"instagram":"not_requested"},"retired":False}

class InstagramAndAbTests(unittest.TestCase):
    def test_only_recent_images_convert_to_jpeg(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src=root/"assets/images/editorial/article-test-abcdef-social.webp"
            src.parent.mkdir(parents=True)
            Image.new("RGB",(1080,1080),(11,32,52)).save(src,"WEBP")
            q=root/"queue.json";q.write_text(json.dumps([item()]))
            report=editorial_instagram_assets.prepare(root,q,now=NOW)
            self.assertEqual(report["prepared"],1)
            record=json.loads(q.read_text())[0]
            dest=root/record["instagram_image"]
            self.assertTrue(dest.is_file())
            with Image.open(dest) as im:
                self.assertEqual(im.format,"JPEG")
                self.assertEqual(im.size,(1080,1080))
            self.assertLess(dest.stat().st_size,8_000_000)
    def test_old_or_retired_news_never_posted(self):
        entry=item()
        self.assertFalse(editorial_instagram.eligible({**entry,"retired":True,"instagram_image":"assets/images/editorial/a.jpg"},NOW))
        self.assertFalse(editorial_instagram.eligible({**entry,"kind":"news","instagram_image":"assets/images/editorial/a.jpg"},NOW))
        self.assertFalse(editorial_instagram.eligible({**entry,"source_date":"2026-01-01T00:00:00Z","instagram_image":"assets/images/editorial/a.jpg"},NOW))
    def test_post_requires_public_jpeg_and_meta_id(self):
        class Reply:
            def __init__(self,payload=None,mimetype="image/jpeg"):
                self.payload=payload or {}
                self.headers={"Content-Type":mimetype}
            def raise_for_status(self):pass
            def json(self):return self.payload
            def close(self):pass
        with tempfile.TemporaryDirectory() as d:
            q=Path(d)/"queue.json"
            entry={**item(),"instagram_image":"assets/images/editorial/article-test-abcdef-social.jpg"}
            q.write_text(json.dumps([entry]))
            calls=[]
            def fake_post(url,**kwargs):
                calls.append(url)
                return Reply({"id":"container1" if len(calls)==1 else "media2"})
            with patch.dict(os.environ,{"IG_USER_ID":"123","META_ACCESS_TOKEN":"test-token"}):
                outcome=editorial_instagram.publish(
                    q,True,NOW,request_post=fake_post,request_get=lambda *a,**kw:Reply())
            self.assertEqual(outcome["sent"],1)
            self.assertEqual(len(calls),2)
            self.assertTrue(calls[0].endswith("/media"))
            self.assertTrue(calls[1].endswith("/media_publish"))
            self.assertEqual(json.loads(q.read_text())[0]["platform_status"]["instagram"],"sent")
            # La deuxième tentative ne doit pas publier à nouveau.
            self.assertEqual(editorial_instagram.publish(q,False,NOW)["sent"],0)
    def test_not_live_jpeg_does_not_create_instagram_container(self):
        class Reply:
            headers={"Content-Type":"text/html"}
            def raise_for_status(self):pass
            def close(self):pass
        with tempfile.TemporaryDirectory() as d:
            q=Path(d)/"queue.json"
            q.write_text(json.dumps([{**item(),"instagram_image":"assets/images/editorial/article-test-abcdef-social.jpg"}]))
            with patch.dict(os.environ,{"IG_USER_ID":"123","META_ACCESS_TOKEN":"t"}):
                result=editorial_instagram.publish(
                    q,True,NOW,request_get=lambda *a,**k:Reply(),
                    request_post=lambda *a,**k: self.fail("No Meta post should happen"))
            self.assertEqual(result["skipped"],"jpeg_not_published")
    def test_two_distinct_article_covers_and_real_ab_aggregates(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch.object(content_studio,"ROOT",root),patch.object(content_studio,"OUT",root/"assets/images/editorial"):
                result=content_studio.save_cover("Deux design même article","article","test-a-b")
                self.assertNotEqual(result["ab_image_url"],result["image_url"])
                self.assertTrue((root/result["ab_image_url"]).exists())
            events=[
                {"event_type":"editorial_ab_exposure","page":"article|test-a-b|onsite|a"},
                {"event_type":"editorial_ab_exposure","page":"article|test-a-b|onsite|b"},
                {"event_type":"editorial_ab_click","page":"article|test-a-b|onsite|b"},
            ]
            report=editorial_attribution.summarize(events,now=NOW)
            self.assertEqual(report["attributed_visits"],0)
            self.assertEqual(len(report["ab_tests"]),2)
            bv=next(v for v in report["ab_tests"] if v["variant"]=="b")
            self.assertEqual(bv["open_rate"],1.0)
            self.assertEqual(bv["status"],"insufficient_data")
            self.assertIsNone(report["ab_significance"])

if __name__=="__main__":unittest.main()
