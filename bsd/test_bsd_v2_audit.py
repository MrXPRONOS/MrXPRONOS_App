"""Tests for append-only BSD audit and separate monitoring metrics."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bsd_v2_audit import update_ledger, audit_report


def row(ident, *, status="notstarted", h=None, a=None, source="bsd_consensus",
        odds=1.5, key="OVER_15", category="Pro", confidence=80):
    pick = {"selection_key": key, "market": "over_under_15",
            "confidence": confidence, "odds_source": source, "odds": odds}
    return {
        "id": "bsd:"+str(ident), "source_event_id": ident, "source": "bsd",
        "event_date": "2026-10-11T18:00:00+00:00",
        "date": "2026-10-11", "status": status,
        "home_score": h, "away_score": a, "prediction": pick,
        "predictions": [pick, {"selection_key": "1X", "market": "double_chance",
                               "confidence": 85, "odds_source": "mrxpronos_model",
                               "odds": 1.2}],
        "category": category,
        "home_team": "A", "away_team": "B", "league": "Test League",
    }


class PublicationAuditTests(unittest.TestCase):
    def test_preserve_original_after_feed_removal(self):
        at = "2026-10-11T00:05:00+00:00"
        ledger = update_ledger({}, [row(1), row(2)], observed_at=at)
        self.assertEqual(len(ledger["entries"]), 2)
        ledger = update_ledger(ledger, [row(1, key="UNDER_35")],
                               observed_at="2026-10-11T07:00:00+00:00")
        self.assertEqual(len(ledger["entries"]), 2)
        self.assertEqual(ledger["entries"][0]["original_pick"]["selection_key"], "OVER_15")
        self.assertEqual(ledger["entries"][1]["feed_state"], "absent_from_current_feed")
        self.assertEqual(ledger["entries"][1]["withdrawal_reason"], "unexplained_absence_needs_review")

    def test_pending_never_counts_as_loss(self):
        ledger = update_ledger({}, [row(3)],
                               observed_at="2026-10-11T00:00:00+00:00")
        report = audit_report(ledger)
        self.assertEqual(report["unsettled"], 1)
        self.assertEqual(report["settled"], 0)
        self.assertEqual(report["primary"]["n"], 0)

    def test_settle_frozen_choice_with_fixture_score(self):
        ledger = update_ledger({}, [row(3)],
                               observed_at="2026-10-11T00:00:00+00:00")
        ledger = update_ledger(ledger, [], [row(3, status="finished", h=1, a=0)],
                               observed_at="2026-10-11T22:00:00+00:00")
        report = audit_report(ledger)
        self.assertEqual(report["primary"]["losses"], 1)
        self.assertEqual(report["secondary"]["wins"], 1)
        self.assertEqual(report["absent_from_current_feed"], 1)
        self.assertEqual(report["primary"]["priced_by_verified_source"], 1)
        self.assertEqual(report["secondary"]["estimated_or_unpriced"], 1)
        self.assertIsNone(report["secondary"]["theoretical_flat_stake_yield_on_verified_quotes"])

    def test_estimated_odds_not_treated_as_verified_roi(self):
        ledger = update_ledger({}, [row(4, status="finished", h=2, a=1,
                                         source="mrxpronos_model")],
                               observed_at="2026-10-11T23:00:00+00:00")
        report = audit_report(ledger)
        self.assertEqual(report["primary"]["wins"], 1)
        self.assertEqual(report["primary"]["priced_by_verified_source"], 0)
        self.assertIsNone(report["primary"]["theoretical_flat_stake_yield_on_verified_quotes"])

    def test_idempotent_addition(self):
        orig = row(5)
        ledger = update_ledger({}, [orig], observed_at="2026-10-11T00:00:00+00:00")
        ledger = update_ledger(ledger, [orig], observed_at="2026-10-11T00:00:00+00:00")
        self.assertEqual(len(ledger["entries"]), 1)
        self.assertEqual(ledger["last_run"]["new"], 0)

    def test_incomplete_score_does_not_settle(self):
        ledger = update_ledger({}, [row(7)],
                               observed_at="2026-10-11T00:00:00+00:00")
        ledger = update_ledger(ledger, [], [row(7, status="finished", h=2)],
                               observed_at="2026-10-11T22:00:00+00:00")
        self.assertEqual(audit_report(ledger)["unsettled"], 1)


if __name__ == "__main__":
    unittest.main()
