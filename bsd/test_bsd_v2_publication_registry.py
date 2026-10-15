"""Append-only deduplication contract for BSD publication (offline)."""
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from bsd_v2_publish import assemble,historical_publication_ids
from bsd_v2_audit import update_ledger

TIME=datetime(2026,10,15,10,tzinfo=timezone.utc)

def sample():
    return {
        "id":"bsd:1234","source":"bsd","source_event_id":1234,
        "event_date":"2026-10-16T19:00:00+00:00",
        "home_team":"Fixture Home","away_team":"Fixture Away",
        "prediction":{"selection_key":"UNDER_35","odds":1.6,
                      "odds_source":"bsd_consensus","confidence":80.0},
    }

def fixture(ident=1234):
    return {"id":ident,"event_date":"2026-10-16T19:00:00+00:00",
            "status":"notstarted",
            "home_team":{"id":111,"name":"Fixture Home"},
            "away_team":{"id":112,"name":"Fixture Away"},
            "league_id":8,"league_name":"Premier League"}

class HistoricalPublicationGuardTests(unittest.TestCase):
    def test_republication_blocked_after_feed_retirement(self):
        ledger=update_ledger({},[sample()],observed_at="2026-10-15T08:00:00+00:00")
        ids=historical_publication_ids(ledger,{"source":"bsd","matches":[]})
        self.assertEqual(ids,{"1234"})
        # Event is no longer displayed, but reappears in the incoming source.
        with patch("bsd_v2_publish.predict_v2",side_effect=AssertionError("reposted retired fixture")):
            result=assemble({"source":"bsd","matches":[]},[fixture()],[],now=TIME,
                calibration=None,policy=None,rho=0,odds_fetcher=None,
                historical_published_ids=ids)
        self.assertEqual(result["matches"],[])
        self.assertEqual(result["diagnostics"]["v21_new_picks"],0)
        self.assertEqual(result["diagnostics"]["fixture_details"],[])

    def test_bad_historic_registry_fails_closed(self):
        with self.assertRaises(ValueError):
            historical_publication_ids({},{"source":"bsd","matches":[]})
        ledger=update_ledger({},[sample()],observed_at="2026-10-15T08:00:00+00:00")
        ledger["entries"][0]["original_pick"]["selection_key"]=None
        with self.assertRaises(ValueError):
            historical_publication_ids(ledger,{"source":"bsd","matches":[]})

    def test_current_feed_cannot_mutate_first_published_market(self):
        ledger=update_ledger({},[sample()],observed_at="2026-10-15T08:00:00+00:00")
        modified=sample()
        modified["prediction"]["selection_key"]="OVER_35"
        with self.assertRaisesRegex(ValueError,"immutable"):
            historical_publication_ids(ledger,{"source":"bsd","matches":[modified]})
        self.assertEqual(historical_publication_ids(ledger,{"source":"bsd","matches":[sample()]}),{"1234"})

    def test_new_event_remains_candidate_and_existing_id_stays_frozen(self):
        with patch("bsd_v2_publish.predict_v2",return_value=(None,"no_qualified_market")) as pick:
            out=assemble({"source":"bsd","matches":[]},[fixture(1234),fixture(5678)],[],
                now=TIME,calibration=None,policy=None,rho=0,odds_fetcher=None,
                historical_published_ids={"1234"})
        self.assertEqual(pick.call_count,1)
        self.assertEqual(out["diagnostics"]["fixture_details"][0]["event_id"],"5678")
        self.assertEqual(out["diagnostics"]["v21_new_picks"],0)

    def test_bad_published_ids_cannot_disable_guard(self):
        with self.assertRaises(ValueError):
            assemble({"source":"bsd","matches":[]},[],[],now=TIME,
                     calibration=None,policy=None,rho=0,historical_published_ids={"invalid-id"})

if __name__=="__main__":
    unittest.main()
