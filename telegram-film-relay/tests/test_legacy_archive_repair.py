"""Regression tests for the safe CineX legacy recognition and linking."""
import unittest
import asyncio
from unittest.mock import patch
from types import SimpleNamespace as NS

from film_relay.legacy_media_identity import (
    parse_identity, video_identity, poster_identity, compatible,
    find_legacy_poster, youtube_url_for,
)
from film_relay.ten_video_rotation import verify_existing_pair, unmatched_candidate, split_recent_and_old
from film_relay.legacy_neighbor_matching import find_neighbor_pair, identity_for_pair
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

    def test_repaired_public_poster_after_video_is_validated_by_exact_private_copy(self):
        rescue = "https://t.me/+ABCdefghi123456"
        folder = "https://t.me/addlist/AAA"
        url = "https://t.me/c/4392607284/55"
        public_video = media(12, "Saga Partie 2", video=True, doc=777)
        public_poster = media(900, "🎬 Saga Partie 2", photo=True, buttons=[
            [NS(url=url)], [NS(url=rescue)], [NS(url=folder)]
        ])
        private_video = media(55, "Saga Partie 2", video=True, doc=777)
        private_poster = media(54, "🎬 Saga Partie 2", photo=True, buttons=[
            [NS(url=rescue)], [NS(url=folder)]
        ])

        class FakeClient:
            async def get_messages(self, channel, ids):
                return [private_poster] if isinstance(ids, list) else private_video

        with (patch("film_relay.ten_video_rotation.rescue_link_for", return_value=rescue),
              patch("film_relay.ten_video_rotation.film_folder_url", return_value=folder)):
            matched = asyncio.run(verify_existing_pair(
                FakeClient(), "public", "private", -1004392607284,
                public_video, [public_poster], "films"))
        self.assertIs(matched, public_poster)

    def test_no_public_link_without_all_verified_buttons(self):
        source = media(41, "Saga Partie 2", video=True, doc=111)
        public = media(42, "Saga Partie 2", photo=True, buttons=[
            [NS(url="https://t.me/c/4392607284/30")],
        ])
        self.assertIsNone(find_verified_public_link(
            [public], source, "films", -1004392607284, 30,
            "https://t.me/+SomeValidInvite"))


class AdjacentLegacyPairTests(unittest.TestCase):
    def test_photo_then_video_with_generic_video_caption(self):
        photo = media(40, "🎬 Le Secret de Jade", photo=True)
        video = media(41, "Vidéo complète", video=True, name="video.mp4")
        pair = find_neighbor_pair(video, [photo, video], "films")
        self.assertIsNotNone(pair)
        self.assertEqual(pair.mode, "poster_video")
        self.assertEqual(pair.identity.title, "le secret de jade")

    def test_photo_text_video_preserves_description(self):
        cover = media(20, "🎬 Naruto", photo=True)
        description = media(21, "Synopsis : un ninja et ses amis")
        episode = media(22, "Naruto S02E03", video=True, name="naruto.S02E03.mkv")
        pair = find_neighbor_pair(episode, [episode, cover, description], "anime")
        self.assertIsNotNone(pair)
        self.assertEqual(pair.mode, "poster_text_video")
        self.assertEqual((pair.identity.season, pair.identity.episode), (2, 3))
        caption = cover_caption(cover, episode, "anime", identity=pair.identity,
                                extra_text=pair.extra_text)
        self.assertIn("Synopsis : un ninja", caption)

    def test_only_nearest_cover_is_used(self):
        poster = media(100, "🎬 Les Chroniques du Nord", photo=True)
        another = media(101, "🎬 Les Chroniques du Sud", photo=True)
        video = media(102, "Vidéo complète", video=True)
        # The only adjacent poster must be the actually neighbouring one.
        pair = find_neighbor_pair(video, [poster, another, video], "series")
        self.assertIsNotNone(pair)
        self.assertIs(pair.poster, another)

    def test_untitled_neighbour_pair_gets_explicit_non_fabricated_label(self):
        cover = media(210, "", photo=True)
        video = media(211, "Vidéo complète", video=True, name="video.mp4")
        paired = find_neighbor_pair(video, [cover, video], "films")
        self.assertIsNotNone(paired)
        self.assertEqual(paired.identity.kind, "unknown")
        self.assertEqual(paired.identity.title, "contenu sans titre 211")
        self.assertIn("contenu sans titre 211",
                      cover_caption(cover, video, "films", identity=paired.identity))

    def test_description_only_text_not_used_as_movie_title(self):
        cover = media(220, "", photo=True)
        text = media(221, "Synopsis : Une histoire de vengeance")
        video = media(222, "Vidéo complète", video=True, name="video.mp4")
        paired = find_neighbor_pair(video, [cover, text, video], "films")
        self.assertIsNotNone(paired)
        self.assertEqual(paired.identity.kind, "unknown")

    def test_link_preview_still_counts_as_plain_text(self):
        class MessageMediaWebPage:
            pass
        cover = media(230, "🎬 La Ville de Jade", photo=True)
        text = media(231, "Le résumé avec https://youtu.be/dQw4w9WgXcQ")
        text.media = MessageMediaWebPage()
        video = media(232, "Vidéo complète", video=True)
        paired = find_neighbor_pair(video, [cover, text, video], "films")
        self.assertIsNotNone(paired)
        self.assertEqual(paired.mode, "poster_text_video")

    def test_conflicting_film_part_not_reassigned_by_proximity(self):
        photo = media(10, "Film Partie 2", photo=True)
        video = media(11, "Film Partie 1", video=True, name="film.partie.1.mkv")
        self.assertIsNone(find_neighbor_pair(video, [photo, video], "films"))

    def test_only_missing_evidence_is_unmatched_purge_candidate(self):
        video = media(11, "Film inconnu", video=True)
        self.assertTrue(unmatched_candidate(video, [video], "films"))
        photo = media(10, "🎬 Film inconnu", photo=True)
        self.assertFalse(unmatched_candidate(video, [photo, video], "films"))
        promo = media(12, "Bande-annonce du programme", video=True)
        self.assertFalse(unmatched_candidate(promo, [promo], "films"))

    def test_ten_recent_remain_protected_under_unmatched_option(self):
        videos = [media(n, "film inconnu", video=True) for n in range(1, 14)]
        recent, old = split_recent_and_old(videos, "films")
        self.assertEqual({v.id for v in recent}, set(range(4, 14)))
        self.assertEqual({v.id for v in old}, {1, 2, 3})

    def test_old_reposted_cover_cannot_replace_unedited_original(self):
        rescue = "https://t.me/+ABCdefghi123456"
        folder = "https://t.me/addlist/AAA"
        url = "https://t.me/c/4392607284/55"
        source_cover = media(10, "🎬 Les Aventures de Jade", photo=True)
        source_video = media(11, "Vidéo complète", video=True, doc=777)
        repaired = media(900, "🎬 Les Aventures de Jade", photo=True, buttons=[
            [NS(url=url)], [NS(url=rescue)], [NS(url=folder)]
        ])
        private_cover = media(54, "🎬 Les Aventures de Jade", photo=True, buttons=[
            [NS(url=rescue)], [NS(url=folder)]
        ])
        private_video = media(55, "vidéo", video=True, doc=777)
        class Client:
            async def get_messages(self, channel, ids):
                return [private_cover] if isinstance(ids, list) else private_video
        with (patch("film_relay.ten_video_rotation.rescue_link_for", return_value=rescue),
              patch("film_relay.ten_video_rotation.film_folder_url", return_value=folder)):
            linked = asyncio.run(verify_existing_pair(
                Client(), "public", "private", -1004392607284, source_video,
                [source_cover, repaired], "films",
                messages=[source_cover, source_video, repaired]))
        self.assertIsNone(linked)
        # Once the SAME historic image has been edited and carries the links,
        # the original ID is recognized and the public video can be rotated.
        source_cover.buttons = repaired.buttons
        with (patch("film_relay.ten_video_rotation.rescue_link_for", return_value=rescue),
              patch("film_relay.ten_video_rotation.film_folder_url", return_value=folder)):
            linked_original = asyncio.run(verify_existing_pair(
                Client(), "public", "private", -1004392607284, source_video,
                [source_cover, repaired], "films",
                messages=[source_cover, source_video, repaired]))
        self.assertIs(linked_original, source_cover)


if __name__ == "__main__":
    unittest.main()
