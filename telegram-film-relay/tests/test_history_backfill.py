"""Archive paging and checkpoint regression tests, without Telegram credentials."""
import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS

from film_relay.runner import load_archive_messages
from film_relay.state import State


class FakeArchive:
    def __init__(self, size):
        self.ids = list(range(1, size + 1))
        self.calls = []

    async def iter_messages(self, entity, *, limit, max_id=None):
        self.calls.append((limit, max_id))
        ids = [x for x in reversed(self.ids) if max_id is None or x < max_id]
        for id in ids[:limit]:
            yield NS(id=id)


class HistoryTests(unittest.TestCase):
    def test_walks_to_oldest(self):
        with TemporaryDirectory() as d:
            s = State(str(Path(d) / 'state.json'))
            c = FakeArchive(89)
            seen = []
            for _ in range(10):
                page, cursor, done = asyncio.run(load_archive_messages(
                    c, object(), s, 'source', {'history_page_messages': 30,
                                              'history_overlap_messages': 5}))
                seen.extend(x.id for x in page)
                s.advance_history('source', cursor, done)
                if done:
                    break
            self.assertTrue(s.history_done('source'))
            self.assertEqual(set(seen), set(range(1, 90)))
            self.assertGreater(len(seen), 89)
            before = len(c.calls)
            page, _, done = asyncio.run(load_archive_messages(c, object(), s, 'source', {}))
            self.assertEqual(page, [])
            self.assertTrue(done)
            self.assertEqual(len(c.calls), before)

    def test_archive_cycle_restarts_after_reaching_oldest_message(self):
        with TemporaryDirectory() as d:
            state = State(str(Path(d) / 'state.json'))
            state.advance_history('source', None, True)
            client = FakeArchive(11)
            page, next_cursor, done = asyncio.run(load_archive_messages(
                client, object(), state, 'source',
                {'history_page_messages': 30, 'history_overlap_messages': 5,
                 'archive_cycle': True}
            ))
            self.assertEqual([x.id for x in page], list(range(1, 12)))
            self.assertTrue(done)
            self.assertIsNone(next_cursor)

    def test_resume(self):
        with TemporaryDirectory() as d:
            path = str(Path(d) / 'state.json')
            c = FakeArchive(91)
            s = State(path)
            first, next_id, done = asyncio.run(load_archive_messages(c, object(), s, 'source',
                {'history_page_messages': 30, 'history_overlap_messages': 5}))
            again, _, _ = asyncio.run(load_archive_messages(c, object(), s, 'source',
                {'history_page_messages': 30, 'history_overlap_messages': 5}))
            self.assertEqual([x.id for x in first], [x.id for x in again])
            s.advance_history('source', next_id, done)
            later, _, _ = asyncio.run(load_archive_messages(c, object(), State(path), 'source',
                {'history_page_messages': 30, 'history_overlap_messages': 5}))
            self.assertLess(max(x.id for x in later), max(x.id for x in first))
