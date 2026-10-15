"""Sécurité du routage Telegram test/prod, sans réseau."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from scripts import telegram_test_smoke, editorial_telegram

ROOT=Path(__file__).resolve().parents[1]

class TelegramTestRoutingTests(unittest.TestCase):
    def read(self,path):
        return (ROOT/path).read_text(encoding="utf-8")

    def test_actu_foot_manual_suite_never_references_production_chat_id(self):
        path = ".github/workflows/actu-foot-test-suite.yml"
        text = self.read(path)
        self.assertIn("TELEGRAM_TEST_CHAT_ID", text)
        self.assertNotIn("secrets.FOOTBALL_NEWS_CHAT_ID", text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn("telegram_test_guard.py", text)

    def test_production_workflow_has_separate_test_state_and_supabase_news_path(self):
        text=self.read(".github/workflows/football-production.yml")
        self.assertIn(".state/mrxpronos-football-test.json",text)
        self.assertIn(".state/mrxpronos-football.json",text)
        self.assertIn('default: "test"',text)
        self.assertIn("TELEGRAM_TEST_CHAT_ID manquant",text)
        self.assertIn("SUPABASE_URL", text)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", text)
        self.assertNotIn("git add footnews.json", text)
        self.assertNotIn("git push origin HEAD:main", text)

    def test_bsd_manual_defaults_to_test_but_cron_routes_production(self):
        text=self.read(".github/workflows/bsd-v2-telegram-hourly.yml")
        self.assertIn('default: "test"',text)
        self.assertIn('[ "$TRIGGER_SOURCE" = "cron-job.org" ]',text)
        self.assertIn("TELEGRAM_TEST_CHAT_ID",text)

    def test_editorial_cli_can_use_an_isolated_queue(self):
        with tempfile.TemporaryDirectory() as d:
            q=Path(d)/"queue.json"
            q.write_text("[]",encoding="utf-8")
            result=editorial_telegram.publish(queue_path=q,enabled=False)
            self.assertTrue(result["dry_run"])

    def test_public_test_channel_is_the_default_everywhere(self):
        paths=(
            ".github/workflows/football-production.yml",
            ".github/workflows/actu-foot-test-suite.yml",
            ".github/workflows/bsd-v2-telegram-hourly.yml",
            ".github/workflows/editorial-telegram.yml",
            ".github/workflows/telegram-test-channel-smoke.yml",
        )
        for path in paths:
            text=self.read(path)
            self.assertIn("@predict_mrxp",text,path)
            self.assertIn("TELEGRAM_TEST_CHAT_ID",text,path)

    def test_manual_actu_foot_suite_locks_comments_off(self):
        text = self.read(".github/workflows/actu-foot-test-suite.yml")
        self.assertIn("FOOTBALL_REQUIRE_COMMENTS: '0'", text)
        self.assertIn("TELEGRAM_TEST_GUARD_BOT_TOKEN", text)

    def test_actu_foot_suite_is_manual_only_and_has_all_modes(self):
        text = self.read(".github/workflows/actu-foot-test-suite.yml")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("push:", text)
        for mode in ("templates", "live", "visual", "viral", "health", "all"):
            self.assertIn(mode, text)
        self.assertIn("--live-test", text)
        self.assertIn("--visual-test", text)
        self.assertIn("actu_foot_health_report.py", text)

    def test_obsolete_actu_foot_one_shots_are_replaced_by_manual_suite(self):
        consolidated = ROOT / ".github/workflows/actu-foot-test-suite.yml"
        self.assertTrue(consolidated.is_file())
        for path in (
            ".github/workflows/actu-foot-copy-samples-once.yml",
            ".github/workflows/football-live-test-once.yml",
            ".github/workflows/football-premium-validation-once.yml",
            ".github/workflows/football-visual-live-test-once.yml",
            ".github/workflows/football-viral-visual-test-once.yml",
        ):
            self.assertFalse((ROOT / path).exists(), path)

    def test_five_business_systems_review_replaces_old_e2e_workflow(self):
        script=self.read("scripts/football_five_systems_test.py")
        workflow=self.read(".github/workflows/football-five-systems-review.yml")
        self.assertFalse((ROOT / ".github/workflows/telegram-real-e2e-once.yml").exists())
        self.assertFalse((ROOT / "scripts/telegram_live_e2e.py").exists())
        for category in (
            "programme", "avant_match", "resultat", "statistique", "flash",
            "composition", "kickoff", "goal", "quiz", "debat", "reaction",
            "viral_news", "viral_match", "viral_stat",
        ):
            self.assertIn(category, script)
        self.assertNotIn("workflow run", script)
        self.assertNotIn("actions: write", workflow)
        self.assertIn("FOOTBALL_NEWS_CHAT_ID: ${{ secrets.TELEGRAM_TEST_CHAT_ID", workflow)
        self.assertIn("telegram_test_guard.py", workflow)

    def test_smoke_card_is_square_and_network_can_be_mocked(self):
        image=telegram_test_smoke.build()
        self.assertEqual(image.size,(1080,1080))
        self.assertEqual(image.mode,"RGB")

if __name__=="__main__":
    unittest.main()
