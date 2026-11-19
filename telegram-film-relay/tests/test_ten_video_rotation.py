"""Offline tests for the simple multi-channel ten-video rotation."""
import unittest
from types import SimpleNamespace as NS
from film_relay.ten_video_rotation import (
    split_recent_and_old, category_targets, movie_button_target,
    is_rotatable_video,
)


def movie(i, title="🎞️ Film", filename="film.mp4"):
    return NS(id=i, raw_text=title, document=NS(id=3000 + i, attributes=[]),
              video=object(), file=NS(name=filename), photo=None)


class TenVideoRotationTests(unittest.TestCase):
    def test_keep_ten_recent_films_and_identify_oldest_first(self):
        records = [movie(i) for i in range(1, 15)]
        records += [movie(80, "animation gif", "animation.gif.mp4"),
                    movie(81, "Pronostics Mr XPRONOS", "daily_pronos_coupon_short.mp4"),
                    movie(82, "John Wick 4")]
        protected, old = split_recent_and_old(records, "films")
        self.assertEqual([m.id for m in protected], list(range(14, 4, -1)))
        self.assertEqual([m.id for m in reversed(old)], [1, 2, 3, 4])

    def test_series_and_anime_keep_episodes(self):
        records = [movie(i, "S01 EP %02d" % i) for i in range(1, 13)]
        kept, old = split_recent_and_old(records, "series")
        self.assertEqual(len(kept), 10)
        self.assertEqual(len(old), 2)
        self.assertTrue(is_rotatable_video(records[0], "anime"))
        self.assertFalse(is_rotatable_video(movie(40, "animation gif"), "series"))

    def test_movie_private_url_matches_configured_library_only(self):
        poster = NS(buttons=[[NS(url="https://t.me/c/4392607284/267")],
                             [NS(url="https://t.me/addlist/example")]])
        self.assertEqual(movie_button_target(poster, -1004392607284), 267)
        self.assertIsNone(movie_button_target(poster, -1007777777777))
        poster.buttons.append([NS(url="https://t.me/c/4392607284/123")])
        self.assertIsNone(movie_button_target(poster, -1004392607284))

    def test_unconfigured_categories_are_skipped_without_invented_channel(self):
        targets = category_targets({
            "TG_PRIVATE_CHANNEL": "-1004392607284",
            "SERIES_PUBLIC_CHANNEL": "@seriesvf_cinex",
            "ANIME_PUBLIC_CHANNEL": "@CineXAnimeFR",
        })
        self.assertEqual(targets, [("films", "@CineXFilms_vf", -1004392607284)])

    def test_categories_require_ids_and_exact_usernames(self):
        with self.assertRaises(RuntimeError):
            category_targets({
                "TG_PRIVATE_CHANNEL": "my-private",
            })
        with self.assertRaises(RuntimeError):
            category_targets({
                "TG_PRIVATE_CHANNEL": "-1004392607284",
                "COMEDIE_PRIVATE_CHANNEL": "-1005432100000",
                "COMEDIE_PUBLIC_CHANNEL": "NoUsername",
            })


if __name__ == "__main__":
    unittest.main()
