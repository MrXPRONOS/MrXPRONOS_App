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


if __name__ == "__main__":
    unittest.main()
