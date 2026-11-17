"""Offline reliability checks for no-post streak and failure alerting."""
import unittest
from scripts.cycle_monitor import update_monitor

OK = {k: "success" for k in ("films", "series", "desir", "comedie", "anime")}


class CycleMonitorTests(unittest.TestCase):
    def cycle(self, prev=None, run="1", verification="no_new_posts",
              posts=0, outcomes=None):
        return update_monitor(prev or {}, run_id=run, verification=verification,
                              verified_posts=posts, outcomes=outcomes or OK,
                              now="2026-11-17T00:00:00+00:00")

    def test_two_empty_cycles_alert(self):
        a = self.cycle()
        self.assertEqual(a["empty_streak"], 1)
        self.assertFalse(a["alert"])
        b = self.cycle(a, run="2")
        self.assertEqual(b["empty_streak"], 2)
        self.assertTrue(b["alert"])

    def test_verified_publication_resets_streak(self):
        a = self.cycle(self.cycle(), run="2", verification="verified", posts=2)
        self.assertEqual(a["status"], "published")
        self.assertEqual(a["empty_streak"], 0)
        self.assertFalse(a["alert"])

    def test_failures_do_not_count_as_empty(self):
        first = self.cycle()
        broken = dict(OK, comedie="failure")
        second = self.cycle(first, run="2", outcomes=broken)
        self.assertEqual(second["status"], "category_failed")
        self.assertEqual(second["empty_streak"], 1)
        self.assertTrue(second["alert"])
        third = self.cycle(second, run="3", verification="error")
        self.assertEqual(third["status"], "verification_failed")
        self.assertEqual(third["empty_streak"], 1)

    def test_idempotent_retry(self):
        first = self.cycle()
        self.assertEqual(self.cycle(first), first)

    def test_inconsistent_verification_alerts(self):
        result = self.cycle(verification="verified", posts=0)
        self.assertEqual(result["status"], "verification_inconsistent")
        self.assertTrue(result["alert"])

    def test_reject_invalid_run_id(self):
        with self.assertRaises(ValueError):
            self.cycle(run="invalid")


if __name__ == "__main__":
    unittest.main()
