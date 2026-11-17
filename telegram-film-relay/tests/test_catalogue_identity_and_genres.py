"""Regression tests for previously partial CineX catalogue and genre fixes."""
import unittest
from types import SimpleNamespace as NS

from film_relay.episode_identity import (
    canonical_title, consistent_title, episode_numbers, series_title)
from film_relay.genre_guard import category_allowed, explicit_genres
from film_relay.tv_policy import complete_tv_seasons
from film_relay.anime_policy import complete_anime_seasons
from film_relay.catalog_scan import episode_audit
from film_relay.title_guard import title_assessment


def episodes(key, count, season=1, label=None):
    caption = label if label is not None else f"Demo Saison complète {count} épisodes"
    return [
        {"series": key, "title": "Demo", "season": season, "episode": no,
         "source_key": f"source:{season}:{no}",
         "poster": NS(raw_text=caption, photo=object()),
         "video": NS(raw_text=f"Épisode {no}"),
         "timestamp": float(100 * season + no)}
        for no in range(1, count + 1)
    ]


class CatalogueIdentityTests(unittest.TestCase):
    def test_accented_episode_and_e_code(self):
        self.assertEqual(episode_numbers("Épisode 7"), (1, 7))
        self.assertEqual(episode_numbers("E05.mkv"), (1, 5))
        self.assertEqual(episode_numbers("S02E03.mkv"), (2, 3))
        self.assertIsNone(episode_numbers("Saison 2 seulement"))

    def test_source_signature_episode_number_and_resolution_do_not_split_series(self):
        self.assertEqual(series_title("@Mangas fv Death Parade EP05"), "Death Parade")
        self.assertEqual(canonical_title("mangas-fv-death-parade-ep05"), "death-parade")
        self.assertEqual(canonical_title("death-parade-480p"), "death-parade")
        self.assertEqual(canonical_title("animeisekaic-beast-tamer-fin"), "beast-tamer")
        self.assertEqual(canonical_title("no-longer-rangers-s02-mp4"), "no-longer-rangers")

    def test_generic_episode_uses_its_poster_title(self):
        self.assertEqual(consistent_title("Naruto S02", "", "Episode_01.mkv"), "Naruto")

    def test_named_video_cannot_inherit_unrelated_poster(self):
        self.assertEqual(consistent_title("Naruto", "Bleach S01E02",
                                          "Bleach.S01E02.mkv"), "")

    def test_video_caption_and_filename_must_not_conflict(self):
        self.assertEqual(consistent_title("Naruto", "Naruto S01E03",
                                          "Bleach.S01E03.mkv"), "")

    def test_multiple_complete_tv_seasons_not_blocked_by_total_show_length(self):
        groups = {"demo": episodes("demo", 6, season=1) +
                   episodes("demo", 7, season=2)}
        found = complete_tv_seasons(groups, {}, maximum=12)
        self.assertEqual(len(found), 2)
        self.assertEqual([len(rows) for _, rows in found], [6, 7])

    def test_incomplete_tv_season_never_promoted(self):
        rows = episodes("demo", 6)
        rows.pop(3)
        reasons = {}
        found = complete_tv_seasons({"demo": rows}, {}, diagnostics=reasons)
        self.assertEqual(found, [])
        self.assertEqual(reasons["demo:S01"], "numerotation_incomplete")

    def test_anime_26_episodes_stays_blocked(self):
        rows = episodes("anime", 26, label="Anime Saison complète 26 épisodes")
        reasons = {}
        self.assertEqual(complete_anime_seasons(
            {"anime": rows}, {}, maximum=25, diagnostics=reasons), [])
        self.assertEqual(reasons["anime:S01"], "hors_limite_episodes")

    def test_historical_aliases_are_not_counted_twice(self):
        data = {
            "series": {"death-parade": {
                "title": "Death Parade",
                "episodes": {"1": {"5": {"message_id": 123}}}}},
            "source_observed": {
                "mangas-fv-death-parade-ep05": {"1": {"5": ["source:5"]}},
                "death-parade-480p": {"1": {"5": ["source:6"]}},
            },
        }
        report = episode_audit(data, [], category="anime_catalog")
        self.assertEqual(report["source_title_variants"], 2)
        self.assertEqual(report["canonical_titles"], 1)
        self.assertEqual(report["source_episode_numbers_observed"], 1)
        self.assertEqual(report["not_yet_indexed_total"], 0)
        self.assertIn("mangas-fv-death-parade-ep05", data["source_observed"])


class CategoryGuardTests(unittest.TestCase):
    def test_explicit_romance_cannot_enter_comedy(self):
        p = NS(raw_text="🎬 Le Film\nGenre : Romance")
        v = NS(raw_text="")
        self.assertFalse(category_allowed("comedie", p, v))
        self.assertTrue(category_allowed("desir", p, v))

    def test_explicit_comedy_cannot_enter_romance(self):
        p = NS(raw_text="Un film\n#Comédie")
        self.assertTrue(category_allowed("comedie", p, None))
        self.assertFalse(category_allowed("desir", p, None))

    def test_mixed_genres_stay_in_review(self):
        self.assertEqual(explicit_genres("Genre: comédie romantique"),
                         {"comedie", "desir"})
        self.assertFalse(category_allowed("comedie",
                                         NS(raw_text="Genre: comédie romantique"), None))

    def test_no_genre_claim_does_not_invent_classification(self):
        self.assertTrue(category_allowed("comedie", NS(raw_text="Le Film"), None))

    def test_generic_upload_filename_does_not_override_real_matching_caption(self):
        p = NS(raw_text="🎬 Un Voyage sur Mars", id=1, grouped_id=None)
        v = NS(raw_text="Un Voyage sur Mars", reply_to=None,
               grouped_id=None, file=NS(name="video_20240101.mp4"))
        self.assertEqual(title_assessment(p, v), "verified")

    def test_generic_filename_without_caption_still_uncertain(self):
        p = NS(raw_text="🎬 Un Voyage sur Mars", id=1, grouped_id=None)
        v = NS(raw_text="", reply_to=None, grouped_id=None,
               file=NS(name="video_20240101.mp4"))
        self.assertEqual(title_assessment(p, v), "uncertain")


if __name__ == "__main__":
    unittest.main()
