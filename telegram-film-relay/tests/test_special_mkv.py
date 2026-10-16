"""Special MKV source pairing: photo-caption-MKV or photo-text-MKV."""
import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS

from film_relay.matching import (
    description_of, is_film_description, match_authorized_mkv_pairs,
)

T = datetime(2026, 10, 16, tzinfo=timezone.utc)


def photo(n, caption="", restricted=False):
    return NS(id=n, photo=object(), document=None, video=None,
              raw_text=caption, entities=None, noforwards=restricted, date=T)


def mkv(n, name="Le.Film.mkv", restricted=False):
    doc=NS(id=n+1000, mime_type="application/octet-stream", size=0,
           attributes=[NS(file_name=name)])
    return NS(id=n, photo=None, document=doc, video=None,
              file=NS(name=None, duration=0, size=0),
              raw_text="", entities=None, noforwards=restricted,
              date=T+timedelta(days=2))


def text(n, value):
    return NS(id=n, photo=None, document=None, video=None, raw_text=value,
              entities=None, noforwards=False, date=T)


class AuthorizedMkvTests(unittest.TestCase):
    def test_photo_caption_and_immediate_mkv(self):
        result=match_authorized_mkv_pairs([mkv(12), photo(11, "Titre original : Super Film\nGenre: Action")])
        self.assertEqual(len(result), 1)
        self.assertEqual(description_of(result[0]), "Titre original : Super Film\nGenre: Action")

    def test_photo_separate_text_mkv(self):
        result=match_authorized_mkv_pairs([mkv(32), text(31, "Durée : 2h\nGenre : aventure"),
                                            photo(30)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].poster.id, 30)
        self.assertEqual(description_of(result[0]), "Durée : 2h\nGenre : aventure")

    def test_no_duration_or_size_needed(self):
        result=match_authorized_mkv_pairs([photo(4, "Film : mon oeuvre"), mkv(5)])
        self.assertEqual(len(result), 1)

    def test_no_pair_when_other_photo_interrupts(self):
        result=match_authorized_mkv_pairs([photo(5, "Film : un film"),
                                           photo(6, "Film : second film"), mkv(7)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].poster.id, 6)

    def test_reject_non_mkv_and_unrelated_text(self):
        self.assertEqual(match_authorized_mkv_pairs([photo(1,"Genre: Fiction"),
                                                      mkv(2,name="document.zip")]), [])
        self.assertEqual(match_authorized_mkv_pairs([photo(1),
                                                      text(2,"Rejoins le canal https://t.me/join"),
                                                      mkv(3)]), [])

    def test_protected_media_rejected(self):
        self.assertEqual(match_authorized_mkv_pairs([photo(1,"Film : un film"),
                                                      mkv(2,restricted=True)]), [])
        self.assertEqual(match_authorized_mkv_pairs([photo(1,"Film : un film",restricted=True),
                                                      mkv(2)]), [])

    def test_film_metadata(self):
        self.assertTrue(is_film_description("🎬 Titre original : La Vie"))
        self.assertTrue(is_film_description("Genre : Comédie"))
        self.assertTrue(is_film_description("Synopsis : aventure extraordinaire"))
        self.assertFalse(is_film_description("https://t.me/film"))

if __name__ == "__main__":
    unittest.main()
