"""No-send regression for Cloudflare D1 production ledger."""
import sys,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from d1_publication_ledger import D1Ledger,D1LedgerError

def api_response(*,results=None,changes=0,status=200,success=True):
    return Mock(status_code=status,json=lambda:{
        "success":success,
        "result":[{"success":True,"results":results if results is not None else [],
                   "meta":{"changes":changes}}],
    })

class D1PublicationLedgerTests(unittest.TestCase):
    def test_claim_atomic_and_duplicate(self):
        session=Mock(post=Mock(side_effect=[api_response(changes=1),api_response(changes=0)]))
        ledger=D1Ledger(token="test",session=session)
        self.assertTrue(ledger.claim("kind","ref","2026-10-24"))
        self.assertFalse(ledger.claim("kind","ref","2026-10-24"))
        self.assertIn("INSERT OR IGNORE",session.post.call_args_list[0].kwargs["json"]["sql"])

    def test_timeout_fails_closed(self):
        from requests import Timeout
        ledger=D1Ledger(token="test",session=Mock(post=Mock(side_effect=Timeout())))
        with self.assertRaises(D1LedgerError):
            ledger.claim("kind","ref","2026-10-24")

    def test_api_failure_fails_closed(self):
        ledger=D1Ledger(token="test",session=Mock(post=Mock(return_value=api_response(status=403))))
        with self.assertRaises(D1LedgerError):
            ledger.rows("kind","2026-10-24")

    def test_rows_and_mark(self):
        session=Mock(post=Mock(side_effect=[
          api_response(results=[{"ref_id":"test"}]),
          api_response(changes=1),
        ]))
        ledger=D1Ledger(token="test",session=session)
        self.assertEqual(ledger.rows("kind","2026-10-24")[0]["ref_id"],"test")
        self.assertTrue(ledger.mark("kind","ref","2026-10-24",message_id=10))

    def test_missing_credentials(self):
        with self.assertRaises(D1LedgerError):
            D1Ledger(token="")

if __name__=="__main__":unittest.main()
