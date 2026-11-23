"""Offline-only checks for 24h public video expiration and private safety."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from film_relay.public_video_retention import (
    due_for_removal, select_due, process_public,
)


NOW = datetime(2026, 11, 23, 0, 0, tzinfo=timezone.utc)


def video(mid, age_hours, doc=None):
    return NS(
        id=mid, date=NOW - timedelta(hours=age_hours),
        video=object(), document=NS(id=mid + 900 if doc is None else doc,
                                    attributes=[]),
    )


class RetentionTests(unittest.TestCase):
    def test_24_hour_boundary_and_legacy_posts(self):
        self.assertFalse(due_for_removal(video(1, 23.99), NOW))
        self.assertTrue(due_for_removal(video(2, 24), NOW))
        self.assertTrue(due_for_removal(video(3, 48), NOW))
        self.assertFalse(due_for_removal(NS(id=4, date=NOW - timedelta(days=7),
                                          video=None, document=None), NOW))
        self.assertFalse(due_for_removal(NS(id=5, date=None, video=object(),
                                          document=NS(id=8, attributes=[])), NOW))

    def test_oldest_first_and_photo_excluded(self):
        msgs = [video(2, 24), video(1, 60), video(3, 2)]
        self.assertEqual([x.id for x in select_due(msgs, NOW)], [1, 2])

    def test_public_cleanup_caps_and_maintains_posters(self):
        a, b = video(10, 100), video(11, 72)
        photo = NS(id=9, date=NOW - timedelta(days=9), photo=object(),
                   video=None, document=None)
        rows = {10: a, 11: b, 9: photo}
        deleted = []

        class Client:
            async def iter_messages(self, entity, limit):
                for item in [b, photo, a]:
                    yield item

            async def get_me(self):
                return NS(id=45)

            async def get_permissions(self, channel, who):
                return NS(is_creator=True)

            async def get_messages(self, channel, ids):
                return rows.get(ids)

            async def delete_messages(self, channel, ids, revoke=True):
                self.revoke = revoke
                deleted.extend(ids)
                for key in ids:
                    rows.pop(key, None)

        public = NS(id=-1001234567890, username="CineXFilms_vf", broadcast=True)
        with (patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id),
              patch("asyncio.sleep", new=AsyncMock())):
            report = asyncio.run(process_public(
                Client(), category="films", public=public,
                private_id=-1002222222222, apply=True, now=NOW, max_deleted=1,
            ))
        self.assertEqual(report["expired_videos"], 2)
        self.assertEqual(report["deleted"], 1)
        self.assertEqual(report["not_deleted"], 1)
        self.assertEqual(deleted, [10])
        self.assertIn(9, rows)
        self.assertIn(11, rows)

    def test_never_deletes_private_or_wrong_destination(self):
        class Client:
            async def iter_messages(self, entity, limit):
                yield video(1, 48)
        with patch("telethon.utils.get_peer_id", side_effect=lambda p: p.id):
            for peer in (
                NS(id=-1001111111111, username=None, broadcast=True),
                NS(id=-1001111111111, username="testprivate", broadcast=False),
            ):
                with self.assertRaisesRegex(RuntimeError, "refuse"):
                    asyncio.run(process_public(
                        Client(), category="films", public=peer,
                        private_id=-1002222222222, apply=True, now=NOW,
                    ))


if __name__ == "__main__":
    unittest.main()
