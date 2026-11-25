import unittest
from unittest.mock import Mock
from scripts.cinex_private_button_smoke import (
 BUTTON_TEXT, BUTTON_URL, TEXT, SmokeFailure,
 private_stock_record, validate_destination, verify_receipt, run
)

CHAT = "-100123456789"  # synthetic ID exclusively for local tests
BOTID = 1234567


def response(payload, ok=True):
    obj = Mock(ok=ok)
    obj.json.return_value = payload
    return obj


class TestCineXPrivateButtonSmoke(unittest.TestCase):
    def test_offline_never_connects(self):
        sess = Mock()
        result = run(sess, "", "", execute=False)
        self.assertEqual(result["sent"], False)
        sess.post.assert_not_called()

    def test_verifies_d1_exact_stock(self):
        sess = Mock()
        sess.post.return_value = response(
            {"success": True, "result":[{"results":[
                {"stock_chat_id":CHAT, "radar_bot_id":BOTID, "ready":1}]}]})
        self.assertEqual(private_stock_record(sess, "testkey"), (CHAT, BOTID))

    def test_refuses_other_stock(self):
        sess = Mock()
        sess.post.return_value = response(
            {"success": True, "result":[{"results":[
                {"stock_chat_id":"@Public", "radar_bot_id":BOTID, "ready":1}]}]})
        with self.assertRaises(SmokeFailure):
            private_stock_record(sess, "testkey")

    def test_private_admin_rights(self):
        sess = Mock()
        sess.post.side_effect = [
            response({"ok":True,"result":{"id":BOTID,"is_bot":True,"username":"CineRadarFr_Bot"}}),
            response({"ok":True,"result":{"id":int(CHAT),"type":"channel","title":"CinéX — Stock privé"}}),
            response({"ok":True,"result":{"status":"administrator","can_post_messages":True,"can_delete_messages":True}})
        ]
        self.assertTrue(validate_destination(sess, "test-token", CHAT, BOTID))

    def test_rejects_missing_delete_rights(self):
        sess = Mock()
        sess.post.side_effect = [
            response({"ok":True,"result":{"id":BOTID,"is_bot":True,"username":"CineRadarFr_Bot"}}),
            response({"ok":True,"result":{"id":int(CHAT),"type":"channel","title":"CinéX — Stock privé"}}),
            response({"ok":True,"result":{"status":"administrator","can_post_messages":True,"can_delete_messages":False}})
        ]
        with self.assertRaises(SmokeFailure):
            validate_destination(sess, "test-token", CHAT, BOTID)

    def test_bot_button_receipt(self):
        receipt={"chat":{"id":int(CHAT)},"message_id":45,"text":TEXT,
            "reply_markup":{"inline_keyboard":[[{"text":BUTTON_TEXT,"url":BUTTON_URL}]]}}
        self.assertEqual(verify_receipt(receipt, CHAT),45)
        receipt["reply_markup"] = {"inline_keyboard":[]}
        with self.assertRaises(SmokeFailure):
            verify_receipt(receipt, CHAT)

    def test_live_posts_and_deletes_exact_message(self):
        sess = Mock()
        sess.post.side_effect = [
            response({"success":True,"result":[{"results":[
                {"stock_chat_id":CHAT,"radar_bot_id":BOTID,"ready":1}]}]}),
            response({"ok":True,"result":{"id":BOTID,"is_bot":True,"username":"CineRadarFr_Bot"}}),
            response({"ok":True,"result":{"id":int(CHAT),"type":"channel","title":"CinéX — Stock privé"}}),
            response({"ok":True,"result":{"status":"administrator","can_post_messages":True,"can_delete_messages":True}}),
            response({"ok":True,"result":{"message_id":77,"chat":{"id":int(CHAT)},
                    "text":TEXT,"reply_markup":{"inline_keyboard":[[{"text":BUTTON_TEXT,"url":BUTTON_URL}]]}}}),
            response({"ok":True,"result":True})
        ]
        out=run(sess, "cfkey","botkey",execute=True)
        self.assertEqual(out,{"sent":True,"verified":True,"deleted":True})
        self.assertIn("deleteMessage",sess.post.call_args.args[0])
        self.assertEqual(sess.post.call_args.kwargs["json"]["message_id"],77)
