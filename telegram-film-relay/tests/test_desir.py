"""Offline validation for independent CinéX Désir relay. No Telegram messages sent."""
import asyncio
import unittest
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS

from film_relay.desir_matching import is_supported_video, pair_items, film_title, item_key
from film_relay.desir_runner import (ReceiptState, DesirPromotionsState, verify_destination,
                                    forward_public_poster, finish_mirrors)


def photo(i, text=""):
    return NS(id=i, photo=object(), document=None, raw_text=text,
              noforwards=False)

def video(i, name, duration=None, protected=False):
    file = NS(name=name, duration=duration)
    document = NS(id=i+100000, mime_type="application/octet-stream", size=300000000)
    return NS(id=i, photo=None, document=document, file=file, raw_text="",
              noforwards=protected)


class DesirTests(unittest.TestCase):
    def test_mkv_without_duration_or_size_filter(self):
        doc = video(2, "a.mkv", None)
        doc.document.size = 100
        self.assertTrue(is_supported_video(doc))
        self.assertTrue(is_supported_video(video(3, "a.mp4", 7200)))
        self.assertFalse(is_supported_video(video(4, "a.avi")))
        self.assertFalse(is_supported_video(video(5, "a.mp4", protected=True)))

    def test_captionless_photo_pairs_with_mkv_and_mp4(self):
        pairs = pair_items([video(4, "film1.mkv"), photo(1), photo(3), video(2, "film0.mp4")])
        self.assertEqual([(v.poster.id if v.poster else None, v.video.id) for v in pairs],
                         [(1, 2), (3, 4)])

    def test_video_only_supported(self):
        result = pair_items([video(22, "Autre_Film.mkv")])
        self.assertIsNone(result[0].poster)
        self.assertIn("autre film", film_title(result[0]).lower())

    def test_new_photo_bounds_previous_pair(self):
        pairs = pair_items([photo(1), photo(2), video(3,"test.mkv")])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].poster.id, 2)

    def test_no_forward_for_protected_image(self):
        p = photo(1)
        p.noforwards = True
        pair = pair_items([p, video(2, "test.mkv")])
        self.assertEqual(len(pair), 1)
        self.assertIsNone(pair[0].poster)

    def test_source_destination_guard(self):
        verify_destination("@Filmromatique", "@CineXDesirfr", "-100123456789")
        with self.assertRaises(RuntimeError):
            verify_destination("@other", "@CineXDesirfr", "-100123456789")
        with self.assertRaises(RuntimeError):
            verify_destination("@Filmromatique", "@other", "-100123456789")
        with self.assertRaises(RuntimeError):
            verify_destination("@Filmromatique", "@CineXDesirfr", "@unknown")

    def test_mirror_receipts_survive_reload(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "desir.json")
            state = ReceiptState(path)
            state.complete("src:video", 70, 44)
            self.assertEqual(state.mirror_pending("-100999"), [44])
            state.mirror_done("-100999", 44, 96)
            restored = ReceiptState(path)
            self.assertEqual(restored.mirror_pending("-100999"), [])
            self.assertEqual(restored.data["mirrors"]["-100999"]["44"], 96)

    def test_native_forward_preserves_origin_channel(self):
        user = NS(forward_messages=AsyncMock(return_value=NS(id=205)))
        public_peer = NS(id=111)
        mirror_peer = NS(id=222)
        forwarded = asyncio.run(forward_public_poster(user, public_peer, mirror_peer, 45))
        self.assertEqual(forwarded, 205)
        args, kwargs = user.forward_messages.await_args
        self.assertIs(args[0], mirror_peer)
        self.assertEqual(args[1], 45)
        self.assertIs(kwargs["from_peer"], public_peer)

    def test_pending_mirror_recovery_does_not_duplicate_forward(self):
        with TemporaryDirectory() as folder:
            state = ReceiptState(str(Path(folder)/"state.json"))
            state.complete("some:film", 70, 41)
            client = NS()
            with patch("film_relay.desir_runner.existing_native_forwards",
                       new=AsyncMock(return_value={41: 99})), patch(
                       "film_relay.desir_runner.forward_public_poster", new=AsyncMock()
                       ) as forward:
                # utils.get_peer_id uses Telethon's peer types.
                from telethon.tl.types import PeerChannel
                public_peer = PeerChannel(12)
                done = asyncio.run(finish_mirrors(
                    client, state, NS(), "-100888", public_peer))
                self.assertEqual(done, 0)
                forward.assert_not_awaited()
                self.assertTrue(state.mirror_recorded("-100888", 41))

    def test_merge_mirror_checkpoints(self):
        from scripts.merge_desir_state import merge
        result = merge(
            {"completed": {}, "staged": {}, "mirrors": {"-1001": {"11": 99}}},
            {"completed": {}, "staged": {}, "mirrors": {"-1001": {"12": 100}}},
        )
        self.assertEqual(result["mirrors"]["-1001"], {"11": 99, "12": 100})

    def test_two_desir_films_trigger_one_ad_rotation(self):
        from film_relay.promotions import due, _cursor
        with TemporaryDirectory() as folder:
            state = ReceiptState(str(Path(folder)/"desir.json"))
            bridge = DesirPromotionsState(state)
            target = "-100publicdesir"
            # One movie is not enough to advertise.
            state.complete("film1", 1, 21)
            self.assertIsNone(due(bridge, target, len(bridge.data["processed"])))
            state.complete("film2", 2, 22)
            self.assertEqual(due(bridge, target, len(bridge.data["processed"])), 0)
            cursor = _cursor(bridge, target)
            cursor["last_film_total"] = 2
            cursor["next_index"] += 1
            bridge.save()
            self.assertIsNone(due(bridge, target, len(bridge.data["processed"])))
            # Subsequent pairs trigger exactly one new campaign.
            state.complete("film3", 3, 23)
            state.complete("film4", 4, 24)
            self.assertEqual(due(bridge, target, len(bridge.data["processed"])), 1)
            self.assertEqual(ReceiptState(str(Path(folder)/"desir.json")).data[
                "promotions"][target]["next_index"], 1)

    def test_private_and_torrent_mirror_have_independent_promo_counters(self):
        from film_relay.promotions import due
        with TemporaryDirectory() as folder:
            state = ReceiptState(str(Path(folder)/"desir.json"))
            state.complete("film1", 1, 21)
            state.complete("film2", 2, 22)
            state.mirror_done("-100mirror", 21, 101)
            bridge = DesirPromotionsState(state)
            self.assertEqual(due(bridge, "-100public", 2), 0)
            self.assertEqual(due(bridge, "-100private", 2), 0)
            self.assertIsNone(due(bridge, "-100mirror", 1))
            state.mirror_done("-100mirror", 22, 102)
            self.assertEqual(due(bridge, "-100mirror", 2), 0)

    def test_receipt_checkpoint(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder)/"desir.json")
            state = ReceiptState(path)
            state.stage("1:2", "poster", 50)
            state.stage("1:2", "video", 51)
            self.assertEqual(ReceiptState(path).data["staged"]["1:2"]["video"], 51)
            state.complete("1:2", 51, 19)
            again=ReceiptState(path)
            self.assertNotIn("1:2",again.data["staged"])
            self.assertIn("1:2",again.data["completed"])

if __name__ == "__main__":
    unittest.main()
