"""Offline no-send regressions for Neon-independent football news pipeline."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import actu_foot_d1_news as pub

NOW=datetime(2026,10,24,4,30,tzinfo=timezone.utc)

class NewsD1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        image=self.root/"assets/images/footnews/news.jpg"
        image.parent.mkdir(parents=True,exist_ok=True)
        image.write_bytes(b"fixture-only")
        self.patcher=patch.object(pub,"ROOT",self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.item={
            "slug":"news1","title":"Football confirmed update","summary":"Source verified.",
            "telegram_summary":"Source verified.", "published":(NOW-timedelta(minutes=25)).isoformat(),
            "link":"https://example.org/news/story",
            "image":"assets/images/footnews/news.jpg","image_origin":"source",
            "source":"Example source",
        }

    def test_only_genuine_recent_stories_with_source_photo(self):
        valid=pub.select_stories([self.item],NOW)
        self.assertEqual(len(valid),1)
        self.assertEqual(pub.select_stories([{**self.item,"published":(NOW-timedelta(days=4)).isoformat()}],NOW),[])
        self.assertEqual(pub.select_stories([{**self.item,"link":"javascript:bad"}],NOW),[])
        self.assertEqual(pub.select_stories([{**self.item,"image_origin":"generated_fallback"}],NOW),[])

    def test_empty_feed_finishes_successfully_without_network(self):
        with patch.object(pub,"D1Ledger",side_effect=AssertionError("D1 called")), \
             patch.object(pub,"send_article",side_effect=AssertionError("Telegram called")):
            report=pub.dispatch([],NOW,dry_run=False)
        self.assertEqual(report["sent"],0)
        self.assertTrue(report["no_fresh_news"])

    def test_dry_run_never_claims_or_sends(self):
        with patch.object(pub,"D1Ledger",side_effect=AssertionError("D1 called")), \
             patch.object(pub,"send_article",side_effect=AssertionError("Telegram called")):
            report=pub.dispatch([self.item],NOW,dry_run=True)
        self.assertEqual(report["would_send"],"news1")

    def test_confirmed_send_is_reserved_and_marked_once(self):
        ledger=Mock()
        ledger.rows.return_value=[]
        ledger.claim.return_value=True
        with patch.object(pub,"send_article",return_value=321) as send:
            result=pub.dispatch([self.item],NOW,dry_run=False,ledger=ledger,
                token="fake-token",chat="-100123",session=Mock())
        self.assertEqual(result["sent"],1)
        self.assertEqual(result["telegram_message_id"],321)
        self.assertEqual(ledger.claim.call_count,2)
        self.assertEqual(ledger.mark.call_count,2)
        send.assert_called_once()
        self.assertEqual(ledger.claim.call_args_list[1].args[0],pub.KIND)

    def test_no_duplicates_if_story_exists(self):
        ledger=Mock()
        ledger.rows.return_value=[{"ref_id":"-100123:news1"}]
        with patch.object(pub,"send_article",side_effect=AssertionError("Telegram called")):
            result=pub.dispatch([self.item],NOW,dry_run=False,ledger=ledger,
                token="fake-token",chat="-100123",session=Mock())
        self.assertEqual(result["already_sent"],1)
        ledger.claim.assert_not_called()

    def test_uncertain_delivery_keeps_both_claims(self):
        ledger=Mock()
        ledger.rows.return_value=[]
        ledger.claim.return_value=True
        with patch.object(pub,"send_article",side_effect=TimeoutError("uncertain")):
            result=pub.dispatch([self.item],NOW,dry_run=False,ledger=ledger,
                token="fake-token",chat="-100123",session=Mock())
        self.assertEqual(result["errors"],1)
        ledger.release.assert_not_called()
        self.assertEqual(ledger.claim.call_count,2)

if __name__=="__main__":
    unittest.main()
