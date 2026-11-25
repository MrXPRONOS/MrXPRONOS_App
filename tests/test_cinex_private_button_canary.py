import hashlib
import unittest
from unittest.mock import Mock
from scripts.cinex_private_button_canary import (
  CanaryError, verify_private_destination, run, BUTTON_TEXT, BUTTON_URL,
  TEXTS, EXPECTED_STOCK_SHA256, reserve_once
)

def mock_result(obj,status=True):
    r=Mock(ok=status); r.json.return_value=obj;return r

class CanaryTests(unittest.TestCase):
    def test_approved_digest_is_pinned(self):
        self.assertEqual(len(EXPECTED_STOCK_SHA256),64)
        self.assertEqual(set(TEXTS),{"now","later"})

    def test_wrong_stock_is_rejected_before_api(self):
        sess=Mock()
        with self.assertRaises(CanaryError):
            verify_private_destination(sess,"token","-100555666777")
        sess.post.assert_not_called()

    def test_no_credentials_no_reservation(self):
        with self.assertRaises(CanaryError):
            reserve_once(Mock(),"","",-100111,"now")

    def test_verified_now_with_button_and_ledger(self):
        # Synthetic values: override the pinned digest in the test only.
        from unittest.mock import patch
        import scripts.cinex_private_button_canary as canary
        dest="-100123456789"
        calls=[
           mock_result({"ok":True,"result":{"id":55,"username":"CineRadarFr_Bot","is_bot":True}}),
           mock_result({"ok":True,"result":{"id":int(dest),"type":"channel","title":"CinéX — Stock privé"}}),
           mock_result({"ok":True,"result":{"status":"administrator","can_post_messages":True}}),
           mock_result([{"campaign":"foo"}]),
           mock_result({"ok":True,"result":{"message_id":57,"chat":{"id":int(dest)},
             "text":TEXTS["now"],"reply_markup":{"inline_keyboard":[[{"text":BUTTON_TEXT,"url":BUTTON_URL}]]}}}),
        ]
        sess=Mock()
        sess.post.side_effect=calls
        sess.patch.return_value=mock_result(None)
        with patch.object(canary,"EXPECTED_STOCK_SHA256",hashlib.sha256(dest.encode()).hexdigest()):
            self.assertTrue(run(sess,phase="now",stock_id=dest,bot_token="token",
                supabase_url="https://example.supabase.co",service_key="key"))
        self.assertEqual(sess.post.call_count,5)
        sess.patch.assert_called_once()

    def test_duplicate_never_sends(self):
        from unittest.mock import patch
        import scripts.cinex_private_button_canary as canary
        dest="-100123456789"
        sess=Mock()
        sess.post.side_effect=[
            mock_result({"ok":True,"result":{"id":55,"username":"CineRadarFr_Bot","is_bot":True}}),
            mock_result({"ok":True,"result":{"id":int(dest),"type":"channel","title":"CinéX — Stock privé"}}),
            mock_result({"ok":True,"result":{"status":"administrator","can_post_messages":True}}),
            mock_result([]),
        ]
        with patch.object(canary,"EXPECTED_STOCK_SHA256",hashlib.sha256(dest.encode()).hexdigest()):
            with self.assertRaises(CanaryError):
                run(sess,phase="later",stock_id=dest,bot_token="token",
                    supabase_url="https://example.supabase.co",service_key="key")
        self.assertEqual(sess.post.call_count,4)
