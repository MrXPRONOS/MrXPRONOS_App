import unittest
from unittest.mock import patch,Mock
from scripts.repair_shared_formation_bot_access import record_safe_status

CHAT="-1001234567890"
TOKEN="123456:synthetic_test_token"

def reply(data):
    response=Mock()
    response.json.return_value=data
    return response

class SourceBotAccessTests(unittest.TestCase):
    def test_verified_admin_source_can_be_read_by_exact_bot_token(self):
        responses=[
            reply({"ok":True,"result":{"id":45678,"is_bot":True,"username":"FormBot"}}),
            reply({"ok":True,"result":{"id":-1001234567890,"type":"channel"}}),
            reply({"ok":True,"result":{"status":"administrator","can_post_messages":True}})
        ]
        with patch("requests.post",side_effect=responses) as mock:
            self.assertTrue(record_safe_status("formation",TOKEN,CHAT,45678))
            self.assertEqual(mock.call_count,3)

    def test_wrong_bot_identity_fails_closed(self):
        responses=[reply({"ok":True,"result":{"id":999,"is_bot":True}})]
        with patch("requests.post",side_effect=responses):
            with self.assertRaisesRegex(RuntimeError,"identity_mismatch"):
                record_safe_status("formation",TOKEN,CHAT,45678)

    def test_missing_admin_rights_are_blocking(self):
        responses=[
            reply({"ok":True,"result":{"id":45678,"is_bot":True}}),
            reply({"ok":True,"result":{"type":"channel"}}),
            reply({"ok":True,"result":{"status":"member"}})
        ]
        with patch("requests.post",side_effect=responses):
            with self.assertRaisesRegex(RuntimeError,"bot_post_rights_missing"):
                record_safe_status("formation",TOKEN,CHAT,45678)

    def test_protected_source_never_treated_as_transferable(self):
        responses=[
            reply({"ok":True,"result":{"id":45678,"is_bot":True}}),
            reply({"ok":True,"result":{"type":"channel","has_protected_content":True}})
        ]
        with patch("requests.post",side_effect=responses):
            with self.assertRaisesRegex(RuntimeError,"source_protected_copy_not_allowed"):
                record_safe_status("formation",TOKEN,CHAT,45678)
if __name__=="__main__":
    unittest.main()
