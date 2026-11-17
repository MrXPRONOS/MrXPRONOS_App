"""Structural checks: schedule, state persistence, verification before monitoring."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class WorkflowGuardrailsTests(unittest.TestCase):
    def test_only_four_daily_scheduled_runs(self):
        text = (ROOT / ".github/workflows/telegram-film-relay.yml").read_text(encoding="utf-8")
        self.assertIn("cron: '17 */6 * * *'", text)
        self.assertEqual(text.count("    - cron:"), 1)
        self.assertIn("group: mrx-telegram-personal-account", text)
        self.assertIn("cancel-in-progress: false", text)

    def test_monitor_reads_telegram_receipts_and_is_persisted(self):
        text = (ROOT / ".github/workflows/telegram-film-relay.yml").read_text(encoding="utf-8")
        self.assertLess(text.index("name: Confirmer les nouvelles publications directement sur Telegram"),
                        text.index("name: Surveiller publications, erreurs et cycles vides"))
        self.assertIn("steps.telegram_check.outputs.verification_status", text)
        self.assertIn('merge_cycle_monitor.py "$RUNNER_TEMP/cinex-cycle-monitor.json"', text)
        self.assertIn('"$STATE/cycle_monitor.json"', text)
        self.assertIn("CINEX_TORRENT9_PAUSED: 'true'", text)
        self.assertIn("CINEX_PARTNERSHIP_ENABLED: 'false'", text)

    def test_audit_cannot_publish(self):
        text = (ROOT / ".github/workflows/cinex-channel-audit.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/channel_audit.py", text)
        self.assertIn("COMEDIE_BOT_TOKEN:", text)
        # Audit code requests metadata and permissions only.
        script = (ROOT / "telegram-film-relay/scripts/channel_audit.py").read_text(encoding="utf-8")
        self.assertNotIn("send_message(", script)
        self.assertNotIn("send_file(", script)


if __name__ == "__main__":
    unittest.main()
