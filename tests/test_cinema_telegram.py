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
    stub.post_text = lambda *args, **kwargs: None
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
        with patch.object(cm.TMDBClient, 'get', return_value=[dict(m, poster_path='/test.jpg') for m in cm.DEMO]):
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

    def test_original_tmdb_image_unchanged(self):
        import tempfile
        picture = b'\xff\xd8\xff' + bytes(range(256))
        response = MagicMock(content=picture)
        with tempfile.TemporaryDirectory() as directory:
            session = MagicMock()
            session.get.return_value = response
            images = [dict(cm.DEMO[0], poster_path='/original.jpg')]
            path, mime = cm.download_source_image(images, session, Path(directory))
            self.assertEqual(path.read_bytes(), picture)
            self.assertEqual(mime, 'image/jpeg')
            session.get.assert_called_once_with(cm.IMG+'/original.jpg', timeout=25)

    def test_no_placeholder_image_when_missing(self):
        with patch.object(cm, 'post_text', return_value=77) as text, patch.object(cm, 'post_photo', side_effect=AssertionError('invented photo')):
            sent = cm.publish('film', cm.DEMO, 'token', '@predict_mrxp', self.day, MagicMock())
            self.assertEqual(sent, 77)
            self.assertTrue(text.call_args.kwargs['html'])

    def test_demo_never_downloads_image(self):
        session = MagicMock()
        with patch.object(cm, 'post_text', return_value=44) as text:
            self.assertEqual(cm.publish('film', cm.DEMO, 't', '@predict_mrxp', self.day, session, demo=True), 44)
            session.get.assert_not_called()
            self.assertEqual(text.call_count, 1)

    def test_reject_invalid_provider_paths(self):
        self.assertFalse(cm.valid_tmdb_path('https://example.com/a.jpg'))
        self.assertFalse(cm.valid_tmdb_path('/../secret.jpg'))
        self.assertTrue(cm.valid_tmdb_path('/ab-C_12.jpg'))

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
# Smoke test: verify unmodified TMDB posters in @predict_mrxp.
