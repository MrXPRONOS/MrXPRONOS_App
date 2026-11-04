#!/usr/bin/env python3
"""Regression tests for D1-only production Shorts validation (no network calls)."""
import unittest
from scripts.settle_short_production_batches import (
    KIND, VALIDATION_KIND, canonical_ref, mark_rows, pending_rows,
    social_complete, validation_identity, validation_state,
)


class Ledger:
    def __init__(self, results=None, changes=1):
        self.results = results if results is not None else []
        self.changes = changes
        self.calls = []

    def query(self, sql, params=()):
        self.calls.append((sql, params))
        if sql.startswith("UPDATE"):
            return {"meta": {"changes": self.changes}}
        return {"results": self.results}

    def rows(self, kind, day, ref_id=None):
        self.calls.append(("rows", (kind, day, ref_id)))
        return self.results


class ValidationLedgerTests(unittest.TestCase):
    def test_pending_reads_sent_d1_rows_and_not_supabase(self):
        db = Ledger([{"id": "a", "ref_id": "morning:bsd:123",
                      "ref_date": "2026-11-04", "validation_sent": 0}])
        result = pending_rows(db)
        self.assertEqual(len(result), 1)
        sql, args = db.calls[0]
        self.assertIn("telegram_sent", sql)
        self.assertIn("delivery_status='sent'", sql)
        self.assertNotIn("validation_sent=0", sql)  # social retries after Telegram
        self.assertEqual(args[0], KIND)

    def test_legacy_and_bad_references(self):
        self.assertEqual(canonical_ref("morning:bsd:123"), ("morning", "bsd:123"))
        self.assertEqual(canonical_ref("evening:bsd:9"), ("evening", "bsd:9"))
        self.assertEqual(canonical_ref("preview:bsd:9"), (None, None))

    def test_guard_identity(self):
        self.assertEqual(validation_identity("morning", "2026-11-04"),
                         (VALIDATION_KIND, "morning:2026-11-04", "2026-11-04"))

    def test_guard_reserved_is_distinguishable_from_sent(self):
        db = Ledger([{"delivery_status": "reserved"}])
        self.assertEqual(validation_state(db, "morning", "2026-11-04"), "reserved")
        self.assertEqual(db.calls[0][1][0], VALIDATION_KIND)

    def test_social_only_complete_with_all_receipts(self):
        kinds = ["facebook", "youtube", "instagram", "threads", "bluesky"]
        db = Ledger([{"kind": "shorts_validation_social_" + platform,
                      "delivery_status": "sent",
                      "validation_details": '{"id":"provider-123"}'} for platform in kinds])
        self.assertTrue(social_complete(db, "morning", "2026-11-04"))
        db.results.pop()
        self.assertFalse(social_complete(db, "morning", "2026-11-04"))

    def test_closure_is_scoped_to_source_row(self):
        db = Ledger()
        mark_rows(db, ["some-id"], status="validated")
        sql, params = db.calls[0]
        self.assertIn("kind=?", sql)
        self.assertIn("validation_sent=0", sql)
        self.assertEqual(params, ("validated", "some-id", KIND))


if __name__ == "__main__":
    unittest.main()
