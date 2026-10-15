"""Entire relay contract tested with an in-memory fake Telegram client; no API calls."""
import asyncio
import json
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from film_relay import runner
from film_relay.state import State


DATE = datetime(2026, 10, 15, tzinfo=timezone.utc)
SRC, PRIV, PUB = -1009012345678, -1001020304050, -1005060708090


def sample_messages(count=1):
    found = []
    for i in range(count):
        k = 10 + i * 2
        doc = NS(id=100 + i, mime_type='video/mp4', size=500_000_000)
        found += [
            NS(id=k, photo=object(), document=None, video=None, media=f'poster-{i}',
               raw_text=f'🎬 Excellente histoire numéro {i + 1}\nRésumé du film\nhttps://t.me/promo',
               date=DATE + timedelta(minutes=i*10), file=None,
               entities=None, grouped_id=None, reply_to=None, noforwards=False),
            NS(id=k+1, photo=None, document=doc, video=doc, media=f'video-{i}',
               raw_text='', date=DATE + timedelta(minutes=i*10+1),
               file=NS(name='movie.mp4', duration=7200, size=doc.size),
               entities=None, grouped_id=None, reply_to=None, noforwards=False),
        ]
    return found


class FakeTelegramClient:
    def __init__(self, samples, fail_on_send=None):
        self.samples = samples
        self.fail_on_send = fail_on_send
        self.sent = []
        self.private = NS(peer_id=PRIV)
        self.public = NS(peer_id=PUB)
        self.source = NS(peer_id=SRC, noforwards=False)
        self._next = 100

    async def connect(self): pass
    async def disconnect(self): pass
    async def is_user_authorized(self): return True
    async def get_entity(self, value):
        if value == PRIV or str(value) == str(PRIV): return self.private
        if value == '@public_legal': return self.public
        if value == '@source_legal': return self.source
        raise ValueError(value)

    async def iter_messages(self, entity, *, limit=10, min_id=0, reverse=False):
        if entity.peer_id != SRC:
            return
        found = [x for x in self.samples if x.id > min_id]
        if not reverse:
            found.reverse()
        for obj in found[:limit]:
            yield obj

    async def send_file(self, entity, media, *, caption, parse_mode=None):
        if self.fail_on_send is not None and len(self.sent) + 1 == self.fail_on_send:
            raise RuntimeError('simulated Telegram transport failure')
        self._next += 1
        self.sent.append(NS(channel=entity.peer_id, media=media, caption=caption, id=self._next))
        return NS(id=self._next)


def mocks_for(client):
    telethon = types.ModuleType('telethon')
    telethon.TelegramClient = lambda *args, **kwargs: client
    telethon.utils = NS(get_peer_id=lambda entity: entity.peer_id)
    sessions = types.ModuleType('telethon.sessions')
    sessions.StringSession = lambda content: content
    return {'telethon': telethon, 'telethon.sessions': sessions}


class RelayEndToEndTests(unittest.TestCase):
    def start(self, client, cfg_path, state_path):
        environment = {
            'TG_API_ID': '12345', 'TG_API_HASH': 'not-real', 'TG_STRING_SESSION': 'fake',
            'TG_RIGHTS_ATTESTED': 'true', 'FILM_PUBLISH_ENABLED': 'true',
            'CHANNELS_CONFIG': str(cfg_path), 'STATE_PATH': str(state_path),
        }
        with patch.dict(os.environ, environment), patch.dict(sys.modules, mocks_for(client)):
            with patch.object(runner.asyncio, 'sleep', new=AsyncMock()):
                return asyncio.run(runner.execute())

    def setup_files(self, temp, max_posts=5):
        cfg_file = Path(temp) / 'config.json'
        cfg_file.write_text(json.dumps({
            'sources': [{'channel': '@source_legal', 'redistribution_authorized': True}],
            'private_channel': str(PRIV), 'public_channel': '@public_legal',
            'private_invite_link': 'https://t.me/+JOIN', 'private_layout': 'poster_and_video',
            'max_posts_per_run': max_posts, 'bootstrap_messages': 150, 'lookback_ids': 80,
        }))
        return cfg_file, Path(temp) / 'state.json'

    def test_private_poster_then_video_public_poster_with_link(self):
        with TemporaryDirectory() as temp:
            cfg, state = self.setup_files(temp)
            client = FakeTelegramClient(sample_messages())
            self.assertEqual(self.start(client, cfg, state), 0)
            self.assertEqual([x.channel for x in client.sent], [PRIV, PRIV, PUB])
            self.assertEqual([x.media for x in client.sent], ['poster-0', 'video-0', 'poster-0'])
            self.assertIn('Résumé du film', client.sent[0].caption)
            self.assertNotIn('t.me', client.sent[0].caption)
            self.assertTrue(client.sent[1].caption.startswith('🎬 Excellente histoire'))
            self.assertNotIn('http', client.sent[1].caption)
            self.assertIn('https://t.me/c/1020304050/102', client.sent[2].caption)
            self.assertEqual(State(str(state)).seen(str(SRC)), 11)
            second_client = FakeTelegramClient(sample_messages())
            self.assertEqual(self.start(second_client, cfg, state), 0)
            self.assertEqual(second_client.sent, [])

    def test_failure_after_private_video_resume_only_public(self):
        with TemporaryDirectory() as temp:
            cfg, state = self.setup_files(temp)
            first = FakeTelegramClient(sample_messages(), fail_on_send=3)
            self.assertEqual(self.start(first, cfg, state), 1)
            self.assertEqual(len(first.sent), 2)
            self.assertEqual(State(str(state)).get_staged_posts(f'{SRC}:10:11'), {'poster': 101, 'video': 102})
            second = FakeTelegramClient(sample_messages())
            self.assertEqual(self.start(second, cfg, state), 0)
            self.assertEqual(len(second.sent), 1)
            self.assertEqual(second.sent[0].channel, PUB)
            self.assertIn('/102', second.sent[0].caption)
            self.assertEqual(State(str(state)).get_staged_posts(f'{SRC}:10:11'), {})

    def test_publication_limit_does_not_drop_later_pairs(self):
        with TemporaryDirectory() as temp:
            cfg, state = self.setup_files(temp, max_posts=1)
            samples = sample_messages(count=2)
            first = FakeTelegramClient(samples)
            self.assertEqual(self.start(first, cfg, state), 0)
            self.assertEqual(len(first.sent), 3)
            self.assertEqual(State(str(state)).seen(str(SRC)), 11)
            second = FakeTelegramClient(samples)
            self.assertEqual(self.start(second, cfg, state), 0)
            self.assertEqual([x.media for x in second.sent], ['poster-1', 'video-1', 'poster-1'])
            self.assertEqual(State(str(state)).seen(str(SRC)), 13)


if __name__ == '__main__':
    unittest.main()
