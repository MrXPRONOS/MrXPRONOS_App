"""Offline tests for conservative poster/video matching decisions."""
import unittest
from types import SimpleNamespace as NS
from film_relay.title_guard import title_assessment


def poster(title="",id=1,grouped_id=None):
    return NS(id=id,raw_text=title,grouped_id=grouped_id)


def movie(name,caption="",reply_id=None,grouped_id=None):
    reply=NS(reply_to_msg_id=reply_id) if reply_id else None
    return NS(id=2,raw_text=caption,file=NS(name=name),reply_to=reply,
              grouped_id=grouped_id)


class TitleGuardTests(unittest.TestCase):
    def test_same_movie_title(self):
        self.assertEqual(title_assessment(poster("🎬 La Grande Aventure"),
                                          movie("La.Grande.Aventure.2024.mkv")),"verified")

    def test_different_named_film_is_blocked(self):
        self.assertEqual(title_assessment(poster("🎬 Le Secret du Chateau"),
                                          movie("Voyage_sur_Mars_2024.mkv")),"mismatch")

    def test_generic_filename_is_uncertain(self):
        self.assertEqual(title_assessment(poster("🎬 Le Secret du Chateau"),
                                          movie("film.mp4")),"uncertain")

    def test_caption_confirms_when_filename_generic(self):
        self.assertEqual(title_assessment(poster("🎬 Un Voyage sur Mars"),
                                          movie("video.mp4","Un Voyage sur Mars")),"verified")

    def test_reply_provides_explicit_evidence(self):
        self.assertEqual(title_assessment(poster(""),movie("episode.mp4",reply_id=1)),"verified")

    def test_ambiguous_reply_with_conflicting_titles_requires_review(self):
        self.assertEqual(title_assessment(poster("🎬 Film Soleil"),
                                          movie("film_lune.mkv",reply_id=1)),"uncertain")

    def test_album_provides_explicit_evidence(self):
        self.assertEqual(title_assessment(poster("",grouped_id=567),
                                          movie("film.mp4",grouped_id=567)),"verified")

    def test_matching_caption_cannot_override_wrong_filename(self):
        self.assertEqual(title_assessment(poster("La Grande Aventure"),
                                         movie("Voyage.Sur.Mars.mkv", "La Grande Aventure")),
                         "mismatch")

    def test_one_shared_word_is_not_sufficient(self):
        self.assertEqual(title_assessment(poster("Le Secret du Chateau"),
                                         movie("Le Secret de la Foret.mkv")),
                         "mismatch")

    def test_sequel_numbers_must_not_be_confused(self):
        self.assertEqual(title_assessment(poster("Aventure Galactique 2"),
                                         movie("Aventure.Galactique.3.mkv")), "mismatch")

    def test_same_sequel_number_matches(self):
        self.assertEqual(title_assessment(poster("Aventure Galactique 2"),
                                         movie("Aventure.Galactique.2.2024.mkv")), "verified")

    def test_unmatched_media_cannot_be_published(self):
        self.assertEqual(title_assessment(None,movie("film.mp4")),"uncertain")


if __name__=="__main__":
    unittest.main()
