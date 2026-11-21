"""Offline tests: account-based Anime audit makes no Telegram mutations."""
from __future__ import annotations

import unittest
from types import SimpleNamespace as NS

from scripts.anime_user_session_audit import (
    _flatten, _mark_duplicates, summarize_receipt_messages,
)


def video(mid, doc):
    return NS(id=mid, video=object(), document=NS(id=doc, attributes=[]))


class AnimeUserSessionAuditTests(unittest.TestCase):
    def test_genuine_private_and_public_pair(self):
        data = {"series": {"naruto": {
            "episodes": {"1": {"1": {"message_id": 101}}},
            "public_episode_posts": {"S01E01": {
                "poster": 201, "video": 202, "private_video": 101}},
        }}}
        result = summarize_receipt_messages(data,
            {101: video(101, 55)},
            {201: NS(photo=object()), 202: video(202, 55)})
        self.assertEqual(result["verified_public_pairs"], 1)
        self.assertEqual(result["issues"], {})
        self.assertEqual(result["legacy_episodes_without_new_public_receipt"], 0)

    def test_missing_public_video_not_reported_as_verified(self):
        data = {"series": {"naruto": {
            "episodes": {"1": {"1": {"message_id": 101}}},
            "public_episode_posts": {"S01E01": {
                "poster": 201, "video": 202, "private_video": 101}},
        }}}
        result = summarize_receipt_messages(data,
            {101: video(101, 55)}, {201: NS(photo=object())})
        self.assertEqual(result["verified_public_pairs"], 0)
        self.assertEqual(result["issues"]["public_video_missing"], 1)

    def test_same_private_file_reused_for_two_episode_numbers_is_flagged(self):
        data = {"series": {"naruto": {
            "episodes": {"1": {
                "1": {"message_id": 101}, "2": {"message_id": 102}}},
            "public_episode_posts": {},
        }}}
        report = summarize_receipt_messages(data,
            {101: video(101, 55), 102: video(102, 55)}, {})
        self.assertEqual(report["issues"][
            "private_document_used_for_different_episodes"], 1)
        self.assertEqual(report["legacy_episodes_without_new_public_receipt"], 2)

    def test_repeated_public_pair_marker_detected_without_metadata_leak(self):
        def poster(mid, caption):
            return NS(id=mid, photo=object(), raw_text=caption)
        marker = "#CXPAIR_" + "a" * 18
        rows = [poster(1, marker), poster(2, marker),
                poster(3, "#CXPAIR_" + "b" * 18)]
        self.assertEqual(_mark_duplicates(rows), 1)

    def test_empty_catalogue_is_safe(self):
        self.assertEqual(_flatten({"series": {}})[2], 0)


if __name__ == "__main__":
    unittest.main()
