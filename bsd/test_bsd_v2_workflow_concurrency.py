from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/bsd-v2-production.yml")


class TestBsdV2ProductionWorkflowSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_production_workflow_is_not_triggered_by_pull_requests(self):
        self.assertNotIn("\n  pull_request:\n", self.text)

    def test_multisource_corroboration_is_enabled(self):
        self.assertIn("BSD_MULTISOURCE_CC0: '1'", self.text)

    def test_serialized_production_checks_out_latest_main(self):
        self.assertIn("ref: main", self.text)
        checkout = self.text.index("uses: actions/checkout@v4")
        latest = self.text.index("ref: main", checkout)
        build = self.text.index("Build BSD V2 site feed and settle completed matches")
        self.assertLess(latest, build)

    def test_concurrent_main_updates_are_rebased_and_retried(self):
        self.assertIn("for attempt in 1 2 3 4 5; do", self.text)
        self.assertIn("git pull --rebase origin main", self.text)
        self.assertIn("if git push origin HEAD:main; then", self.text)
        self.assertIn('if [ "$pushed" -ne 1 ]; then', self.text)

    def test_validation_precedes_commit_and_push(self):
        validation = self.text.index('assert data["source"]=="bsd"')
        commit = self.text.index('git commit -m "data(bsd): publish V2 football picks and verified results"')
        self.assertLess(validation, commit)


    def test_full_multisource_gate_runs_before_append_only_audit(self):
        full_gate = self.text.index("Build and apply fully-qualified multisource candidates")
        audit = self.text.index("Archive first-seen published selections and audit quality")
        commit = self.text.index('git commit -m "data(bsd): publish V2 football picks and verified results"')
        self.assertLess(full_gate, audit)
        self.assertLess(audit, commit)

    def test_full_gate_is_fail_closed_and_does_not_send_telegram(self):
        self.assertIn("--accepted-output=tmp/multisource-qualified-accepted.json", self.text)
        self.assertIn("football_multisource_apply_qualified.py", self.text)
        self.assertIn('mg.get("thresholds_lowered") is False', self.text)
        self.assertIn('mg.get("telegram_sent_by_this_step") is False', self.text)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", self.text)



if __name__ == "__main__":
    unittest.main()
