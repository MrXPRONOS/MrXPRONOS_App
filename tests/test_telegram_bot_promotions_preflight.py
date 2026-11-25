import unittest
from unittest.mock import Mock
from scripts.telegram_bot_promotions_preflight import (
    PreflightError, check_channels, check_ledger, bot_read
)

def resp(data,status=True):
    m=Mock(ok=status)
    m.json.return_value=data
    return m

class TestBotPromotionPreflight(unittest.TestCase):
    def test_bot_channels_authorized(self):
        s=Mock()
        s.post.side_effect=[
            resp({"ok":True,"result":{"is_bot":True,"id":55}}),
            resp({"ok":True,"result":{"id":-100101,"type":"channel","title":"Promos A"}}),
            resp({"ok":True,"result":{"status":"administrator","can_post_messages":True}}),
            resp({"ok":True,"result":{"id":-100102,"type":"channel","title":"Promos B"}}),
            resp({"ok":True,"result":{"status":"administrator","can_post_messages":True}}),
        ]
        self.assertEqual(check_channels(s,"test","-100101","-100102"),2)
        self.assertEqual(s.post.call_count,5)

    def test_reject_private_stock(self):
        s=Mock()
        s.post.side_effect=[
            resp({"ok":True,"result":{"is_bot":True,"id":55}}),
            resp({"ok":True,"result":{"id":-100101,"type":"channel","title":"CinéX — Stock privé"}}),
        ]
        with self.assertRaises(PreflightError):
            check_channels(s,"test","-100101","-100102")

    def test_reject_no_admin(self):
        s=Mock()
        s.post.side_effect=[
            resp({"ok":True,"result":{"is_bot":True,"id":55}}),
            resp({"ok":True,"result":{"id":-100101,"type":"channel","title":"A"}}),
            resp({"ok":True,"result":{"status":"member"}}),
        ]
        with self.assertRaises(PreflightError):
            check_channels(s,"test","-100101","-100102")

    def test_reject_alias_duplicates(self):
        s=Mock()
        s.post.side_effect=[
            resp({"ok":True,"result":{"is_bot":True,"id":55}}),
            resp({"ok":True,"result":{"id":-100101,"type":"channel","title":"A"}}),
            resp({"ok":True,"result":{"status":"creator"}}),
            resp({"ok":True,"result":{"id":-100101,"type":"channel","title":"A"}}),
        ]
        with self.assertRaises(PreflightError):
            check_channels(s,"test","@first","-100101")

    def test_ledger_read(self):
        s=Mock()
        s.get.return_value=resp([])
        check_ledger(s,"https://example.supabase.co","key")
        s.get.assert_called_once()
        self.assertNotIn("send",s.get.call_args.args[0])

    def test_failed_ledger(self):
        s=Mock()
        s.get.return_value=resp({"error":"forbidden"},False)
        with self.assertRaises(PreflightError):
            check_ledger(s,"https://example.supabase.co","key")

    def test_bot_api_fails_closed(self):
        s=Mock()
        s.post.return_value=resp({"ok":False},False)
        with self.assertRaises(PreflightError):
            bot_read(s,"secret","getMe",{})
