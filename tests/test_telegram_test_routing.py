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

    def test_smoke_card_is_square_and_network_can_be_mocked(self):
        image=telegram_test_smoke.build()
        self.assertEqual(image.size,(1080,1080))
        self.assertEqual(image.mode,"RGB")

if __name__=="__main__":
    unittest.main()
