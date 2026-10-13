"""Tests hors réseau de la phase 3 : vraie attribution, UTM et reçus de diffusion."""
import unittest
from datetime import datetime,timezone
from scripts import editorial_pages,editorial_attribution,editorial_merge_receipts

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
