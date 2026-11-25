import unittest
from types import SimpleNamespace as NS
from film_relay.private_stock_audit import (
    filename_descriptive, description_descriptive, audit_messages
)

def photo(mid, desc):
    return NS(id=mid, photo=object(), raw_text=desc, document=None,
              video=None, file=NS(name=""))

def video(mid, filename, caption="Film"):
    return NS(id=mid, photo=None, raw_text=caption, file=NS(name=filename),
              document=NS(id=mid + 900, attributes=[]), video=object())

class PrivateStockAuditTests(unittest.TestCase):
    def test_descriptive_filenames(self):
        self.assertTrue(filename_descriptive("Le Voyage 2026 - Partie 1.mkv"))
        self.assertTrue(filename_descriptive("Mon Anime S01E03.mp4"))
        self.assertFalse(filename_descriptive("video_12345.mp4"))
        self.assertFalse(filename_descriptive("1739242093345678.mp4"))
        self.assertFalse(filename_descriptive("movie.mp4"))
        self.assertFalse(filename_descriptive(""))
        self.assertFalse(filename_descriptive("Affiche.jpeg"))

    def test_descriptive_cover(self):
        self.assertTrue(description_descriptive(photo(
            1, "🎬 Voyage fantastique\nGenre : Aventure\nUn voyage mystérieux "
               "entre les deux continents, avec des aventures surprenantes.")))
        self.assertFalse(description_descriptive(photo(1, "🎬 Voyage S01E03")))

    def test_read_only_complete_poster_video(self):
        rows = [photo(2, "🎬 Une histoire en trois parties\n"
                        "Un synopsis complet et détaillé pour mieux décrire le film."),
                video(3, "Une histoire - Partie 1.mkv", "Partie 1")]
        result = audit_messages(rows, stock="films", limit=100)
        self.assertEqual(result["videos"], 1)
        self.assertEqual(result["prior_photo_3"], 1)
        self.assertEqual(result["photo_description_3"], 1)
        self.assertEqual(result["file_named"], 1)
        self.assertTrue(result["all_verified"])

    def test_missing_cover_and_generic_file_are_reported(self):
        rows = [video(1, "video.mp4", "")]
        result = audit_messages(rows, stock="central", limit=100)
        self.assertEqual(result["video_without_photo_80"], 1)
        self.assertEqual(result["filename_missing_or_generic"], 1)
        self.assertFalse(result["all_verified"])

    def test_batch_one_poster_before_multiple_episodes(self):
        rows = [photo(5, "🌸 Série Saison 1\nHistoire complète des épisodes "
                         "du héros dans un monde fantastique."),
                video(6, "Serie S01E01.mkv"), video(7, "Serie S01E02.mkv")]
        result = audit_messages(rows, stock="series", limit=100)
        self.assertEqual(result["prior_photo_3"], 2)
        self.assertEqual(result["photo_description_80"], 2)

    def test_scan_limit_indicates_incomplete_evidence(self):
        rows = [photo(1, "Un synopsis exceptionnel pour un film incroyable "
                         "avec plusieurs aventures inoubliables."),
                video(2, "Un film incroyable.mp4")]
        result = audit_messages(rows, stock="films", limit=2)
        self.assertTrue(result["scan_limit_reached"])
        self.assertFalse(result["all_verified"])

if __name__ == "__main__":
    unittest.main()
