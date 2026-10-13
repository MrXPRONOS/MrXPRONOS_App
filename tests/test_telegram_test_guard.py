"""Tests unitaires sans réseau pour le routage Telegram de test."""
import unittest
from unittest.mock import Mock
from scripts.telegram_test_guard import validate_test_channel, TestChannelGuardError

class TelegramTestGuardTests(unittest.TestCase):
    def test_wrong_channel_is_rejected(self):
        response = Mock()
        response.json.return_value = {'ok': True, 'result': {'type': 'channel', 'username': 'mr_xpronos', 'id': -100123}}
        with self.assertRaises(TestChannelGuardError):
            validate_test_channel('@mr_xpronos', 'dummy', lambda *args, **kwargs: response)

    def test_missing_bot_is_rejected(self):
        with self.assertRaises(TestChannelGuardError):
            validate_test_channel('@predict_mrxp', '')

if __name__ == '__main__':
    unittest.main()
