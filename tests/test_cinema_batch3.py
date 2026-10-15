"""Offline tests; the repo's actual cinema_telegram module is used on GitHub."""
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
if not (ROOT / 'scripts' / 'cinema_telegram.py').exists():
    # Local isolated test directory: emulate only the base functions batch3 needs.
    stub = types.ModuleType('cinema_telegram')
    stub.TMDB = 'https://api.themoviedb.org/3'
    stub.short = lambda value, limit=100: str(value)[:limit]
    stub.footer = lambda demo: '<p><i>DEMO</i></p>' if demo else '<p><i>Source TMDB</i></p>'
    stub.year = lambda movie: str(movie.get('release_date', ''))[:4]
    stub.valid_tmdb_path = lambda path: isinstance(path, str) and path.startswith('/') and '..' not in path
    stub.target_chat = lambda mode: '@predict_mrxp' if mode == 'test' else os.environ.get('CINEMA_PRODUCTION_CHAT_ID')
    stub.verify_test_bot = lambda *a: True
    stub.post_text = lambda *a, **kw: 234
    stub.post_photo = lambda *a, **kw: 235
    stub.download_source_image = lambda *a, **kw: (None, None)
    stub.call_telegram = lambda *a, **kw: {'message_id': 236}
    sys.modules['cinema_telegram'] = stub
import cinema_batch3 as cm


class BatchThreeTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 10, 15)

    def test_all_five_drafts(self):
        for kind in cm.FORMATS:
            with self.subTest(kind=kind):
                html, rows = cm.render(kind, cm.demo_selection(kind), self.day, True)
                self.assertIn('<h3>', html)
                self.assertIn('<i>', html)
                self.assertIn('<blockquote>', html)
                self.assertIn('<b>', html)
                self.assertTrue(rows)
                self.assertTrue(all(len(row) == 1 for row in rows))
                self.assertTrue(all(row[0]['url'].startswith('https://') for row in rows))

    def test_escape_external_names(self):
        data = {'items': [dict(cm.DEMO_MOVIES[0], title='<img src=x onerror=evil()>')], 'directors': ['<script>alert(1)</script>']}
        html, _ = cm.render('anecdote', data, self.day)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=', html)
        self.assertIn('&lt;script&gt;', html)

    def test_boxoffice_is_cumulative_not_weekly(self):
        html, _ = cm.render('boxoffice', cm.demo_selection('boxoffice'), self.day)
        self.assertIn('recettes mondiales cumulées', html)
        self.assertIn('pas un classement hebdomadaire', html)
        self.assertIn('50 000 000 $', html)

    def test_duel_poll_has_two_options(self):
        data = cm.poll_payload(cm.DEMO_MOVIES[:2], '@predict_mrxp')
        self.assertEqual(len(data['options']), 2)
        self.assertEqual(data['type'], 'regular')
        self.assertEqual(data['chat_id'], '@predict_mrxp')

    def test_duel_recovers_after_partial_send(self):
        session = MagicMock()
        with patch.object(cm.base, 'post_text', return_value=91) as post, \
             patch.object(cm.base, 'call_telegram', return_value={'message_id': 92}) as poll:
            updates=[]
            result=cm.publish('duel', cm.demo_selection('duel'), '@predict_mrxp', 'test', session, self.day,
                              demo=True, on_progress=lambda x: updates.append(dict(x)))
            self.assertEqual(result['photo_message_id'], 91)
            self.assertEqual(result['poll_message_id'], 92)
            self.assertEqual(len(updates), 2)
            self.assertEqual(poll.call_count, 1)
            post.assert_called_once()
            retry=cm.publish('duel', cm.demo_selection('duel'), '@predict_mrxp', 'test', session, self.day,
                             demo=True, previous=updates[0])
            self.assertEqual(retry['photo_message_id'], 91)
            self.assertEqual(poll.call_count, 2)
            self.assertEqual(post.call_count, 1)

    def test_no_fabricated_photos_in_demo(self):
        with patch.object(cm.base, 'post_photo', side_effect=AssertionError('Synthetic photo forbidden')), \
             patch.object(cm.base, 'post_text', return_value=234):
            out=cm.publish('anecdote', cm.demo_selection('anecdote'), '@predict_mrxp', 'test', MagicMock(), self.day, demo=True)
            self.assertEqual(out['photo_message_id'], 234)

    def test_missing_real_source_image_blocks_post(self):
        with patch.object(cm.base, 'download_source_image', return_value=(None, None)), \
             patch.object(cm.base, 'post_text', side_effect=AssertionError('No fallback')):
            with self.assertRaises(RuntimeError):
                cm.publish('anecdote', cm.demo_selection('anecdote'), '@predict_mrxp', 'test', MagicMock(), self.day)

    def test_untouched_image_passed_to_publisher(self):
        data=b'\xff\xd8\xff'+b'original photo payload'
        def save(items,session,folder):
            source=folder/'official.jpg'
            source.write_bytes(data)
            return source,'image/jpeg'
        with patch.object(cm.base,'download_source_image',side_effect=save), \
             patch.object(cm.base,'post_photo',return_value=44) as output:
            result=cm.publish('anecdote',cm.demo_selection('anecdote'),'@predict_mrxp','token',MagicMock(),self.day)
            self.assertEqual(result['photo_message_id'],44)
            self.assertEqual(output.call_args.kwargs['mime'],'image/jpeg')

    def test_official_trailer_selection(self):
        movie=dict(cm.DEMO_MOVIES[0], poster_path='/safe.jpg')
        fakeclips={'results':[{'site':'YouTube','type':'Trailer','official':False,'key':'11111111111'},
                              {'site':'YouTube','type':'Trailer','official':True,'key':'A1b2C3d4E5f'}]}
        with patch.object(cm.TMDB,'trending',return_value=[movie]),patch.object(cm.TMDB,'get',return_value=fakeclips):
            selection=cm.TMDB('fake').pick('bandeannonce', self.day)
            self.assertEqual(selection['video_url'],'https://www.youtube.com/watch?v=A1b2C3d4E5f')

    def test_fact_requires_verified_director(self):
        movie=dict(cm.DEMO_MOVIES[0], poster_path='/safe.jpg')
        with patch.object(cm.TMDB,'trending',return_value=[movie]), \
             patch.object(cm.TMDB,'get',return_value={'crew':[{'job':'Director','name':'Jane Doe'}]}):
            selection=cm.TMDB('fake').pick('anecdote',self.day)
            self.assertEqual(selection['directors'],['Jane Doe'])

    def test_revenue_zero_is_not_included(self):
        movies=[dict(m,poster_path='/valid.jpg') for m in cm.DEMO_MOVIES]
        def get(path,**kwargs):
            if path.startswith('/movie/now_playing'):
                return {'results':movies}
            idx=int(path.split('/')[-1])
            return {'revenue':0 if idx==1001 else 5_000_000+idx}
        with patch.object(cm.TMDB,'get',side_effect=get):
            data=cm.TMDB('fake').pick('boxoffice',self.day)
            self.assertTrue(all(x['revenue']>0 for x in data['items']))
            self.assertNotIn(1001,[m['id'] for m in data['items']])

    def test_weekend_multiple_genres(self):
        movies=[dict(m,poster_path='/valid.jpg') for m in cm.DEMO_MOVIES]
        with patch.object(cm.TMDB,'trending',return_value=movies):
            data=cm.TMDB('fake').pick('weekend',self.day)
            self.assertEqual(len(data['items']),4)
            self.assertEqual(len(set(x['editorial_genre'] for x in data['items'])),4)

    def test_dry_run_never_posts(self):
        with patch.object(cm.base, 'post_photo',side_effect=AssertionError('Network attempted')), \
             patch.object(cm.base, 'post_text',side_effect=AssertionError('Network attempted')), \
             patch.object(cm.base, 'call_telegram',side_effect=AssertionError('Network attempted')):
            for kind in cm.FORMATS:
                self.assertIsNone(cm.publish(kind,cm.demo_selection(kind),'@predict_mrxp',None,MagicMock(),self.day,demo=True,dry_run=True))

    def test_demo_forbidden_in_production(self):
        with self.assertRaises(SystemExit):
            cm.run(['--mode','production','--demo','--dry-run'])

    def test_test_destination_fixed(self):
        self.assertEqual(cm.base.target_chat('test'), '@predict_mrxp')


if __name__=='__main__':
    unittest.main()
# Dedicated one-time TMDB source-image smoke test on @predict_mrxp; no production posts.
