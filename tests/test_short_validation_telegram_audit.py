"""Offline tests of the read-only Telegram audit matching (no credentials)."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from scripts.audit_telegram_validation_20261114 import is_expected_video, expected_caption, START, END


class TelegramValidationAuditTests(unittest.TestCase):
    def test_requires_date_caption_video_and_window(self):
        valid = SimpleNamespace(
            id=7040, date=datetime(2026, 11, 14, 22, 45, tzinfo=timezone.utc),
            message=expected_caption("2026-11-14") + "\n4/4 VALIDÉS · AUCUN PERDU",
            video=object(),
        )
        self.assertTrue(is_expected_video(valid))
        self.assertFalse(is_expected_video(SimpleNamespace(**{**vars(valid), "video": None})))
        self.assertFalse(is_expected_video(SimpleNamespace(**{**vars(valid), "message": expected_caption("2026-11-13") + "\nother"})))
        self.assertFalse(is_expected_video(SimpleNamespace(**{**vars(valid), "date": START.replace(hour=20)})))
        self.assertFalse(is_expected_video(SimpleNamespace(**{**vars(valid), "date": END.replace(hour=23, minute=50)})))

    def test_unrelated_media_or_text_never_matches(self):
        self.assertFalse(is_expected_video(SimpleNamespace(
            date=datetime(2026, 11, 14, 22, 46, tzinfo=timezone.utc),
            message="4/4 VALIDÉS", video=object()
        )))
        self.assertFalse(is_expected_video(SimpleNamespace(
            date=None, message=expected_caption("2026-11-14") + "\nvalid", video=object()
        )))


if __name__ == "__main__":
    unittest.main()
