"""Offline tests for the simple multi-channel ten-video rotation."""
import unittest
import asyncio
from unittest.mock import patch
from types import SimpleNamespace as NS
from film_relay.ten_video_rotation import (
    split_recent_and_old, category_targets, movie_button_target,
    is_rotatable_video, execute, original_poster_safe_for_deletion,
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

    def test_download_button_does_not_change_verified_private_video_target(self):
        # Additional external bot download links never replace the exact
        # private archive link required before rotation may delete public videos.
        poster = NS(buttons=[
            [NS(url="https://t.me/c/4455497484/42")],
            [NS(url="https://t.me/CineRadarFr_Bot?start=d_" + "A" * 24)],
            [NS(url="https://t.me/addlist/example")]
        ])
        self.assertEqual(movie_button_target(poster, -1004455497484), 42)
        self.assertIsNone(movie_button_target(poster, -1004462439590))

    def test_opaque_existing_button_preserves_video_without_crashing(self):
        cover = NS(id=100, photo=NS(id=808), pinned=True,
                   raw_text="Film Partie 1",
                   buttons=[[NS(text="Bouton historique", url=None)]])
        live = NS(id=100, photo=NS(id=808), pinned=True,
                  raw_text="Film Partie 1",
                  buttons=[[NS(text="Bouton historique", url=None)]])
        self.assertFalse(original_poster_safe_for_deletion(live, cover))

    def test_verified_cover_stays_edit_protected(self):
        cover = NS(id=101, photo=NS(id=809), pinned=True,
                   raw_text="Film Partie 2",
                   buttons=[[NS(text="🎬 VOIR", url="https://t.me/c/4392607284/55")]])
        live = NS(id=101, photo=NS(id=809), pinned=True,
                  raw_text="Film Partie 2",
                  buttons=[[NS(text="🎬 VOIR", url="https://t.me/c/4392607284/55")]])
        self.assertTrue(original_poster_safe_for_deletion(live, cover))
        live.pinned = False
        self.assertFalse(original_poster_safe_for_deletion(live, cover))
        live.pinned = True
        live.raw_text = "Film Partie 3"
        self.assertFalse(original_poster_safe_for_deletion(live, cover))
        live.raw_text = cover.raw_text
        live.buttons = [[NS(text="🎬 VOIR", url="https://t.me/c/4392607284/999")]]
        self.assertFalse(original_poster_safe_for_deletion(live, cover))


    def test_native_callback_button_unchanged_allows_verified_cleanup(self):
        from telethon import Button
        from film_relay.original_poster_edit import (
            read_only_keyboard_signature, public_keyboard_signature,
        )
        def make(data=b"film-421"):
            return NS(id=420, photo=NS(id=817), pinned=True,
                      raw_text="Film éligible",
                      buttons=[[NS(button=Button.inline(
                          "Ancien bouton", data=data).button)]])
        prior = make()
        current = make()
        with self.assertRaises(RuntimeError):
            public_keyboard_signature(prior)
        self.assertEqual(read_only_keyboard_signature(prior),
                         read_only_keyboard_signature(current))
        self.assertTrue(original_poster_safe_for_deletion(current, prior))
        current = make(b"another-film")
        self.assertFalse(original_poster_safe_for_deletion(current, prior))

    def test_native_legacy_url_and_callback_changed_blocks_cleanup(self):
        from telethon import Button
        def make(link, data):
            return NS(id=421, photo=NS(id=818), pinned=True,
                      raw_text="Film éligible",
                      buttons=[[NS(button=Button.url("VOIR FILM", link).button),
                          NS(button=Button.inline("Informations", data=data).button)]])
        saved = make("https://t.me/c/4392607284/314", b"verified")
        self.assertTrue(original_poster_safe_for_deletion(
            make("https://t.me/c/4392607284/314", b"verified"), saved))
        self.assertFalse(original_poster_safe_for_deletion(
            make("https://t.me/c/4392607284/999", b"verified"), saved))
        self.assertFalse(original_poster_safe_for_deletion(
            make("https://t.me/c/4392607284/314", b"tampered"), saved))

    def test_unknown_unserializable_opaque_button_remains_blocked(self):
        original = NS(id=99, photo=NS(id=17), pinned=False, raw_text="Film",
                      buttons=[[NS(text="opaque", url=None)]])
        current = NS(id=99, photo=NS(id=17), pinned=False, raw_text="Film",
                      buttons=[[NS(text="opaque", url=None)]])
        self.assertFalse(original_poster_safe_for_deletion(current, original))

    def test_public_unknown_purge_requires_real_manual_dispatch(self):
        with patch.dict("os.environ", {"CINEX_MANUAL_PURGE_REQUEST": ""}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "workflow manuel"):
                asyncio.run(execute(apply=True, purge_unmatched=True))

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
