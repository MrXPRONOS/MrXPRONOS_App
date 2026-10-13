"""Tests hors réseau de la phase 3 : vraie attribution, UTM et reçus de diffusion."""
import unittest
import json,os,tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
from scripts import editorial_pages,editorial_attribution,editorial_merge_receipts,editorial_threads

class EditorialPhase3Tests(unittest.TestCase):
    def test_og_preserves_only_approved_utm_params(self):
        page=editorial_pages.render("article",{
            "slug":"test-fixture","title":"Togo vs Ghana",
            "image_url":"assets/images/editorial/test-og.webp"
        })
        self.assertIn("window.location.replace(destination.toString())",page)
        self.assertIn("utm_source",page)
        self.assertIn("utm_content",page)
        self.assertIn('og:image',page)
        self.assertIn('content="3;url=',page)
        self.assertIn("article.html?slug=test-fixture",page)
    def test_real_traffic_attribution_groups_and_only_approved_fields(self):
        sample=[
            {"event_type":"editorial_view","page":"article|test-fixture|telegram|v1"},
            {"event_type":"editorial_view","page":"article|test-fixture|telegram|v1"},
            {"event_type":"editorial_promo_copy","page":"article|test-fixture|telegram|v1"},
            {"event_type":"editorial_view","page":"conseil|test-guide|facebook|v2"},
            {"event_type":"editorial_view","page":"conseil|test-guide|malicious source|v2"},
            {"event_type":"visit","page":"conseil|test-guide|facebook|v2"},
        ]
        out=editorial_attribution.summarize(sample,now=datetime(2026,10,13,tzinfo=timezone.utc))
        self.assertEqual(out["attributed_visits"],3)
        self.assertEqual(out["promo_copy_actions"],1)
        self.assertEqual(out["invalid_events_skipped"],2)
        self.assertIsNone(out["unique_visitors"])
        self.assertIsNone(out["ab_significance"])
        tg=next(x for x in out["groups"] if x["source"]=="telegram")
        self.assertEqual(tg["promo_copy_per_visit"],0.5)
    def test_receipt_merge_never_resets_success_or_duplicate_item(self):
        current=[{"id":"a","platform_status":{"telegram":"not_requested","facebook":"sent"},
                 "delivered":{"facebook":{"post_id":"99"}}}]
        fetched=[{"id":"a","platform_status":{"telegram":"sent","facebook":"not_requested"},
                  "delivered":{"telegram":{"message_id":19}}},
                 {"id":"unknown","platform_status":{"telegram":"sent"},"delivered":{"telegram":{"message_id":1}}}]
        n=editorial_merge_receipts.merge(current,fetched)
        self.assertEqual(n,1)
        self.assertEqual(current[0]["platform_status"]["telegram"],"sent")
        self.assertEqual(current[0]["platform_status"]["facebook"],"sent")
        self.assertEqual(editorial_merge_receipts.merge(current,fetched),0)
    def test_threads_publisher_uses_two_confirmed_steps(self):
        now=datetime(2026,10,13,12,tzinfo=timezone.utc)
        observed=[]
        class FakeResponse:
            def __init__(self,payload):self.payload=payload
            def raise_for_status(self):return None
            def json(self):return self.payload
        def fake_post(url,**kwargs):
            observed.append((url,kwargs))
            return FakeResponse({"id":"container-19" if len(observed)==1 else "post-20"})
        with tempfile.TemporaryDirectory() as tmp:
            queue=Path(tmp)/"queue.json"
            data=[{"id":"a","kind":"article","title":"Togo vs Ghana",
              "url":editorial_threads.BASE+"articles/test/",
              "source_date":now.isoformat(),
              "platform_status":{"threads":"not_requested"}}]
            queue.write_text(json.dumps(data))
            with patch.dict(os.environ,{"THREADS_ACCESS_TOKEN":"test","THREADS_USER_ID":"user42"}):
                outcome=editorial_threads.publish(queue_path=queue,enabled=True,now=now,request_post=fake_post)
            self.assertEqual(outcome["sent"],1)
            self.assertEqual(len(observed),2)
            self.assertIn("threads_publish",observed[1][0])
            self.assertIn("utm_source=threads",observed[0][1]["data"]["link_attachment"])
            self.assertEqual(json.loads(queue.read_text())[0]["platform_status"]["threads"],"sent")
            second=editorial_threads.publish(queue_path=queue,enabled=False,now=now)
            self.assertEqual(second["sent"],0)

    def test_malformed_tracking_event_is_never_exported(self):
        for item in [
            {"event_type":"editorial_view","page":"article|../secret|telegram|v1"},
            {"event_type":"editorial_view","page":"article|ab|telegram|v9"},
            {"event_type":"editorial_view","page":"article|ab|telegram|v1|extra"},
            {"event_type":"editorial_view","page":"article|ab|email|v1"},
        ]:
            self.assertIsNone(editorial_attribution.parse_event(item))

if __name__=="__main__":
    unittest.main()
