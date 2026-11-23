"""CineX V4 boundaries: dedicated series get no Secours, only newly posted
videos receive the 24-hour expiry marker."""
import unittest
from types import SimpleNamespace as NS

from film_relay.cinex_v4_policy import (
    AUTO_VIDEO_TTL_TAG, MAIN_RELAY_HANDLES, DEDICATED_NO_SECOURS,
    canonical_public_handle, is_main_relay,
    has_automatic_ttl, caption_with_automatic_ttl,
)
from film_relay.rescue_channels import targets_from_env


class CineXV4PolicyTests(unittest.TestCase):
    def test_seven_general_relay_channels_only(self):
        self.assertEqual(len(MAIN_RELAY_HANDLES), 7)
        self.assertEqual(len(DEDICATED_NO_SECOURS), 4)
        self.assertTrue(MAIN_RELAY_HANDLES.isdisjoint(DEDICATED_NO_SECOURS))
        self.assertEqual(set(targets_from_env({
            "COMEDIE_PUBLIC_CHANNEL": "@CineXComediefr",
        })), MAIN_RELAY_HANDLES)

    def test_single_work_channels_never_get_backup(self):
        for handle in DEDICATED_NO_SECOURS:
            self.assertFalse(is_main_relay(handle))
        for handle in MAIN_RELAY_HANDLES:
            self.assertTrue(is_main_relay(handle))

    def test_rejects_unconfigured_or_malformed_backup_destination(self):
        with self.assertRaisesRegex(ValueError, "Secours interdit"):
            targets_from_env({"TG_PUBLIC_CHANNEL": "@RandomMoviesPublic"})
        self.assertIsNone(canonical_public_handle("https://t.me/no"))

    def test_posting_marker_is_idempotent_and_only_on_new_videos(self):
        caption = caption_with_automatic_ttl("<b>Épisode S01E01</b>")
        self.assertEqual(caption.split().count(AUTO_VIDEO_TTL_TAG), 1)
        self.assertEqual(caption, caption_with_automatic_ttl(caption))
        self.assertTrue(has_automatic_ttl(NS(raw_text=caption)))
        self.assertFalse(has_automatic_ttl(NS(raw_text="Film ancien sans marqueur")))
        self.assertFalse(has_automatic_ttl(NS(raw_text=None)))

    def test_tag_in_other_text_not_accepted(self):
        self.assertFalse(has_automatic_ttl(NS(
            raw_text="prefix" + AUTO_VIDEO_TTL_TAG + "suffix"
        )))


if __name__ == "__main__":
    unittest.main()
