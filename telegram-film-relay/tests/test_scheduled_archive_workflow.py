"""Offline guard: the twice-daily archive step must never be silently skipped.

No Telegram access. Validate the checked-in production workflow source only.
"""
import unittest
from pathlib import Path

WORKFLOW = (Path(__file__).resolve().parents[2] / ".github" / "workflows"
            / "cinex-public-video-rotation.yml")


class ScheduledArchiveWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = WORKFLOW.read_text(encoding="utf-8")

    def test_scheduled_twice_per_day(self):
        self.assertIn("cron: '0 0,12 * * *'", self.content)

    def test_scheduled_repair_runs_before_deletion(self):
        source = self.content
        repair = source.index(
            "- name: Rattraper les archives anciennes avant la rotation (automatique)")
        rotate = source.index(
            "- name: Supprimer uniquement les anciennes vidéos archivées et vérifiées")
        self.assertLess(repair, rotate)
        step = source[repair:rotate]
        self.assertIn("github.event_name == 'schedule'", step)
        self.assertNotIn("vars.CINEX_LEGACY_REPAIR_ENABLED", step)
        self.assertIn(
            "python -m film_relay.legacy_archive_repair --apply --max-repaired 4",
            step)

    def test_repair_respects_three_independent_admin_authorizations(self):
        source = self.content
        start = source.index(
            "- name: Rattraper les archives anciennes avant la rotation (automatique)")
        finish = source.index(
            "- name: Supprimer uniquement les anciennes vidéos archivées et vérifiées")
        repair = source[start:finish]
        for key in ("CINEX_ARCHIVE_ENABLED",
                    "CINEX_ARCHIVE_DELETE_APPROVED",
                    "CINEX_RIGHTS_VERIFIED"):
            self.assertIn("vars." + key + " == 'true'", repair)
        self.assertIn('if [[ "$RUN_REPAIR_APPLY" != "true" ]]', repair)
        self.assertIn("exit 1", repair)

    def test_cron_deletes_only_verified_archives_not_unknowns(self):
        source = self.content
        start = source.index(
            "- name: Supprimer uniquement les anciennes vidéos archivées et vérifiées")
        rotation = source[start:]
        self.assertIn("github.event_name == 'schedule'", rotation)
        self.assertIn(
            "python -m film_relay.ten_video_rotation --apply --max-deleted 10",
            rotation)
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && inputs.apply == true && inputs.purge_unmatched == true",
            rotation)
        self.assertIn(
            "python -m film_relay.ten_video_rotation --apply --purge-unmatched",
            rotation)
        # The manual purge flag must be set only by a user-invoked workflow.
        self.assertNotIn("main-films-cleanup", rotation)

    def test_telegram_session_serialized_and_never_cancelled(self):
        source = self.content
        self.assertIn("group: mrx-telegram-personal-account", source)
        self.assertIn("cancel-in-progress: false", source)
        self.assertIn("scripts/check_personal_cooldown.py", source)


if __name__ == "__main__":
    unittest.main()
