import os
import sys
import tempfile
import unittest
import types
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
if not (Path(__file__).resolve().parents[1] / 'scripts' / 'telegram_rich.py').exists():
    stub = types.ModuleType('telegram_rich')
    stub.post_photo = lambda *args, **kwargs: None
    sys.modules['telegram_rich'] = stub
import cinema_batch2 as c


class CinemaBatch2Tests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 10, 15)

    def test_all_four_rich_formats(self):
        for kind in c.FORMATS[:4]:
            with self.subTest(kind=kind):
                items = [c.MOCK_ACTOR] if kind == 'acteur' else (c.MOCK_SERIES if kind == 'series' else c.MOCK_MOVIES)
                html, keyboard = c.caption(kind, items, self.day, True)
                self.assertIn('<h3>', html)
                self.assertIn('<i>', html)
                self.assertIn('<blockquote>', html)
                self.assertIn('<b>', html)
                self.assertEqual(len(keyboard), 1)
                self.assertEqual(len(keyboard[0]), 1)
                self.assertEqual(keyboard[0][0]['style'], 'primary')

    def test_escaping_external_data(self):
        movie = dict(c.MOCK_MOVIES[0], title='<b>BAD&STRANGE</b>')
        html, _ = c.caption('pepites', [movie], self.day)
        self.assertIn('&lt;b&gt;', html)
        self.assertNotIn('<b>BAD', html)

    def test_normalized_tv(self):
        rows = c.API.normalize([{'id': 55, 'name': 'Test TV', 'first_air_date': '2026-08-01', 'adult': False}], 'tv')
        self.assertEqual(rows[0]['title'], 'Test TV')
        self.assertEqual(rows[0]['media_type'], 'tv')
        self.assertEqual(rows[0]['release_date'], '2026-08-01')

    def test_api_selects_five_series(self):
        data = {'results': [{'id': i, 'name': 'Série ' + str(i), 'vote_count': 200,
                             'popularity': 300-i, 'poster_path': '/test.jpg', 'adult': False} for i in range(1, 9)]}
        with patch.object(c.API, 'call', return_value=data):
            selected = c.API('fake').pick('series', self.day)
            self.assertEqual(len(selected), 5)
            self.assertEqual(len({x['id'] for x in selected}), 5)
            self.assertEqual(selected[0]['media_type'], 'tv')

    def test_avoids_recent_picks(self):
        data = {'results': [{'id': i, 'name': 'Série '+str(i), 'vote_count': 200, 'poster_path': '/test.jpg'} for i in range(1, 10)]}
        with patch.object(c.API, 'call', return_value=data):
            selected = c.API('fake').pick('series', self.day, {'series':[1,2,3,4]})
            self.assertTrue(all(x['id'] not in (1,2,3,4) for x in selected))

    def test_native_poll(self):
        data = c.poll_payload(c.MOCK_MOVIES, '@predict_mrxp')
        self.assertEqual(data['type'], 'regular')
        self.assertEqual(len(data['options']), 4)
        self.assertTrue(all(isinstance(x, dict) for x in data['options']))
        with patch.object(c.base, 'call_telegram', return_value={'message_id': 22}):
            self.assertEqual(c.publish('sondage', c.MOCK_MOVIES, '@predict_mrxp', 'fake', MagicMock(), self.day), 22)

    def test_publication_uses_original_poster(self):
        session = MagicMock()
        media = [dict(c.MOCK_MOVIES[0], poster_path='/abc123.jpg')]
        with patch.object(c.base, 'download_source_image', return_value=(Path('/tmp/original.jpg'), 'image/jpeg')) as download, patch.object(c.base, 'post_photo', return_value=22) as photo:
            mid = c.publish('pepites', media, '@predict_mrxp', 'token', session, self.day)
            self.assertEqual(mid, 22)
            self.assertTrue(download.called)
            self.assertEqual(photo.call_args.kwargs['mime'], 'image/jpeg')

    def test_demo_has_no_invented_image(self):
        with patch.object(c.base, 'post_photo', side_effect=AssertionError('invented image')), patch.object(c.base, 'post_text', return_value=33) as text:
            sent = c.publish('series', c.MOCK_SERIES, '@predict_mrxp', 'token', MagicMock(), self.day, demo=True)
            self.assertEqual(sent, 33)
            self.assertTrue(text.call_args.kwargs['html'])

    def test_actor_needs_source_portrait(self):
        with patch.object(c.base, 'download_source_image', return_value=(None, None)) as download, patch.object(c.base, 'post_text', return_value=17) as text:
            self.assertEqual(c.publish('acteur', [c.MOCK_ACTOR], '@predict_mrxp', 'token', MagicMock(), self.day), 17)
            self.assertTrue(download.call_args.kwargs['person'])
            self.assertTrue(text.called)

    def test_dry_run_never_sends(self):
        with patch.object(c.base, 'post_photo', side_effect=AssertionError('network')), patch.object(c.base, 'call_telegram', side_effect=AssertionError('network')):
            for kind in c.FORMATS:
                items = [c.MOCK_ACTOR] if kind == 'acteur' else c.MOCK_MOVIES
                c.publish(kind, items, '@predict_mrxp', 'fake', MagicMock(), self.day, True, True)

    def test_demo_blocked_in_production(self):
        with self.assertRaises(SystemExit):
            c.run(['--mode', 'production', '--demo', '--dry-run'])

    def test_no_token_no_live(self):
        with patch.dict(os.environ, {'CINEMA_TELEGRAM_BOT_TOKEN':'', 'TELEGRAM_BOT_TOKEN':''}):
            with self.assertRaises(SystemExit):
                c.run(['--mode', 'test', '--format', 'sondage'])

    def test_target_is_strict(self):
        self.assertEqual(c.base.target_chat('test'), '@predict_mrxp')


if __name__ == '__main__':
    unittest.main()