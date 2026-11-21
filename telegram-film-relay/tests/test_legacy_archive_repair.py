"""Regression tests for the safe CineX legacy recognition and linking."""
import unittest
from types import SimpleNamespace as NS

from film_relay.legacy_media_identity import (
    parse_identity, video_identity, poster_identity, compatible,
    find_legacy_poster, youtube_url_for,
)
from film_relay.legacy_archive_repair import (
    cover_caption, find_verified_public_link, find_verified_private_pair,
)


def media(mid, title, *, photo=False, video=False, name="", doc=None, buttons=None):
    return NS(
        id=mid, raw_text=title,
        photo=(object() if photo else None),
        video=(object() if video else None),
        document=NS(id=doc or 10000 + mid, attributes=[]) if video else None,
        file=NS(name=name), buttons=buttons or [], noforwards=False,
    )


class LegacyMediaIdentityTests(unittest.TestCase):
    def test_movies_with_number_are_sequels_not_parts(self):
        a = parse_identity("Taxi 2 VF", "films")
        b = parse_identity("Taxi 3 VF", "films")
        self.assertEqual(a.kind, "film")
        self.assertEqual(a.title, "taxi 2")
        self.assertEqual(compatible(a, b), 0)

    def test_parts_one_two_three_are_distinct(self):
        parts = [parse_identity(f"Le Grand Film Partie {i} VF.mkv", "action")
                 for i in (1, 2, 3)]
        self.assertEqual([p.part for p in parts], [1, 2, 3])
        self.assertEqual({p.title for p in parts}, {"le grand"})
        self.assertEqual(compatible(parts[0], parts[1]), 0.0)
        self.assertEqual(compatible(parts[0], parse_identity(
            "Le Grand Film Partie 1", "action")), 1.0)
        self.assertEqual(compatible(parts[0], parse_identity(
            "Le Grand Film Partie 2", "action")), 0.0)

    def test_seasons_and_anime_episodes(self):
        episode = parse_identity("Naruto S02E011 VF.mkv", "anime")
        self.assertEqual((episode.kind, episode.season, episode.episode),
                         ("episode", 2, 11))
        other = parse_identity("Naruto Saison 2 Episode 12", "anime")
        self.assertEqual(compatible(episode, other), 0)
        pack = parse_identity("Naruto Saison 2 complète VF", "anime")
        self.assertEqual((pack.kind, pack.season), ("season_pack", 2))
        self.assertEqual(compatible(episode, pack), 1.0)

    def test_no_inferred_episode_from_numbered_movie(self):
        self.assertIsNone(parse_identity("John Wick 3", "films").episode)

    def test_remote_cover_and_legacy_movie_can_match(self):
        video = media(450, "Le Voyageur Partie 1 VF",
                      video=True, name="Le.Voyageur.Partie.1.mp4")
        poster = media(100, "🎬 Le Voyageur\nSynopsis : une histoire", photo=True)
        self.assertIs(find_legacy_poster(video, [poster], "films"), poster)

    def test_wrong_part_poster_never_matches(self):
        video = media(450, "Le Voyageur Partie 1", video=True)
        wrong = media(449, "Le Voyageur Partie 2", photo=True)
        self.assertIsNone(find_legacy_poster(video, [wrong], "films"))

    def test_conflicting_episode_numbers_cannot_be_mislabeled(self):
        video = media(10, "Naruto S01E02", video=True, name="Naruto.S01E03.mkv")
        self.assertFalse(video_identity(video, "anime").safe)

    def test_ambiguous_duplicate_legacy_covers_are_quarantined(self):
        video = media(300, "Le Voyageur", video=True)
        posters = [media(290, "Le Voyageur", photo=True),
                   media(291, "Le Voyageur", photo=True)]
        self.assertIsNone(find_legacy_poster(video, posters, "films"))

    def test_private_pair_requires_document_and_correct_part(self):
        source = media(100, "Le Voyageur Partie 2", video=True, doc=777)
        photo = media(201, "🎬 le voyageur — Partie 2", photo=True)
        private_video = media(202, "Le Voyageur Partie 2", video=True, doc=777)
        other = media(203, "Le Voyageur Partie 1", video=True, doc=778)
        pair = find_verified_private_pair([photo, private_video, other],
                                          source, "films")
        self.assertEqual(pair[0].id, 202)

    def test_video_caption_keeps_episode_and_part(self):
        poster = media(1, "🎬 Saga\nSynopsis : récit", photo=True)
        episode = media(2, "Saga S02E03", video=True)
        part = media(3, "Saga Partie 3", video=True)
        self.assertIn("S02E03", cover_caption(poster, episode, "anime"))
        self.assertIn("Partie 3", cover_caption(poster, part, "films"))

    def test_youtube_only_when_explicit_valid_link(self):
        blank = media(1, "Saga", photo=True)
        self.assertIsNone(youtube_url_for(blank))
        good = media(1, "Saga\nhttps://youtu.be/dQw4w9WgXcQ", photo=True)
        self.assertEqual(youtube_url_for(good),
                         "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        bad = media(1, "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
                    photo=True)
        self.assertIsNone(youtube_url_for(bad))

    def test_no_public_link_without_all_verified_buttons(self):
        source = media(41, "Saga Partie 2", video=True, doc=111)
        public = media(42, "Saga Partie 2", photo=True, buttons=[
            [NS(url="https://t.me/c/4392607284/30")],
        ])
        self.assertIsNone(find_verified_public_link(
            [public], source, "films", -1004392607284, 30,
            "https://t.me/+SomeValidInvite"))


if __name__ == "__main__":
    unittest.main()
