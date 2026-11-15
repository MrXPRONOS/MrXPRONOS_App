#!/usr/bin/env python3
"""Regression tests for D1-only production Shorts validation (no network calls)."""
import unittest
import os
import requests
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import scripts.settle_short_production_batches as settlement
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


    def test_legacy_sent_groups_do_not_consume_render_slots_or_repost(self):
        rows = [
            {"id": "new", "ref_id": "morning:bsd:900", "ref_date": "2026-11-14", "validation_sent": 0},
            {"id": "old_13", "ref_id": "morning:bsd:901", "ref_date": "2026-11-13", "validation_sent": 1},
            {"id": "old_08", "ref_id": "morning:bsd:902", "ref_date": "2026-11-08", "validation_sent": 1},
        ]
        ledger = Mock()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(sys, "argv", ["settle_short_production_batches.py", "--no-send", "--work-dir", tmp]), \
                patch.object(settlement, "D1Ledger", return_value=ledger), \
                patch.object(settlement, "pending_rows", return_value=rows), \
                patch.object(settlement, "restore_matches", return_value={"bsd:900": {"id": "bsd:900"}}), \
                patch.object(settlement, "validation_state", side_effect=lambda _ledger, _slot, day:
                             "sent" if day <= "2026-11-13" else None), \
                patch.object(settlement, "social_complete", return_value=False), \
                patch.object(settlement, "official_events_for_day", return_value=({"900": {"id": "900"}}, 1)) as fetch, \
                patch.object(settlement, "_leg_verdict", return_value=(True, 2, 1)), \
                patch.object(settlement, "render_exact_validated_cards", return_value=(["card.png"], "pack")), \
                patch.object(settlement, "build_video") as render, \
                patch.object(settlement, "send_video") as send:
            settlement.main()
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
        statuses = {group["target"]: group["status"] for group in manifest["groups"]}
        self.assertEqual(statuses["2026-11-14"], "ready")
        self.assertEqual(statuses["2026-11-13"], "legacy_social_reconciliation_required")
        self.assertEqual(statuses["2026-11-08"], "legacy_social_reconciliation_required")
        self.assertEqual(len(manifest["published"]), 1)
        self.assertEqual(manifest["published"][0]["target"], "2026-11-14")
        render.assert_called_once()
        fetch.assert_called_once_with("2026-11-14")
        send.assert_not_called()
        ledger.claim.assert_not_called()
        ledger.mark.assert_not_called()


    def test_unconfirmed_provider_response_never_returns_a_delivery_id(self):
        session = Mock()
        session.post.return_value.json.return_value = {"ok": True, "result": {}}
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "validated.mp4"
            video.write_bytes(b"fake clip")
            with self.assertRaisesRegex(RuntimeError, "without a valid message_id"):
                settlement.send_video(session, "fake-token", "@fake-channel",
                                      video, "2026-11-14", "morning", "test")

    def test_telegram_504_is_quarantined_without_marking_sent_or_retrying(self):
        rows = [{"id": "new", "ref_id": "morning:bsd:900",
                 "ref_date": "2026-11-14", "validation_sent": 0}]
        ledger = Mock()
        ledger.claim.return_value = True
        ledger.set_status.return_value = True
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake",
                                        "TELEGRAM_CHAT_ID": "@fake"}),
                patch.object(sys, "argv", ["settle_short_production_batches.py",
                                           "--work-dir", tmp]),
                patch.object(settlement, "D1Ledger", return_value=ledger),
                patch.object(settlement, "pending_rows", return_value=rows),
                patch.object(settlement, "restore_matches",
                             return_value={"bsd:900": {"id": "bsd:900"}}),
                patch.object(settlement, "validation_state", return_value=None),
                patch.object(settlement, "official_events_for_day",
                             return_value=({"900": {"id": "900"}}, 1)),
                patch.object(settlement, "_leg_verdict",
                             return_value=(True, 2, 1)),
                patch.object(settlement, "render_exact_validated_cards",
                             return_value=(["card.png"], "pack")),
                patch.object(settlement, "build_video"),
                patch.object(settlement, "send_video",
                             side_effect=requests.HTTPError("504 Gateway Timeout")) as send,
            ):
                with self.assertRaisesRegex(RuntimeError,
                                            "SHORTS_VALIDATION_TELEGRAM_UNCERTAIN"):
                    settlement.main()
        ledger.claim.assert_called_once_with("shorts_video_validation",
                                             "morning:2026-11-14", "2026-11-14")
        ledger.set_status.assert_called_once_with("shorts_video_validation",
                                                  "morning:2026-11-14",
                                                  "2026-11-14", "uncertain")
        ledger.mark.assert_not_called()
        send.assert_called_once()

    def test_existing_uncertain_claim_never_sends_or_renders(self):
        rows = [{"id": "new", "ref_id": "morning:bsd:900",
                 "ref_date": "2026-11-14", "validation_sent": 0}]
        ledger = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(sys, "argv", ["settle_short_production_batches.py",
                                           "--no-send", "--work-dir", tmp]),
                patch.object(settlement, "D1Ledger", return_value=ledger),
                patch.object(settlement, "pending_rows", return_value=rows),
                patch.object(settlement, "restore_matches", return_value={}),
                patch.object(settlement, "validation_state",
                             return_value="uncertain"),
                patch.object(settlement, "official_events_for_day") as fetch,
                patch.object(settlement, "build_video") as render,
                patch.object(settlement, "send_video") as send,
            ):
                settlement.main()
                manifest = json.loads((Path(tmp) / "manifest.json").read_text())
        self.assertEqual(manifest["groups"][0]["status"],
                         "telegram_delivery_review_required")
        self.assertEqual(manifest["groups"][0]["delivery_status"], "uncertain")
        fetch.assert_not_called()
        render.assert_not_called()
        send.assert_not_called()
        ledger.claim.assert_not_called()

if __name__ == "__main__":
    unittest.main()
