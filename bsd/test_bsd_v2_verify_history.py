"""Regression: Telegram result validation can recover an already-sent, missing match."""
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from bsd_v2_verify_history import restore_published_matches, reference

def match(n, second=False):
    m={"id":f"bsd:{n}","source":"bsd","date":"2026-10-08",
       "event_date":"2026-10-08T18:00:00+00:00",
       "prediction":{"selection_key":"1X","odds":1.6}}
    if second:
        m["predictions"]=[m["prediction"],{"selection_key":"OVER_15","odds":1.8}]
    return m

class RecoverHistoryTests(unittest.TestCase):
    def test_invalid_ledger_ignored(self):
        self.assertIsNone(reference({"ref_id":"invalid","ref_date":"2026-10-08"}))

    def test_missing_sent_match_restored(self):
        original={"source":"bsd","matches":[match(11)]}
        ledger=[{"ref_id":"-100123:bsd:77","ref_date":"2026-10-08"}]
        snapshot={"matches":[match(77)]}
        def fake_run(cmd,**kwargs):
            return SimpleNamespace(stdout=("a"*40+"\n") if "log" in cmd else json.dumps(snapshot))
        with patch("bsd_v2_verify_history.subprocess.run",side_effect=fake_run):
            restored,count=restore_published_matches(original,ledger)
        self.assertEqual(count,1)
        self.assertEqual(len(restored["matches"]),2)
        self.assertEqual(len(original["matches"]),1)

    def test_missing_secondary_market_restored(self):
        original={"source":"bsd","matches":[match(77)]}
        ledger=[{"ref_id":"-100123:bsd:77:OVER_15","ref_date":"2026-10-08"}]
        snapshot={"matches":[match(77,second=True)]}
        def fake_run(cmd,**kwargs):
            return SimpleNamespace(stdout=("a"*40+"\n") if "log" in cmd else json.dumps(snapshot))
        with patch("bsd_v2_verify_history.subprocess.run",side_effect=fake_run):
            restored,count=restore_published_matches(original,ledger)
        self.assertEqual(count,1)
        self.assertEqual(restored["matches"][0]["predictions"][1]["selection_key"],"OVER_15")

    def test_original_market_never_overwritten(self):
        original={"source":"bsd","matches":[match(77,second=True)]}
        ledger=[{"ref_id":"-100123:bsd:77","ref_date":"2026-10-08"}]
        with patch("bsd_v2_verify_history.subprocess.run") as fake:
            restored,count=restore_published_matches(original,ledger)
        self.assertEqual(count,0)
        self.assertEqual(restored,original)
        fake.assert_not_called()

if __name__=="__main__":
    unittest.main()
