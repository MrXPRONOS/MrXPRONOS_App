"""Offline checks: GitHub cycle receipts are not real Telegram publication proof."""
import tempfile
import unittest
import json
from pathlib import Path
from scripts.cycle_health import build_report, receipt_counts, FILES


class CycleHealthTests(unittest.TestCase):
    def test_positive_receipts_are_not_telegram_publication_proof(self):
        before={name:0 for name in FILES}
        after={name:2 for name in FILES}
        statuses={name:"success" for name in FILES}
        report=build_report(before,after,statuses,event="schedule",
                            manual_publish=False,run_id="123")
        self.assertEqual(report["status"],"receipts_detected_unverified")
        self.assertFalse(report["publication_verified_on_telegram"])
        self.assertEqual(report["categories"]["films"]["new_receipts_net"],2)

    def test_zero_receipts_reported_as_attention_not_success(self):
        before={name:3 for name in FILES}
        report=build_report(before,before,{name:"success" for name in FILES},
                            event="schedule",manual_publish=False)
        self.assertEqual(report["status"],"needs_attention")
        self.assertEqual(report["categories"]["anime"]["status"],"no_new_receipts")

    def test_failed_category_fails_cycle_even_other_counts_increase(self):
        before={name:1 for name in FILES}
        after={name:2 for name in FILES}
        outcomes={name:"success" for name in FILES}
        outcomes["series"]="failure"
        result=build_report(before,after,outcomes,event="schedule",manual_publish=False)
        self.assertEqual(result["status"],"needs_attention")
        self.assertEqual(result["categories"]["series"]["status"],"failed")

    def test_manual_diagnostics_dont_claim_publishing(self):
        data=build_report({}, {}, {},event="workflow_dispatch",manual_publish=False)
        self.assertEqual(data["status"],"diagnostic_only")
        self.assertFalse(data["publication_requested"])

    def test_missing_receipt_files_are_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/"state.json").write_text(json.dumps({"processed":{"one":1}}))
            counts=receipt_counts(folder)
            self.assertEqual(counts["films"],1)
            self.assertIsNone(counts["anime"])


if __name__ == "__main__":
    unittest.main()
