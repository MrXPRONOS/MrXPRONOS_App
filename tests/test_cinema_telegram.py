"""Run with python -m unittest discover -s tests -p 'test_cinema_telegram.py'."""
import os
import sys
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
if not (Path(__file__).resolve().parents[1] / 'scripts' / 'telegram_rich.py').exists():
    stub = types.ModuleType('telegram_rich')
    stub.post_photo = lambda *args, **kwargs: None
    sys.modules['telegram_rich'] = stub
import cinema_telegram as cm

class CinemaTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 10, 15)

    def test_all_four_rich_formats(self):
        for kind in cm.FORMATS[:4]:
            with self.subTest(kind=kind):
                body, rows, movie = cm.render(kind, cm.DEMO, self.day, True)
                self.assertIn('<h3>', body)
                self.assertIn('<i>', body)
                self.assertIn('<blockquote>', body)
                self.assertEqual(len(rows), 1)
                self.assertEqual(len(rows[0]), 1)
                self.assertEqual(rows[0][0]['style'], 'primary')
                self.assertTrue(rows[0][0]['url'].startswith('https://'))

    def test_html_escaping(self):
        m = dict(cm.DEMO[0], title='<script>& film', overview='<img src=x>')
        body, _, _ = cm.render('film', [m], self.day)
        self.assertNotIn('<script>', body)
        self.assertNotIn('<img src=x>', body)
        self.assertIn('&lt;script&gt;', body)

    def test_tmdb_deterministic(self):
        with patch.object(cm.TMDBClient, 'get', return_value=cm.DEMO):
            client = cm.TMDBClient('fake')
            self.assertEqual(client.choose('top5', self.day), client.choose('top5', self.day))
            self.assertEqual(len(client.choose('top5', self.day)), 5)
            self.assertTrue(all(m['release_date'] >= '2026-10-15' for m in client.choose('sorties', self.day)))

    def test_quiz_native_options(self):
        with patch.object(cm, 'call_telegram', return_value={'message_id': 18}) as mocked:
            result = cm.publish('quiz', [], 'fake', '-100123', self.day, MagicMock())
            self.assertEqual(result, 18)
            method, data = mocked.call_args.args[2:4]
            self.assertEqual(method, 'sendPoll')
            self.assertEqual(data['type'], 'quiz')
            self.assertEqual(len(data['options']), 4)
            self.assertLess(data['correct_option_id'], 4)
            self.assertTrue(all(isinstance(o, dict) and 'text' in o for o in data['options']))

    def test_card_created_offline(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            path = cm.create_card(cm.DEMO, 'top5', Path(temp), MagicMock(), True)
            with Image.open(path) as img:
                self.assertEqual(img.size, (960, 640))

    def test_dry_run_no_network(self):
        with patch.object(cm, 'post_photo', side_effect=AssertionError('sent')):
            for kind in cm.FORMATS:
                cm.publish(kind, cm.DEMO, None, None, self.day, MagicMock(), True, True)

    def test_production_demo_refused(self):
        with self.assertRaises(SystemExit):
            cm.main(['--mode', 'production', '--demo', '--dry-run'])

    def test_test_channel_fixed(self):
        with patch.dict(os.environ, {'CINEMA_TEST_CHAT_ID': '@wrong_channel'}):
            self.assertEqual(cm.target_chat('test'), '@predict_mrxp')

    def test_token_absent_refused(self):
        with patch.dict(os.environ, {'CINEMA_TELEGRAM_BOT_TOKEN': '', 'TELEGRAM_BOT_TOKEN': ''}):
            with self.assertRaises(SystemExit):
                cm.main(['--mode', 'test', '--format', 'quiz'])

    def test_bot_admin_check(self):
        with patch.object(cm, 'call_telegram', side_effect=[{'id': 42}, {'status': 'administrator', 'can_post_messages': True}]) as send:
            cm.verify_test_bot(MagicMock(), 'fake-token', cm.TEST_CHANNEL)
            self.assertEqual(send.call_count, 2)
        with patch.object(cm, 'call_telegram', side_effect=[{'id': 42}, {'status': 'member'}]):
            with self.assertRaises(RuntimeError):
                cm.verify_test_bot(MagicMock(), 'fake-token', cm.TEST_CHANNEL)

    def test_same_channel_refused(self):
        with patch.dict(os.environ, {'TELEGRAM_CHAT_ID': '@predict_mrxp', 'TELEGRAM_BOT_TOKEN':'fake',
                                     'TMDB_API_KEY': 'fake'}):
            with self.assertRaises(SystemExit):
                cm.main(['--mode', 'test', '--format', 'quiz'])

if __name__ == '__main__':
    unittest.main()
# CI smoke-test marker: @predict_mrxp only; fictional demonstration content.
