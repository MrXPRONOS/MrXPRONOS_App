import unittest
from types import SimpleNamespace
from film_relay.public_video_showcase import select_recent_completed
from film_relay.public_video_archive import (
    is_video_message, last_ten_video_ids, matching_poster,
    normalize_title, title_similarity, archive_buttons, verified_film_video_pairs,
    is_user_reserved_film, poster_heading,
)


def msg(identifier, *, title="", photo=False, video=False, document_id=None, name=""):
    document = SimpleNamespace(id=document_id or identifier, attributes=[]) if video else None
    return SimpleNamespace(
        id=identifier, raw_text=title, photo=(object() if photo else None),
        video=(object() if video else None), document=document,
        file=SimpleNamespace(name=name), buttons=None,
    )


class PublicArchiveTests(unittest.TestCase):
    def test_video_and_nonvideo(self):
        self.assertTrue(is_video_message(msg(1, title="Film", video=True)))
        self.assertFalse(is_video_message(msg(2, title="Affiche", photo=True)))

    def test_only_latest_ten_kept(self):
        messages = [msg(i, video=True) for i in range(1, 15)]
        messages += [msg(200, photo=True)]
        self.assertEqual(last_ten_video_ids(messages), set(range(5, 15)))

    def test_movie_matching_is_not_adjacent_guess(self):
        film = msg(32, title="🎞️ Le Voyage de Jade", video=True)
        poster = msg(31, title="🎬 Le Voyage de Jade\nAnnée : 2026", photo=True)
        other = msg(30, title="🎬 Film totalement différent", photo=True)
        self.assertIs(matching_poster(film, [other, poster, film]), poster)

    def test_skip_when_title_missing(self):
        film = msg(50, video=True)
        poster = msg(49, title="La fille du roi", photo=True)
        self.assertIsNone(matching_poster(film, [poster, film]))

    def test_long_gap_requires_strong_title_and_finds_legacy_poster(self):
        film = msg(380, title="🎞️ La fille du roi", video=True)
        poster = msg(30, title="🎬 La fille du roi", photo=True)
        unrelated = msg(379, title="🎬 Une autre fille du roi", photo=True)
        self.assertIs(matching_poster(film, [poster, unrelated, film]), poster)

    def test_reject_ambiguous_far_posters(self):
        film = msg(380, title="🎞️ La fille du roi", video=True)
        poster1 = msg(30, title="🎬 La fille du roi", photo=True)
        poster2 = msg(31, title="🎬 La fille du roi", photo=True)
        self.assertIsNone(matching_poster(film, [poster1, poster2, film]))

    def test_john_wick_is_reserved_for_manual_processing(self):
        video = msg(101, title="John Wick 4.mp4", video=True)
        poster = msg(100, title="🎬 JOHN WICK 4", photo=True)
        self.assertTrue(is_user_reserved_film(video, poster))
        self.assertFalse(is_user_reserved_film(
            msg(103, title="The Criminal", video=True),
            msg(102, title="The Criminal", photo=True)))

    def test_normalize(self):
        self.assertEqual(normalize_title("🎬 FILM : Le Grand Voyage (VF)"), "le grand voyage")
        self.assertGreater(title_similarity("Le Grand Voyage", "Le Grand Voyage VF 2026"), 0.8)

    def test_showcase_only_recent_published_posters(self):
        records = {
            "a": {"private_message_id": 100, "public_message_id": 101},
            "b": {"private_message_id": 200, "public_message_id": 201},
            "old": {"private_message_id": 300, "public_message_id": 1},
        }
        selected = select_recent_completed(records, {101, 201, 202}, count=2)
        self.assertEqual([r["public_message_id"] for r in selected], [201, 101])

    def test_only_ten_verified_films_count_not_unrelated_videos(self):
        messages = []
        for i in range(11):
            messages.extend([
                msg(100 + 2 * i, title=f"🎬 Film voyage {i}", photo=True),
                msg(101 + 2 * i, title=f"🎞️ Film voyage {i}", video=True),
            ])
        # Ten noisy standalone videos and unrelated promo posts must not
        # consume any of the ten protected FILM slots.
        messages.extend(msg(300 + i, title=f"Clip promo {i}", video=True) for i in range(10))
        messages.append(msg(500, title="Publicité", photo=True))
        pairs = verified_film_video_pairs(messages)
        self.assertEqual(len(pairs), 11)
        self.assertEqual([video.id for video, _ in pairs[:10]],
                         [121 - 2 * i for i in range(10)])
        self.assertEqual(pairs[10][0].id, 101)

    def test_orphan_video_never_becomes_archive_candidate(self):
        messages = [msg(40, title="Video unique", video=True),
                    msg(39, title="Autre film", photo=True)]
        self.assertEqual(verified_film_video_pairs(messages), [])

    def test_legacy_hash_film_heading_matches_mutiny(self):
        video = msg(185, title="Mutiny Ultra HD (2026) VF", video=True)
        poster = msg(184, title="#Film\\n\\n🎬 MUTINY (2026)\\nSynopsis : aventure", photo=True)
        self.assertEqual(poster_heading(poster), "MUTINY (2026)")
        self.assertIs(matching_poster(video, [poster, video]), poster)

    def test_duplicate_beekeeper_uses_nearest_exact_poster(self):
        video = msg(175, title="🎞️ The Beekeeper", video=True)
        older = msg(168, title="🎬 The Beekeeper", photo=True)
        latest = msg(174, title="🎬 The Beekeeper", photo=True)
        self.assertIs(matching_poster(video, [older, latest, video]), latest)

    def test_short_hope_and_hash_film_mongoose(self):
        hope = msg(276, title="Hope VF 2026.mp4", video=True)
        hope_poster = msg(275, title="Hope\\n2026 ‧ Thriller/SF", photo=True)
        self.assertIs(matching_poster(hope, [hope_poster, hope]), hope_poster)
        mongoose = msg(293, title="The Mongoose (2026) VF", video=True)
        mongoose_poster = msg(292, title="#Film\\n🎬 THE MONGOOSE (2026)", photo=True)
        self.assertIs(matching_poster(mongoose, [mongoose_poster, mongoose]), mongoose_poster)

    def test_ignore_series_episode_in_movie_count(self):
        poster = msg(216, title="🎬 12 12 12 Saison 1 VF", photo=True)
        video = msg(217, title="12 12 12 [S01 EP 01] [VF]", video=True)
        self.assertEqual(verified_film_video_pairs([poster, video]), [])

    def test_two_buttons(self):
        buttons = archive_buttons("https://t.me/c/1234/5678")
        self.assertEqual(buttons[0][0].url, "https://t.me/c/1234/5678")
        self.assertEqual(len(buttons), 2)


if __name__ == "__main__":
    unittest.main()
