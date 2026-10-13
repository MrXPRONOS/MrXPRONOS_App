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

    def test_visual_test_workflows_never_reference_production_chat_id(self):
        for path in (
            ".github/workflows/football-live-test-once.yml",
            ".github/workflows/football-visual-live-test-once.yml",
            ".github/workflows/football-premium-validation-once.yml",
        ):
            text=self.read(path)
            self.assertIn("TELEGRAM_TEST_CHAT_ID",text,path)
            self.assertNotIn("secrets.FOOTBALL_NEWS_CHAT_ID",text,path)
            self.assertIn("github.event_name == 'workflow_dispatch'",text,path)

    def test_production_workflow_has_separate_test_state_and_no_prod_site_update_for_test(self):
        text=self.read(".github/workflows/football-production.yml")
        self.assertIn(".state/mrxpronos-football-test.json",text)
        self.assertIn(".state/mrxpronos-football.json",text)
        self.assertIn("steps.telegram_route.outputs.destination == 'production'",text)
        self.assertIn('default: "test"',text)
        self.assertIn("TELEGRAM_TEST_CHAT_ID manquant",text)

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
            ".github/workflows/football-live-test-once.yml",
            ".github/workflows/football-visual-live-test-once.yml",
            ".github/workflows/football-premium-validation-once.yml",
            ".github/workflows/bsd-v2-telegram-hourly.yml",
            ".github/workflows/editorial-telegram.yml",
            ".github/workflows/telegram-test-channel-smoke.yml",
        )
        for path in paths:
            text=self.read(path)
            self.assertIn("@predict_mrxp",text,path)
            self.assertIn("TELEGRAM_TEST_CHAT_ID",text,path)

    def test_manual_visual_workflows_do_not_require_a_linked_test_discussion(self):
        for path in (
            ".github/workflows/football-live-test-once.yml",
            ".github/workflows/football-visual-live-test-once.yml",
            ".github/workflows/football-premium-validation-once.yml",
        ):
            self.assertIn("FOOTBALL_REQUIRE_COMMENTS: '0'", self.read(path), path)

    def test_s3_s4_reruns_checkout_current_main_and_lock_comments_off(self):
        for path in (
            ".github/workflows/football-live-test-once.yml",
            ".github/workflows/football-premium-validation-once.yml",
        ):
            text=self.read(path)
            self.assertIn("ref: main", text, path)
            self.assertGreaterEqual(
                text.count("FOOTBALL_REQUIRE_COMMENTS: '0'"), 2, path
            )
            self.assertIn("TELEGRAM_TEST_COMMENTS_DISABLED_OK", text, path)


    def test_five_business_systems_e2e_has_no_overlapping_child_workflows(self):
        script=self.read("scripts/telegram_live_e2e.py")
        workflow=self.read(".github/workflows/telegram-real-e2e-once.yml")
        for stage in ("S1_NEWS", "S2_CYCLE", "S3_DATA", "S4_COMMUNAUTE", "S5_VIRAL"):
            self.assertIn(stage, script)
        for obsolete in (
            "telegram-test-channel-smoke.yml",
            "football-visual-live-test-once.yml",
            "football-live-test-once.yml",
            "football-premium-validation-once.yml",
            "bsd-v2-telegram-hourly.yml",
        ):
            self.assertNotIn(obsolete, script)
        self.assertNotIn("workflow run", script)
        self.assertNotIn("actions: write", workflow)
        self.assertIn("FOOTBALL_NEWS_CHAT_ID: ${{ secrets.TELEGRAM_TEST_CHAT_ID", workflow)
        self.assertIn("FIVE_SYSTEMS_E2E_OK messages=5 doublons=0", script)

    def test_smoke_card_is_square_and_network_can_be_mocked(self):
        image=telegram_test_smoke.build()
        self.assertEqual(image.size,(1080,1080))
        self.assertEqual(image.mode,"RGB")

if __name__=="__main__":
    unittest.main()
