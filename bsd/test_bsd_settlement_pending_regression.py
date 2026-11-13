"""Regression tests: pending BSD settlement -> definitive score, no bet changes."""
import copy
import unittest
from datetime import datetime, timezone, timedelta

from bsd_v2_settlement_watchdog import (
    apply_watchdog, reconcile_finished_state, unresolved_published)
from bsd_markets import candidates_from_goals
from bsd_v2_publish import update_settlement


NOW = datetime(2026, 11, 13, 18, 0, tzinfo=timezone.utc)
KICKOFF = (NOW - timedelta(hours=9)).isoformat()
PICK = candidates_from_goals(1.3, 1.1)[0].key


def match(**changes):
    result = {
        "id": "bsd:123",
        "source_event_id": "123",
        "source": "bsd",
        "event_date": KICKOFF,
        "status": "settlement_pending",
        "is_finished": False,
        "settlement_pending": True,
        "settlement_checked_at": (NOW - timedelta(hours=5)).isoformat(),
        "settlement_watchdog": {
            "stage": "h4", "pending": True,
            "next_retry_after": (NOW - timedelta(hours=1)).isoformat(),
        },
        "prediction": {
            "selection_key": PICK, "market": "goals",
            "odds": 1.82, "odds_source": "bsd_consensus",
            "confidence": 82,
        },
        "home_score": None, "away_score": None,
    }
    result.update(changes)
    return result


def event(**changes):
    result = {
        "id": 123, "event_date": KICKOFF,
        "status": "finished", "home_score": 2, "away_score": 1,
    }
    result.update(changes)
    return result


class SettlementPendingRegression(unittest.TestCase):
    def test_native_settlement_clears_stale_pending(self):
        original = match()
        snapshot = copy.deepcopy(original["prediction"])
        finished = update_settlement(original, event())
        self.assertEqual(finished["status"], "finished")
        self.assertIs(finished["is_finished"], True)
        self.assertNotIn("settlement_pending", finished)
        self.assertNotIn("settlement_checked_at", finished)
        self.assertIs(finished["settlement_watchdog"]["pending"], False)
        self.assertNotIn("next_retry_after", finished["settlement_watchdog"])
        self.assertEqual(finished["prediction"], snapshot)
        self.assertIs(original["settlement_pending"], True)

    def test_watchdog_final_settlement_clears_stale_pending(self):
        original = match()
        data = {"matches": [original]}
        result = apply_watchdog(data, {"123": event()}, now=NOW)
        finished = result["matches"][0]
        self.assertTrue(finished["is_finished"])
        self.assertEqual(finished["status"], "finished")
        self.assertNotIn("settlement_pending", finished)
        self.assertEqual(finished["prediction"], original["prediction"])
        self.assertEqual(result["settlement_watchdog"]["settled"], 1)

    def test_pending_match_without_verified_score_stays_pending(self):
        result = apply_watchdog({"matches": [match()]}, {"123": event(home_score=None)}, now=NOW)
        row = result["matches"][0]
        self.assertFalse(row["is_finished"])
        self.assertTrue(row["settlement_pending"])
        self.assertEqual(row["status"], "settlement_pending")

    def test_retry_cooldown_prevents_repeat_api_checks(self):
        upcoming = NOW + timedelta(hours=2)
        row = match(settlement_watchdog={
            "pending": True, "stage": "h8",
            "next_retry_after": upcoming.isoformat()})
        self.assertEqual(unresolved_published([row], NOW), [])
        untouched = apply_watchdog({"matches": [row]}, {"123": event()}, now=NOW)
        self.assertEqual(untouched["matches"][0], row)
        self.assertEqual(untouched["settlement_watchdog"]["checked"], 0)

    def test_manual_reconciliation_needs_both_finished_and_scores(self):
        row = match(status="finished", is_finished=True, home_score=2, away_score=1)
        output, fixed = reconcile_finished_state({"matches": [row]})
        self.assertEqual(fixed, 1)
        self.assertNotIn("settlement_pending", output["matches"][0])
        self.assertEqual(output["matches"][0]["prediction"], row["prediction"])
        incomplete = match(status="finished", is_finished=True, home_score=None, away_score=1)
        unchanged, count = reconcile_finished_state({"matches": [incomplete]})
        self.assertEqual(count, 0)
        self.assertEqual(unchanged["matches"][0], incomplete)

    def test_non_bsd_matches_are_not_modified(self):
        external = match(source="external")
        result = apply_watchdog({"matches": [external]}, {"123": event()}, now=NOW)
        self.assertEqual(result["matches"][0], external)
        self.assertEqual(result["settlement_watchdog"]["checked"], 0)


if __name__ == "__main__":
    unittest.main()
