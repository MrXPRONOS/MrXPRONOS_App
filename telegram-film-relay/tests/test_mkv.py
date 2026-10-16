"""Regressions: MKV sent by Telegram as a generic document without duration."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
import unittest

from film_relay.matching import filename_of, is_video
from film_relay.verification import screen_pairs

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


def poster(message_id=10):
    return NS(id=message_id, photo=object(), document=None, video=None,
              raw_text="Film extraordinaire en francais", entities=None,
              date=NOW, grouped_id=None, reply_to=None, noforwards=False)


def mkv(message_id=13, *, size=300_000_000, duration=None, name=None, mime="application/octet-stream"):
    doc = NS(id=772, mime_type=mime, size=size,
             attributes=[NS(file_name="Grand.Film.2025.MKV")])
    return NS(id=message_id, photo=None, document=doc, video=None, raw_text="",
              file=NS(name=name, duration=duration, size=size),
              date=NOW + timedelta(minutes=30), grouped_id=None,
              reply_to=None, noforwards=False)


class MKVTests(unittest.TestCase):
    def test_recognize_mkv_attribute_when_generic_document(self):
        msg = mkv()
        self.assertEqual(filename_of(msg), "grand.film.2025.mkv")
        self.assertTrue(is_video(msg))

    def test_accept_substantial_mkv_without_duration(self):
        checked = screen_pairs([mkv(), poster()], min_minutes=40,
                               min_megabytes=75, max_gap=5,
                               max_age_minutes=180, min_caption_chars=12)
        self.assertEqual(len(checked.pairs), 1)
        self.assertEqual(checked.rejected, 0)

    def test_reject_small_mkv_even_without_duration(self):
        checked = screen_pairs([poster(), mkv(size=15_000_000)],
                               min_megabytes=75, max_gap=5,
                               max_age_minutes=180, min_caption_chars=12)
        self.assertEqual(len(checked.pairs), 0)

    def test_zero_duration_treated_as_missing_metadata(self):
        msg = mkv(duration=0)
        self.assertTrue(is_video(msg))
        checked = screen_pairs([poster(), msg], min_minutes=40,
                               min_megabytes=75, max_gap=5,
                               max_age_minutes=180, min_caption_chars=12)
        self.assertEqual(len(checked.pairs), 1)

    def test_reject_short_file_with_duration(self):
        checked = screen_pairs([poster(), mkv(duration=120)],
                               min_megabytes=75, max_gap=5,
                               max_age_minutes=180, min_caption_chars=12)
        self.assertEqual(len(checked.pairs), 0)

    def test_unknown_extension_is_not_accepted(self):
        doc = mkv(mime="application/octet-stream")
        doc.document.attributes = [NS(file_name="mystery.bin")]
        self.assertFalse(is_video(doc))


if __name__ == "__main__":
    unittest.main()
