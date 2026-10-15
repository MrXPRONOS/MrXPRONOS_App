import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.football_publication_transaction_canary import (
    choose_historical_specimen,immutable_key,apply_local_transaction,
    run_real_historical_canary,
)
from bsd.bsd_v2_audit import update_ledger

def authentic_published_sample():
    p={
        "selection_key":"UNDER_35","market":"over_under_35",
        "odds":1.6,"confidence":80.0,"odds_source":"bsd_consensus",
    }
    m={
        "id":"bsd:1234","source_event_id":1234,"source":"bsd",
        "event_date":"2026-10-11T18:00:00+00:00",
        "date":"2026-10-11","status":"finished",
        "home_team":"Fixture Home","away_team":"Fixture Away",
        "league":"Example competition","prediction":p,
    }
    feed={"source":"bsd","matches":[m],"performance_tracker":{}}
    ledger=update_ledger({},[m],observed_at="2026-10-11T19:00:00+00:00")
    return feed,ledger

class OfflinePublicationCanaryTests(unittest.TestCase):
    def test_true_logged_specimen_can_replay_price_and_rollback(self):
        feed,ledger=authentic_published_sample()
        original=(deepcopy(feed),deepcopy(ledger))
        report=run_real_historical_canary(feed,ledger)
        self.assertEqual(report["transaction_rollbacks_byte_identical"],2)
        self.assertEqual(report["duplicate_dispatches_suppressed"],2)
        self.assertEqual(report["simulated_transport_dispatches"],1)
        self.assertEqual(report["external_telegram_messages_sent"],0)
        self.assertFalse(report["new_qualified_prematch_selection_observed"])
        self.assertFalse(report["production_publication_authorized"])
        self.assertTrue(report["historic_selection_authentic_from_feed_and_ledger"])
        self.assertEqual((feed,ledger),original)
        self.assertNotIn("Fixture Home",str(report))
        self.assertNotIn("1234",str(report))

    def test_receipt_survives_sequential_attempts_without_duplicate_send(self):
        feed,ledger=authentic_published_sample()
        row,choice=choose_historical_specimen(feed,ledger)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            first=apply_local_transaction(root,row)
            initial=(root/"ACTIVE.json").read_bytes()
            second=apply_local_transaction(root,row)
            self.assertTrue(first["transaction_committed"])
            self.assertFalse(second["transaction_committed"])
            self.assertEqual(second["deduplicated"],1)
            self.assertEqual(initial,(root/"ACTIVE.json").read_bytes())
            for phase in ("after_prepare","after_activation"):
                other=deepcopy(row)
                other["source_event_id"]=1235
                other["id"]="bsd:1235"
                with self.assertRaisesRegex(RuntimeError,"Injected failure"):
                    apply_local_transaction(root,other,fault=phase)
                self.assertEqual(initial,(root/"ACTIVE.json").read_bytes())

    def test_existing_ledger_identity_and_original_market_must_match(self):
        feed,ledger=authentic_published_sample()
        wrong=deepcopy(feed)
        wrong["matches"][0]["prediction"]["selection_key"]="OVER_35"
        with self.assertRaises(ValueError):
            choose_historical_specimen(wrong,ledger)
        wrong=deepcopy(feed)
        wrong["matches"][0]["prediction"]["odds"]=3.5
        with self.assertRaises(ValueError):
            choose_historical_specimen(wrong,ledger)
        wrong=deepcopy(feed)
        wrong["matches"][0]["prediction"]["odds_source"]="mrxpronos_model"
        with self.assertRaises(ValueError):
            choose_historical_specimen(wrong,ledger)
        wrong=deepcopy(feed)
        wrong["matches"][0]["prediction"]["confidence"]=10
        with self.assertRaises(ValueError):
            choose_historical_specimen(wrong,ledger)

    def test_empty_or_untrusted_ledger_fails_closed(self):
        feed,ledger=authentic_published_sample()
        with self.assertRaises(ValueError):
            choose_historical_specimen(feed,{})
        ledger["entries"]=[]
        with self.assertRaises(ValueError):
            run_real_historical_canary(feed,ledger)

    def test_atomic_pointer_rolls_back_even_if_first_activation_fails(self):
        feed,ledger=authentic_published_sample()
        row,_=choose_historical_specimen(feed,ledger)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for step in ("after_prepare","after_activation"):
                with self.assertRaises(RuntimeError):
                    apply_local_transaction(root,row,fault=step)
                self.assertFalse((root/"ACTIVE.json").exists())
            self.assertEqual(apply_local_transaction(root,row)["reserved_new"],1)
            self.assertEqual(apply_local_transaction(root,row)["deduplicated"],1)

if __name__=="__main__":
    unittest.main()
