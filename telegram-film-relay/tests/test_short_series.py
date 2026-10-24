"""Offline checks for whole-series eligibility; prevents partial or long uploads."""
import unittest
from types import SimpleNamespace as NS
from film_relay.short_series import short_complete_groups, normalized_key


def episodes(title, count, poster_caption=None, season=1):
    poster = NS(raw_text=poster_caption or title, photo=True)
    return [
        {"series": normalized_key(title), "title": title,
         "season": season, "episode": no, "source_key": f"src:{no}",
         "poster": poster, "video": NS(raw_text=f"Episode {no}"),
         "timestamp": float(no)}
        for no in range(1, count + 1)
    ]


class ShortSeriesTests(unittest.TestCase):
    def test_one_twelve_episode_anime_sends_whole_batch(self):
        rows = episodes("Death Parade", 12)
        result = short_complete_groups({"death-parade": rows}, {"series": {}}, 12)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0][1]), 12)

    def test_long_series_always_rejected(self):
        rows = episodes("Yu-Gi-Oh Duel Monsters", 12)
        catalog = {"source_observed": {
            "yu-gi-oh-duel-monsters": {"1": {str(n): [] for n in range(1, 25)}}
        }}
        self.assertEqual(short_complete_groups({"yu-gi-oh-duel-monsters": rows}, catalog), [])

    def test_twelve_plus_one_rejected_without_slice(self):
        rows = episodes("Long", 13)
        self.assertEqual(short_complete_groups({"long": rows}, {}), [])

    def test_eight_complete_tv_episodes_in_one_batch(self):
        rows = episodes("Mini TV", 8, poster_caption="Mini TV Série complète, 8 épisodes")
        picked = short_complete_groups({"mini-tv": rows}, {})
        self.assertEqual(len(picked[0][1]), 8)

    def test_incomplete_short_title_held_back(self):
        rows = episodes("Pending", 6)
        self.assertEqual(short_complete_groups({"pending": rows}, {}), [])

    def test_missing_episodes_not_guessed(self):
        rows = episodes("Mini", 12, poster_caption="Mini Série complète")
        rows.pop(6)
        self.assertEqual(short_complete_groups({"mini": rows}, {}), [])

    def test_available_window_must_cover_total(self):
        rows = episodes("Mini", 5, poster_caption="Mini Série complète, 8 épisodes")
        observed = {"source_observed": {
            "mini": {"1": {str(n): [] for n in range(1, 9)}}
        }}
        self.assertEqual(short_complete_groups({"mini": rows}, observed), [])

    def test_legacy_episode_alias_is_same_series(self):
        self.assertEqual(normalized_key("@Mangas fv Death Parade EP05"),
                         normalized_key("Death Parade"))


if __name__ == "__main__":
    unittest.main()
