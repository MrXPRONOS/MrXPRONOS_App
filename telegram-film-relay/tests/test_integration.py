"""Entire relay contract tested with an in-memory fake Telegram client; no API calls."""
import asyncio
import io
import json
import os
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from film_relay import runner
from film_relay.state import State


DATE = datetime(2026, 10, 15, tzinfo=timezone.utc)
SRC, PRIV, PUB = -1009012345678, -1001020304050, -1005060708090
MIRROR = -1008080808080


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
        self.public = NS(peer_id=PUB, broadcast=True, username='public_legal', title='Canal public de test')
        self.source = NS(peer_id=SRC, noforwards=False)
        self.mirror = NS(peer_id=MIRROR, broadcast=True, username='Torrent9SeriesFilms')
        self.mirror_should_fail = False
        self.forwarded = []
        self._next = 100

    async def connect(self): pass
    async def start(self, bot_token=None): return self
    async def get_me(self): return NS(username='football_bot_test')
    async def get_permissions(self, channel, user): return NS(is_creator=True, is_admin=True, post_messages=True)
    async def disconnect(self): pass
    async def download_media(self, media, file=bytes): return str(media).encode("utf-8")
    async def is_user_authorized(self): return True
    async def get_entity(self, value):
        if value == PRIV or str(value) == str(PRIV): return self.private
        if value == '@public_legal' or value == PUB: return self.public
        if value == '@Torrent9SeriesFilms': return self.mirror
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

    async def forward_messages(self, to, msg_id, *, from_peer):
        if self.mirror_should_fail:
            raise RuntimeError("Secondary channel unavailable")
        self._next += 1
        self.forwarded.append(NS(destination=to.peer_id, source=from_peer.peer_id,
                                 origin_id=msg_id, id=self._next))
        return NS(id=self._next)

    async def send_file(self, entity, media, *, caption, parse_mode=None, **options):
        if self.fail_on_send is not None and len(self.sent) + 1 == self.fail_on_send:
            raise RuntimeError('simulated Telegram transport failure')
        self._next += 1
        if isinstance(media, io.BytesIO):
            media = media.name if str(getattr(media, "name", "")).startswith("mrx_") else media.getvalue().decode("utf-8")
        self.sent.append(NS(channel=entity.peer_id, media=media, caption=caption,
                            parse_mode=parse_mode, options=options, id=self._next))
        return NS(id=self._next)


def mocks_for(client):
    telethon = types.ModuleType('telethon')
    telethon.TelegramClient = lambda *args, **kwargs: client
    telethon.utils = NS(get_peer_id=lambda entity: entity.peer_id)
    telethon.Button = NS(url=lambda label, url: (label, url))
    sessions = types.ModuleType('telethon.sessions')
    sessions.StringSession = lambda content='': content
    return {'telethon': telethon, 'telethon.sessions': sessions}


class RelayEndToEndTests(unittest.TestCase):
    def start(self, client, cfg_path, state_path):
        environment = {
            'TG_API_ID': '12345', 'TG_API_HASH': 'not-real', 'TG_STRING_SESSION': 'fake',
            'TG_RIGHTS_ATTESTED': 'true', 'FILM_PUBLISH_ENABLED': 'true',
            'CINEX_BOT_TOKEN': '123:fake-bot-token',
            'CHANNELS_CONFIG': str(cfg_path), 'STATE_PATH': str(state_path),
            'CINEX_PROMO_ASSETS_DIR': str(Path(state_path).parent / 'promo-assets'),
        }
        with patch.dict(os.environ, environment), patch.dict(sys.modules, mocks_for(client)):
            with patch.object(runner.asyncio, 'sleep', new=AsyncMock()):
                return asyncio.run(runner.execute())

    def setup_files(self, temp, max_posts=5, with_mirror=False):
        assets = Path(temp) / 'promo-assets'
        assets.mkdir(exist_ok=True)
        for i, name in enumerate(('actu', 'live', 'jour')):
            Image.new('RGB', (480, 600), (20+i*30, 40, 60)).save(assets / f'mrx_{name}.png')
        cfg_file = Path(temp) / 'config.json'
        cfg_file.write_text(json.dumps({
            'sources': [{'channel': '@source_legal', 'redistribution_authorized': True}],
            'private_channel': str(PRIV), 'public_channel': '@public_legal',
            'private_invite_link': 'https://t.me/+JOIN', 'private_layout': 'poster_and_video',
            'max_posts_per_run': max_posts, 'bootstrap_messages': 150, 'lookback_ids': 80,
            **({'mirror_channel': '@Torrent9SeriesFilms'} if with_mirror else {}),
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
            self.assertTrue(client.sent[1].caption.startswith('<b>🎞️ Excellente histoire'))
            self.assertNotIn('http', client.sent[1].caption)
            self.assertNotIn('https://t.me/c/1020304050/102', client.sent[2].caption)
            self.assertEqual(client.sent[2].options['buttons'][0][0][1], 'https://t.me/c/1020304050/102')
            self.assertIn('<b>', client.sent[2].caption)
            self.assertEqual(State(str(state)).seen(str(SRC)), 11)
            second_client = FakeTelegramClient(sample_messages())
            self.assertEqual(self.start(second_client, cfg, state), 0)
            self.assertEqual(second_client.sent, [])

    def test_mirror_forwards_original_public_post(self):
        with TemporaryDirectory() as temp:
            cfg, state = self.setup_files(temp, with_mirror=True)
            first = FakeTelegramClient(sample_messages())
            self.assertEqual(self.start(first, cfg, state), 0)
            self.assertEqual(len(first.sent), 3)
            self.assertEqual(len(first.forwarded), 1)
            forwarded = first.forwarded[0]
            self.assertEqual(forwarded.destination, MIRROR)
            self.assertEqual(forwarded.source, PUB)
            self.assertEqual(forwarded.origin_id, first.sent[-1].id)
            self.assertTrue(State(str(state)).mirrored(f'{SRC}:10:11', str(MIRROR)))
            second = FakeTelegramClient(sample_messages())
            self.assertEqual(self.start(second, cfg, state), 0)
            self.assertEqual(len(second.sent), 0)
            self.assertEqual(len(second.forwarded), 0)

    def test_mirror_failure_retries_without_reupload(self):
        with TemporaryDirectory() as temp:
            cfg, state = self.setup_files(temp, with_mirror=True)
            first = FakeTelegramClient(sample_messages())
            first.mirror_should_fail = True
            self.assertEqual(self.start(first, cfg, state), 1)
            self.assertEqual(len(first.sent), 3)
            self.assertEqual(len(State(str(state)).pending_mirrors(str(MIRROR))), 1)
            second = FakeTelegramClient(sample_messages())
            self.assertEqual(self.start(second, cfg, state), 0)
            self.assertEqual(len(second.sent), 0)
            self.assertEqual(len(second.forwarded), 1)
            self.assertTrue(State(str(state)).mirrored(f'{SRC}:10:11', str(MIRROR)))

    def test_two_films_trigger_all_three_button_promos(self):
        with TemporaryDirectory() as temp:
            cfg, state = self.setup_files(temp, max_posts=2, with_mirror=True)
            client = FakeTelegramClient(sample_messages(count=2))
            self.assertEqual(self.start(client, cfg, state), 0)
            ads = [x for x in client.sent if x.media == "mrx_actu.png"]
            self.assertEqual([x.channel for x in ads], [PUB, PRIV])
            self.assertTrue(all(len(x.caption.splitlines()) == 3 for x in ads))
            self.assertTrue(all(x.options["buttons"][0][0][1] ==
                                "https://t.me/actufoot_mrxp" for x in ads))
            forwarded = [x for x in client.forwarded if x.origin_id == ads[0].id]
            self.assertEqual(len(forwarded), 1)
            self.assertEqual(forwarded[0].destination, MIRROR)
            promos = State(str(state)).data["promotions"]
            self.assertEqual(len(promos), 3)
            self.assertTrue(all(p["next_index"] == 1 for p in promos.values()))

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
            self.assertEqual(second.sent[0].options['buttons'][0][0][1], 'https://t.me/c/1020304050/102')
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
            self.assertEqual([x.media for x in second.sent[:3]], ['poster-1', 'video-1', 'poster-1'])
            self.assertEqual([x.media for x in second.sent[3:]], ['mrx_actu.png', 'mrx_actu.png'])
            self.assertEqual(State(str(state)).seen(str(SRC)), 13)


if __name__ == '__main__':
    unittest.main()
