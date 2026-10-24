"""Regression tests for fail-closed D1 ledger adapter; no actual posting."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from telegram_ledger_gateway import Ledger, LedgerError, oidc_token

class LedgerTests(unittest.TestCase):
    def test_atomic_claim_and_duplicate(self):
        session = Mock()
        session.post.side_effect = [
            Mock(status_code=200, json=lambda: {"claimed": True}),
            Mock(status_code=200, json=lambda: {"claimed": False}),
        ]
        ledger = Ledger(session=session, token="fake-test-token")
        self.assertTrue(ledger.claim("bsd_v2_hourly", "c:1", "2026-10-24"))
        self.assertFalse(ledger.claim("bsd_v2_hourly", "c:1", "2026-10-24"))

    def test_unauthorized_fails_closed(self):
        session = Mock(post=Mock(return_value=Mock(status_code=401)))
        with self.assertRaises(LedgerError):
            Ledger(session=session, token="invalid").claim("kind", "ref", "2026-10-24")

    def test_timeout_fails_closed(self):
        import requests
        session = Mock(post=Mock(side_effect=requests.Timeout()))
        with self.assertRaises(LedgerError):
            Ledger(session=session, token="fake").claim("kind", "ref", "2026-10-24")

    def test_missing_oidc_fails_closed(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(LedgerError):
                oidc_token()

    def test_missing_claim_result_fails_closed(self):
        session = Mock(post=Mock(return_value=Mock(status_code=200, json=lambda: {"ok": True})))
        with self.assertRaises(LedgerError):
            Ledger(session=session, token="fake").claim("kind", "ref", "2026-10-24")

    def test_release_and_mark(self):
        session = Mock()
        session.post.side_effect = [
            Mock(status_code=200, json=lambda: {"released": True}),
            Mock(status_code=200, json=lambda: {"marked": True}),
        ]
        ledger = Ledger(session=session, token="fake")
        self.assertTrue(ledger.release("kind", "ref", "2026-10-24"))
        self.assertTrue(ledger.mark("kind", "ref", "2026-10-24", message_id=10))

if __name__ == "__main__":
    unittest.main()
