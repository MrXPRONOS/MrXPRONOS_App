from pathlib import Path
import unittest


WORKFLOW = Path(".github/workflows/bsd-v2-production.yml")


class TestBsdV2ProductionWorkflowConcurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_multisource_corroboration_stays_enabled(self):
        self.assertIn("BSD_MULTISOURCE_CC0: '1'", self.text)

    def test_concurrent_push_is_retried_after_rebase(self):
        self.assertIn("for attempt in 1 2 3 4 5; do", self.text)
        self.assertIn("git pull --rebase origin main", self.text)
        self.assertIn("if git push origin HEAD:main; then", self.text)
        self.assertIn('if [ "$pushed" -ne 1 ]; then', self.text)
        self.assertIn("exit 1", self.text)

    def test_data_commit_still_occurs_only_after_feed_validation(self):
        validation = self.text.index('assert data["source"]=="bsd"')
        commit = self.text.index('git commit -m "data(bsd): publish V2 football picks and verified results"')
        self.assertLess(validation, commit)


if __name__ == "__main__":
    unittest.main()
