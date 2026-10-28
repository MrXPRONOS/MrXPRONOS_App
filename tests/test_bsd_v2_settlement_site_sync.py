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

    def test_only_public_redacted_data_staged(self):
        script = self.workflow
        self.assertIn("from scripts.build_public_site import public_copy", script)
        self.assertIn("public=public_copy(source)", script)
        self.assertIn('assert "diagnostics" not in public', script)
        self.assertIn('assert "model_odds_observations" not in public', script)
        self.assertIn('expected={"data.json"}', script)
        self.assertIn('assert actual==expected', script)
        self.assertIn('publish_dir: ./.bsd-settlement-site-refresh', script)
        self.assertIn("keep_files: true", script)
        self.assertNotIn("publish_dir: ./\\n", script)
        self.assertNotIn("cp bsd/publication_ledger.json", script)
        self.assertNotIn("cp bsd/quality_report.json", script)


    def test_no_telegram_or_full_feed_generation(self):
        script = self.workflow
        self.assertIn("peaceiris/actions-gh-pages@v4.1.0", script)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", script)
        self.assertNotIn("bsd_v2_publish.py", script)
        self.assertNotIn("scripts/send_", script)


if __name__ == "__main__":
    unittest.main()
