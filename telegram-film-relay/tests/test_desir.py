"""Offline validation for independent CinéX Désir relay. No Telegram messages sent."""
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS

from film_relay.desir_matching import is_supported_video, pair_items, film_title, item_key
from film_relay.desir_runner import ReceiptState, verify_destination


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
        self.assertIn("Autre Film", film_title(result[0]))

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
