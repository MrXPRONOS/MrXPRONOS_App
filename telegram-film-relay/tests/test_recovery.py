"""Regression checks against reruns after remote checkpoint push conflicts."""
import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS

from film_relay.recovery import (
    TelegramReceiptCache, movie_document_id,
    referenced_private_messages, snapshot_telegram_posts,
    recover_from_snapshot, existing_native_forwards,
)
from film_relay.state import State
from scripts.merge_state import combine

PRIVATE = -1004392607284
PUBLIC = -1005070707070


def video(doc_id, msg_id):
    return NS(id=msg_id, document=NS(id=doc_id), reply_markup=None,
              raw_text="", fwd_from=None)


def public_post(msg_id, video_id):
    link = f"https://t.me/c/4392607284/{video_id}"
    btn = NS(url=link)
    markup = NS(rows=[NS(buttons=[btn])])
    return NS(id=msg_id, document=None, reply_markup=markup, raw_text="Titre",
              buttons=None, fwd_from=None)


class FakeClient:
    def __init__(self, private=None, public=None, mirror=None):
        self.data = {"private": private or [], "public": public or [],
                     "mirror": mirror or []}

    async def iter_messages(self, entity, *, limit):
        for item in self.data[entity][:limit]:
            yield item


class RecoveryTests(unittest.TestCase):
    def test_recovers_complete_post_after_failed_git_push(self):
        client = FakeClient(
            private=[video(456, 15), video(456, 13)],
            public=[public_post(25, 15), public_post(23, 13)]
        )
        cache = asyncio.run(snapshot_telegram_posts(client, "private", "public", PRIVATE))
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            result = recover_from_snapshot(
                cache, state, "source:27:28", "doc:456", video(456, 28)
            )
            self.assertEqual(result, "complete")
            self.assertTrue(state.recorded("source:27:28", "doc:456"))
            self.assertEqual(state.data["processed"]["source:27:28"],
                             {"private_message_id": 15, "public_message_id": 25})

    def test_recovers_private_video_without_reupload(self):
        cache = TelegramReceiptCache({456: [7]}, {})
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            self.assertEqual(recover_from_snapshot(
                cache, state, "source:27:28", "doc:456", video(456, 28)
            ), "staged")
            self.assertEqual(state.get_stage("source:27:28"), 7)
            self.assertFalse(state.recorded("source:27:28", "doc:456"))

    def test_no_fuzzy_matching_by_title_or_filename(self):
        cache = TelegramReceiptCache({999: [7]}, {7: 25})
        with TemporaryDirectory() as folder:
            state = State(str(Path(folder) / "state.json"))
            self.assertEqual(recover_from_snapshot(
                cache, state, "source:27:28", "doc:456", video(456, 28)
            ), "none")

    def test_public_button_channel_must_match_exact_private(self):
        msg = public_post(5, 17)
        self.assertEqual(referenced_private_messages(msg, PRIVATE), {17})
        self.assertEqual(referenced_private_messages(msg, -10033333333), set())

    def test_existing_forward_recovers_original_public_id(self):
        fw = NS(from_id=NS(channel_id=5070707070), channel_post=31)
        client = FakeClient(mirror=[NS(id=44, fwd_from=fw),
                                    NS(id=45, fwd_from=None)])
        result = asyncio.run(existing_native_forwards(client, "mirror", PUBLIC))
        self.assertEqual(result, {31: 44})

    def test_merge_retains_both_parallel_receipts(self):
        remote = {
            "processed": {"one": {"private_message_id": 5, "public_message_id": 6}},
            "videos": {"doc:1": "one"},
            "last_seen": {"source": 100},
            "staged": {"three": {"video": 15}}
        }
        incoming = {
            "processed": {"two": {"private_message_id": 7, "public_message_id": 8}},
            "videos": {"doc:2": "two"},
            "last_seen": {"source": 90},
            "staged": {"two": {"video": 7}}
        }
        m = combine(remote, incoming)
        self.assertEqual(set(m["processed"]), {"one", "two"})
        self.assertEqual(m["last_seen"]["source"], 100)
        self.assertNotIn("two", m["staged"])
        self.assertIn("three", m["staged"])

    def test_identity_extraction_from_document(self):
        self.assertEqual(movie_document_id(video(987, 2)), 987)
        self.assertIsNone(movie_document_id(NS(document=None)))


if __name__ == "__main__":
    unittest.main()
