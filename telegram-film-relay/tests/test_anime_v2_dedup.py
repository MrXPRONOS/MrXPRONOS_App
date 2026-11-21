"""CinéX Anime V2: offline cross-source dedup and fair weekly-episode selection."""
from __future__ import annotations

import unittest
from types import SimpleNamespace as NS

from film_relay.anime_dedup import (
    canonical_series_key, deduplicate_anime_candidates,
    pending_ongoing_episodes,
)


def row(series: str, number: int, source: str, doc_id: int, *, timestamp=1,
        poster=True, season=1):
    return {
        "series": series, "title": series.replace("-", " ").title(),
        "season": season, "episode": number, "source_key": source,
        "poster": NS(photo=True) if poster else None,
        "video": NS(document=NS(id=doc_id), media="source-file"),
        "timestamp": float(timestamp),
    }


def completed_entry(count: int):
    return {
        "title": "Naruto",
        "episodes": {"1": {
            str(n): {"message_id": n + 1000} for n in range(1, count+1)
        }},
        "public_episode_posts": {
            f"S01E{n:02d}": {"poster": n + 10, "video": n + 20}
            for n in range(1, count+1)
        },
    }


class AnimeCrossSourceDedupTests(unittest.TestCase):
    def test_same_episode_two_sources_is_one_episode(self):
        rows = [
            row("naruto", 7, "-1001:7", 401, timestamp=3),
            row("naruto", 7, "-1002:17", 401, timestamp=6),
        ]
        unique, report = deduplicate_anime_candidates(rows, {})
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]["source_key"], "-1002:17")
        self.assertEqual(unique[0]["alternative_source_keys"], ["-1001:7"])
        self.assertEqual(report["source_duplicates"], 1)
        self.assertEqual(report["media_variants"], 0)

    def test_different_document_for_same_episode_is_audited_not_published_twice(self):
        rows = [
            row("naruto", 7, "-1001:7", 401),
            row("naruto", 7, "-1002:17", 402),
        ]
        unique, report = deduplicate_anime_candidates(rows, {})
        self.assertEqual(len(unique), 1)
        self.assertEqual(report["media_variants"], 1)
        self.assertEqual(report["conflicts"][0]["reason"],
                         "different_telegram_media_for_same_episode")

    def test_separate_season_or_separate_anime_must_never_be_merged(self):
        rows = [
            row("naruto", 7, "a", 401),
            row("naruto", 7, "b", 402, season=2),
            row("bleach", 7, "c", 401),
        ]
        unique, report = deduplicate_anime_candidates(rows, {})
        self.assertEqual(len(unique), 3)
        self.assertEqual(report["source_duplicates"], 0)

    def test_prefer_existing_receipted_source_over_new_repost(self):
        data = {"series": {"naruto": {
            **completed_entry(6), "source_items": {"old:7": 1117}
        }}}
        a = row("naruto", 7, "old:7", 401, timestamp=1)
        b = row("naruto", 7, "new:7", 402, timestamp=9)
        unique, _ = deduplicate_anime_candidates([a, b], data)
        self.assertEqual(unique[0]["source_key"], "old:7")

    def test_persisted_alias_resolves_to_existing_card(self):
        data = {"series": {"naruto": completed_entry(6)},
                "series_aliases": {"mangas-vf-naruto": "naruto"}}
        source = row("mangas-vf-naruto", 7, "a", 401)
        self.assertEqual(canonical_series_key(data, source), "naruto")

    def test_four_distinct_series_max_one_episode_each(self):
        groups = {}
        for n in range(6):
            key = f"anime-serie-{n}"
            groups[key] = [row(key, 1, f"{n}:1", 50+n,
                               timestamp=n)]
        picked = pending_ongoing_episodes(groups, {}, maximum=4)
        self.assertEqual(len(picked), 4)
        self.assertEqual(len({key for key, _ in picked}), 4)
        self.assertEqual([v[0]["episode"] for _, v in picked], [1, 1, 1, 1])

    def test_existing_series_only_picks_new_episode(self):
        stored = {"series": {"naruto": completed_entry(6)}}
        groups = {"naruto": [
            row("naruto", n, f"source:{n}", 300+n, timestamp=n)
            for n in range(1, 9)
        ]}
        picked = pending_ongoing_episodes(groups, stored)
        self.assertEqual([(k, rows[0]["episode"]) for k, rows in picked],
                         [("naruto", 7)])

    def test_episode_8_is_held_back_when_7_missing(self):
        stored = {"series": {"naruto": completed_entry(6)}}
        groups = {"naruto": [row("naruto", 8, "source:8", 308)]}
        self.assertEqual(pending_ongoing_episodes(groups, stored), [])

    def test_active_full_season_batch_blocks_weekly_mode(self):
        data = {"active_batch": {"key": "naruto", "episodes": []}}
        self.assertEqual(pending_ongoing_episodes({
            "bleach": [row("bleach", 1, "source:1", 101)]
        }, data), [])


if __name__ == "__main__":
    unittest.main()
