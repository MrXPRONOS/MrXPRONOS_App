"""Production scheduling invariants: only one recurring source for BSD Telegram."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


class BsdSchedulerSafetyTests(unittest.TestCase):
    def test_coupons_use_external_cron_only(self):
        text = workflow("bsd-v2-telegram-hourly.yml")
        self.assertNotIn("\n  schedule:", text)
        self.assertIn("\n  workflow_dispatch:", text)
        self.assertIn('if [ "$TRIGGER_SOURCE" = "cron-job.org" ]; then', text)
        self.assertIn('if [ "$GITHUB_EVENT_NAME" = "push" ]; then', text)
        self.assertIn("--dry-run", text)
        self.assertIn("group: bsd-v2-telegram-hourly", text)

    def test_verified_winners_use_external_cron_only(self):
        text = workflow("bsd-v2-telegram-wins.yml")
        self.assertNotIn("\n  schedule:", text)
        self.assertIn("\n  workflow_dispatch:", text)
        self.assertIn("group: bsd-v2-telegram-wins", text)

    def test_generator_watchdog_share_writer_lock(self):
        generation = workflow("bsd-v2-production.yml")
        watchdog = workflow("bsd-v2-settlement-watchdog.yml")
        for text in (generation, watchdog):
            self.assertIn("group: bsd-v2-data-writer", text)
            self.assertIn("cancel-in-progress: false", text)
        # Intentional additional intraday recalculations, not duplicated cron times.
        self.assertIn("cron: '17 11,16 * * *'", generation)
        self.assertNotIn("\n  schedule:", watchdog)

    def test_canary_is_readonly_and_importable_in_runner(self):
        text = workflow("football-cc0-bsd-canary.yml")
        self.assertIn("PYTHONPATH:", text)
        self.assertIn("python -m scripts.football_cc0_bsd_canary", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("BSD_CC0_CANARY_PRODUCTION_FEEDS_UNCHANGED", text)
        self.assertNotIn("contents: write", text)


if __name__ == "__main__":
    unittest.main()
