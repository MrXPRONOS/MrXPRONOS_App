"""Offline tests for manual stock fallback decisions. No Telegram network."""
import unittest
from film_relay.manual_fallback_core import (
    Candidate, CYCLE_CAPS, choose_candidates, may_activate_fallback,
    semantic_identity,
)


def item(*, category="films", chat="-1001234567890", poster=1,
         video=2, title="Example Film (2025)", media="unique-file-0001",
         season=None, episode=None, rights=True):
    return Candidate(category, chat, poster, video, title, media,
                     season=season, episode=episode, rights_confirmed=rights)


class ManualFallbackTests(unittest.TestCase):
    def test_activation_requires_revoked_session_and_all_gates(self):
        base = dict(personal_status="session_revoked", bot_ready=True,
                    stock_ready=True, rights_attested=True,
                    durable_receipts=True, owner_enabled=True)
        self.assertTrue(may_activate_fallback(**base))
        for key in ("bot_ready", "stock_ready", "rights_attested",
                    "durable_receipts", "owner_enabled"):
            self.assertFalse(may_activate_fallback(**{**base, key: False}))
        for status in ("ok", "flood_wait", "peer_flood", "timeout",
                       "telegram_unknown", "uncertain_send"):
            self.assertFalse(may_activate_fallback(**{**base, "personal_status": status}))

    def test_no_replay_after_normal_publish(self):
        source = item()
        output = choose_candidates([source], published_media={"file:unique-file-0001"})
        self.assertEqual(output["selected"], [])
        self.assertEqual(output["duplicates"][0][1], "already_delivered")

    def test_no_replay_same_movie_different_message(self):
        first = item()
        second = item(video=23, poster=22, media="unique-file-0001")
        output = choose_candidates([first, second])
        self.assertEqual(len(output["selected"]), 1)
        self.assertEqual(len(output["duplicates"]), 1)

    def test_cross_category_media_collision_blocks_both(self):
        first = item()
        second = item(category="comedie", video=3, poster=4)
        output = choose_candidates([first, second])
        self.assertEqual(len(output["selected"]), 0)
        self.assertTrue(all(reason == "same_video_conflicting_title"
                            for _, reason in output["review"]))

    def test_film_year_disambiguates_remakes(self):
        first = item()
        second = item(video=3, poster=4, title="Example Film (2026)",
                      media="unique-file-0002")
        self.assertNotEqual(semantic_identity(first), semantic_identity(second))
        self.assertEqual(len(choose_candidates([first, second])["selected"]), 2)

    def test_missing_year_is_quarantined_without_file_identity(self):
        one = item(title="Example Film", media="")
        self.assertEqual(choose_candidates([one])["review"][0][1], "insufficient_identity")

    def test_distinct_media_same_title_requires_review(self):
        first = item()
        second = item(poster=4, video=5, media="unique-file-0002")
        output = choose_candidates([first, second])
        self.assertFalse(output["selected"])
        self.assertEqual(len(output["review"]), 2)

    def test_series_episode_identity(self):
        a = item(category="series", title="Great Show", season=1, episode=3)
        b = item(category="series", title="Great Show", season=1, episode=4,
                 poster=4, video=5, media="unique-file-0002")
        self.assertNotEqual(semantic_identity(a), semantic_identity(b))
        self.assertEqual(len(choose_candidates([a, b])["selected"]), 2)

    def test_missing_episode_keeps_video_from_publishing_if_no_media(self):
        a = item(category="animes", title="Great Anime", media="")
        self.assertEqual(choose_candidates([a])["selected"], [])

    def test_caps_include_existing_normal_posts(self):
        entries = [item(video=2+i, poster=100+i, title=f"Film {i} (2025)",
                        media=f"media-value-{i:04}") for i in range(5)]
        out = choose_candidates(entries, already_used={"films": 1})
        self.assertEqual(len(out["selected"]), CYCLE_CAPS["films"] - 1)

    def test_courses_one_per_category(self):
        entries = [item(category="formation_business",
                        title=f"Lesson {i}", video=i+2, poster=i+100,
                        media=f"unique-class-{i:03}") for i in range(4)]
        out = choose_candidates(entries)
        self.assertEqual(len(out["selected"]), 1)

    def test_rights_missing_is_not_published(self):
        out = choose_candidates([item(rights=False)])
        self.assertEqual(out["review"][0][1], "missing_rights")

    def test_invalid_chat_and_fake_video_rejected(self):
        with self.assertRaises(ValueError):
            item(chat="@channel")
        with self.assertRaises(ValueError):
            item(poster=2, video=2)


if __name__ == "__main__":
    unittest.main()
