import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

module_path = Path(__file__).resolve().parents[1] / "scripts/cinema_healthcheck.py"
spec = importlib.util.spec_from_file_location("cinema_healthcheck", module_path)
health = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = health
spec.loader.exec_module(health)

class HealthCheckTests(unittest.TestCase):
    def response(self, payload, status=200):
        return Mock(ok=(status == 200), status_code=status, json=lambda: payload)

    def test_missing_secrets_are_safe(self):
        checks = health.diagnose(env={}, session=Mock())
        self.assertEqual(len(checks), 2)
        self.assertFalse(any(x.passed for x in checks))

    def test_telegram_bot_is_admin(self):
        session = Mock()
        session.post.side_effect = [
            self.response({'ok': True, 'result': {'id': 100, 'is_bot': True}}),
            self.response({'ok': True, 'result': {'type': 'channel', 'username': 'predict_mrxp'}}),
            self.response({'ok': True, 'result': {'status': 'administrator', 'can_post_messages': True}}),
        ]
        check = health.check_telegram(session, 'secret-token')
        self.assertTrue(check.passed)
        self.assertEqual(session.post.call_count, 3)
        self.assertTrue(all('send' not in c.args[0].rsplit('/', 1)[-1].lower() for c in session.post.call_args_list))

    def test_telegram_without_admin_refused(self):
        session = Mock()
        session.post.side_effect = [
            self.response({'ok': True, 'result': {'id': 100, 'is_bot': True}}),
            self.response({'ok': True, 'result': {'type': 'channel', 'username': 'predict_mrxp'}}),
            self.response({'ok': True, 'result': {'status': 'member'}}),
        ]
        self.assertFalse(health.check_telegram(session, 's').passed)

    def test_token_never_leaks_in_network_error(self):
        import requests
        session = Mock()
        session.post.side_effect = requests.exceptions.Timeout('private-token-value')
        result = health.check_telegram(session, 'private-token-value')
        self.assertFalse(result.passed)
        self.assertNotIn('private-token-value', result.note)

    def test_wrong_channel_refused(self):
        session = Mock()
        session.post.side_effect = [
            self.response({'ok': True, 'result': {'id': 3, 'is_bot': True}}),
            self.response({'ok': True, 'result': {'type': 'channel', 'username': 'not_test'}}),
        ]
        self.assertFalse(health.check_telegram(session, 's').passed)

    def test_tmdb_valid_movie_and_poster(self):
        session = Mock()
        session.get.return_value = self.response({'results': [{'id': 1, 'title': 'Film', 'poster_path': '/abc.jpg'}]})
        self.assertTrue(health.check_tmdb(session, 'key').passed)

    def test_tmdb_requires_source_image(self):
        session = Mock()
        session.get.return_value = self.response({'results': [{'id': 1, 'title': 'Film', 'poster_path': None}]})
        self.assertFalse(health.check_tmdb(session, 'key').passed)

    def test_tmdb_bad_key_is_safe(self):
        session = Mock()
        session.get.return_value = self.response({'status_message': 'secret value'}, 401)
        check = health.check_tmdb(session, 'my-key')
        self.assertFalse(check.passed)
        self.assertNotIn('my-key', check.note)

if __name__ == '__main__':
    unittest.main()