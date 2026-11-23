"""Offline acceptance tests: no Telegram write operation is performed."""
import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from film_relay.cinex_v4_policy import MAIN_RELAY_HANDLES
from scripts.cinex_lot1_readonly_audit import audit

FLAGS = {
    "CINEX_ARCHIVE_ENABLED": "true",
    "CINEX_ARCHIVE_DELETE_APPROVED": "true",
    "CINEX_RIGHTS_VERIFIED": "true",
}
PAIRS = [(name, handle, -1001111111111) for name, handle in (
    ("films", "@cinexfilms_vf"), ("series", "@seriesvf_cinex"),
    ("desir", "@cinexdesirfr"), ("comedie", "@cinexcomediefr"),
    ("anime", "@cinexanimefr"), ("action", "@filmsaction2026vf"),
)]


class Lot1ReadOnlyAuditTests(unittest.TestCase):
    def evaluate(self, *, ready=7, truncated=False, flags=None):
        rows = [{"category": name, "errors": 0, "history_truncated": truncated}
                for name, _, _ in PAIRS]
        if flags is None:
            flags = FLAGS
        with (patch.dict(os.environ, flags, clear=True),
              patch("scripts.cinex_lot1_readonly_audit.read_state",
                    return_value={"channels": {name: {} for name in MAIN_RELAY_HANDLES}}),
              patch("scripts.cinex_lot1_readonly_audit.category_targets",
                    return_value=PAIRS),
              patch("scripts.cinex_lot1_readonly_audit.hydrate",
                    new=AsyncMock(return_value={"ready": ready, "missing": 7 - ready})),
              patch("scripts.cinex_lot1_readonly_audit.execute",
                    new=AsyncMock(return_value=rows))):
            return asyncio.run(audit(history=4000))

    def test_success_requires_all_seven_and_six(self):
        self.assertEqual(self.evaluate(), 0)

    def test_missing_invitation_blocks_completion(self):
        self.assertEqual(self.evaluate(ready=6), 1)

    def test_missing_deletion_approval_blocks_completion(self):
        flags = dict(FLAGS)
        flags["CINEX_ARCHIVE_DELETE_APPROVED"] = "false"
        self.assertEqual(self.evaluate(flags=flags), 1)

    def test_truncated_history_blocks_completion(self):
        self.assertEqual(self.evaluate(truncated=True), 1)


if __name__ == "__main__":
    unittest.main()
