import unittest
from unittest.mock import patch, Mock
from relay import Bot, bot_error_reason

class BotDiagnosticsTests(unittest.TestCase):
    def test_safe_reason(self):
        self.assertEqual(bot_error_reason(400,"Bad Request: chat not found"),"chat not found: check channel reference and bot membership")
        self.assertEqual(bot_error_reason(403,"Forbidden: bot was kicked from the channel"),"bot was removed")
        self.assertEqual(bot_error_reason(400,"secret @private_channel"),"unclassified Telegram error")
    def test_context_and_no_sensitive_output(self):
        response=Mock()
        response.json.return_value={"ok":False,"error_code":400,"description":"Bad Request: chat not found @secret_channel"}
        with patch("requests.post",return_value=response):
            with self.assertRaises(RuntimeError) as error:
                Bot("dummy-token").call("getChat",context="business",chat_id=-1001234567890)
        message=str(error.exception)
        self.assertIn("getChat [business]: 400",message)
        for sensitive in ("@secret_channel","dummy-token","1234567890"):
            self.assertNotIn(sensitive,message)
    def test_missing_token(self):
        with self.assertRaisesRegex(RuntimeError,"FORMATION_BOT_TOKEN missing"):
            Bot(" ")
    def test_success(self):
        response=Mock()
        response.json.return_value={"ok":True,"result":{"id":1}}
        with patch("requests.post",return_value=response):
            self.assertEqual(Bot("dummy").call("getMe",context="bot identity"),{"id":1})
