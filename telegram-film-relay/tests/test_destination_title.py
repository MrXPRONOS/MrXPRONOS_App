"""Safeguards against publishing to the wrong Telegram destination."""
import asyncio
import unittest
from types import SimpleNamespace
from film_relay.runner import find_broadcast_by_exact_title

class FakeClient:
    def __init__(self, dialogs):
        self.dialogs = dialogs

    async def iter_dialogs(self):
        for entity in self.dialogs:
            yield SimpleNamespace(entity=entity)

class DestinationTests(unittest.TestCase):
    def test_super_mario_film_unique_match(self):
        client = FakeClient([
            SimpleNamespace(title="Other Channel", broadcast=True),
            SimpleNamespace(title="Super Mario Film", broadcast=True),
            SimpleNamespace(title="Super Mario Film", broadcast=False),
        ])
        matches = asyncio.run(find_broadcast_by_exact_title(client, " SUPER  MARIO film "))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].title, "Super Mario Film")

    def test_ambiguous_names_do_not_select_one(self):
        client = FakeClient([
            SimpleNamespace(title="Super Mario Film", broadcast=True),
            SimpleNamespace(title="SUPER MARIO FILM", broadcast=True),
        ])
        matches = asyncio.run(find_broadcast_by_exact_title(client, "Super Mario Film"))
        self.assertEqual(len(matches), 2)

    def test_no_match(self):
        client = FakeClient([SimpleNamespace(title="Cinema", broadcast=True)])
        self.assertEqual(asyncio.run(find_broadcast_by_exact_title(client, "Super Mario Film")), [])
