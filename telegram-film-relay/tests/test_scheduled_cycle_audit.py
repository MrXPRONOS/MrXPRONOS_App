import unittest
from datetime import datetime, timezone
from scripts.scheduled_cycle_audit import audit_runs


class ScheduledCycleAuditTests(unittest.TestCase):
    def test_reports_missing_and_failed_slots(self):
        runs=[{"id":1,"event":"schedule","created_at":"2026-10-27T00:18:00Z","conclusion":"success"},
              {"id":2,"event":"schedule","created_at":"2026-10-27T06:18:00Z","conclusion":"failure"},
              {"id":3,"event":"schedule","created_at":"2026-10-27T22:18:00Z","conclusion":"failure"}]
        report=audit_runs(runs,now=datetime(2026,10,27,23,30,tzinfo=timezone.utc),days=1)
        self.assertEqual(report["expected_slots_elapsed"],4)
        self.assertEqual(report["observed_run_count"],3)
        self.assertEqual(report["approximate_on_time_slots"],2)
        self.assertEqual(report["missing_or_late_slots"],2)
        self.assertEqual(report["failed_runs"],2)
        self.assertEqual(report["status"],"needs_attention")
        self.assertFalse(report["telegram_publication_verified"])

    def test_future_slots_are_not_counted_as_missing(self):
        report=audit_runs([],now=datetime(2026,10,27,2,0,tzinfo=timezone.utc),days=1)
        self.assertEqual(report["expected_slots_elapsed"],1)
        self.assertEqual(report["missing_or_late_slots"],1)

    def test_non_schedule_runs_do_not_fake_coverage(self):
        report=audit_runs([{"event":"workflow_dispatch",
                           "created_at":"2026-10-27T00:18:00Z","conclusion":"success"}],
                          now=datetime(2026,10,27,23,0,tzinfo=timezone.utc),days=1)
        self.assertEqual(report["observed_run_count"],0)
        self.assertEqual(report["status"],"needs_attention")

    def test_duplicate_near_slot_is_reported(self):
        runs=[{"id":1,"event":"schedule","created_at":"2026-10-27T00:18:00Z","conclusion":"success"},
              {"id":2,"event":"schedule","created_at":"2026-10-27T00:19:00Z","conclusion":"success"}]
        report=audit_runs(runs,now=datetime(2026,10,27,1,50,tzinfo=timezone.utc),days=1)
        self.assertEqual(report["duplicated_nearby_slots"],1)
        self.assertEqual(report["status"],"needs_attention")


if __name__ == "__main__":
    unittest.main()
