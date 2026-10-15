"""Regression checks for settlement-only GitHub Pages refresh."""
from pathlib import Path
import unittest

WATCHDOG = Path(".github/workflows/bsd-v2-settlement-watchdog.yml")


class SettlementPagesSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WATCHDOG.read_text(encoding="utf-8")

    def test_dispatch_only(self):
        self.assertIn("  workflow_dispatch:", self.workflow)
        self.assertNotIn("\n  push:", self.workflow)
        self.assertNotIn("\n  pull_request:", self.workflow)

    def test_upload_only_after_successful_commit(self):
        script = self.workflow
        self.assertIn("id: settlement_commit", script)
        self.assertLess(script.index("git push origin HEAD:main"),
                        script.index('echo "published=true" >> "$GITHUB_OUTPUT"'))
        self.assertIn('echo "published=false" >> "$GITHUB_OUTPUT"', script)
        self.assertEqual(
            script.count("if: steps.settlement_commit.outputs.published == 'true'"), 2)

    def test_exactly_three_staged_bsd_files(self):
        script = self.workflow
        for path in ("data.json", "bsd/publication_ledger.json",
                     "bsd/quality_report.json"):
            self.assertIn(f'cp {path} .bsd-settlement-site-refresh/{path}', script)
        self.assertIn('assert files==expected', script)
        self.assertIn('publish_dir: ./.bsd-settlement-site-refresh', script)
        self.assertIn("keep_files: true", script)
        self.assertNotIn("publish_dir: ./\n", script)

    def test_no_telegram_or_full_feed_generation(self):
        script = self.workflow
        self.assertIn("peaceiris/actions-gh-pages@v4.1.0", script)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", script)
        self.assertNotIn("bsd_v2_publish.py", script)
        self.assertNotIn("scripts/send_", script)


if __name__ == "__main__":
    unittest.main()
