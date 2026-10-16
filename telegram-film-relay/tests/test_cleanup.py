"""Read-only unit tests for conservative duplicate cleanup planning."""
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace as NS

from film_relay.state import State
from scripts.cleanup_cinex_duplicates import choose_plan


def photo(n, p=123):
    return NS(id=n, photo=NS(id=p), raw_text="Titre original : Un film incroyable",
              document=None, reply_markup=None)


def movie(n, doc):
    return NS(id=n, document=NS(id=doc), photo=None, raw_text="", reply_markup=None)


def public(n, private):
    return NS(id=n, raw_text="Film", document=None,
              reply_markup=NS(rows=[NS(buttons=[
                  NS(url=f"https://t.me/c/4392607284/{private}")
              ])]), buttons=None)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.state = State(str(Path(self.tmp.name) / "state.json"))
        self.pair = "-100source:27:28"
        self.state.add(self.pair, "doc:456", 15, 11)
        self.priv = [movie(5, 999),
                     photo(6), movie(7, 456),
                     photo(8), movie(9, 456),
                     photo(10), movie(11, 456),
                     photo(12), movie(13, 456),
                     photo(14), movie(15, 456)]
        self.pub = [public(8, 7), public(9, 9), public(10, 13),
                    public(11, 15), public(50, 5)]

    def tearDown(self):
        self.tmp.cleanup()

    def test_cleanup_preserves_canonical_and_unrelated_posts(self):
        plan = choose_plan(self.state, self.priv, self.pub, -1004392607284)
        self.assertEqual(plan.old_private_videos, (7, 9, 11, 13))
        self.assertEqual(plan.old_private_photos, (6, 8, 10, 12))
        self.assertEqual(plan.old_public_posts, (8, 9, 10))
        self.assertNotIn(15, plan.old_private_videos)
        self.assertNotIn(11, plan.old_public_posts)

    def test_missing_canonical_link_aborts(self):
        pub = [public(11, 400)] + [x for x in self.pub if x.id != 11]
        with self.assertRaises(RuntimeError):
            choose_plan(self.state, self.priv, pub, -1004392607284)

    def test_unique_movie_does_not_get_deleted(self):
        p = [photo(14), movie(15, 456)]
        self.assertIsNone(choose_plan(self.state, p, [public(11, 15)], -1004392607284))


if __name__ == "__main__":
    unittest.main()
