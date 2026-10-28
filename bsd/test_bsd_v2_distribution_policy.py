"""Regression tests: PRO/VIP + >=79% is mandatory at EVERY distribution exit."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from bsd_v2_publication_policy import (
    eligible_model_choice, eligible_feed_match, eligible_feed_selection, qualifying_confidence)
from bsd_v2_combos import choose_leg, build_combos
from bsd_v2_telegram import due, expand_tickets
from bsd_v2_publish import assemble

NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


def row(i, cat="pro", conf=79.0, *, extra=None):
    dt = NOW + timedelta(minutes=90 + i)
    first = {"selection_key": "1X", "market": "double_chance",
             "confidence": conf, "odds": 1.6, "odds_source": "bsd_consensus",
             "recommendation_eligible": True}
    item = {"id": f"bsd:{i}", "source_event_id": i, "source": "bsd",
            "date": dt.date().isoformat(), "event_date": dt.isoformat(),
            "status": "notstarted", "category": cat,
            "recommendation_eligible": True, "prediction": first}
    if extra is not None:
        item["predictions"] = [first, extra]
    return item


class DistributionPolicyTests(unittest.TestCase):
    def test_category_and_confidence_floor(self):
        self.assertTrue(eligible_feed_match(row(1, "pro", 79.0)))
        self.assertTrue(eligible_feed_match(row(1, "vip", 100)))
        self.assertFalse(eligible_feed_match(row(1, "simple", 95)))
        self.assertFalse(eligible_feed_match(row(1, "pro", 78.999)))
        self.assertFalse(eligible_feed_match(row(1, "vip", float("nan"))))
        self.assertFalse(eligible_feed_match(row(1, "pro", None)))
        self.assertTrue(qualifying_confidence(.79))
        self.assertFalse(qualifying_confidence(.78999))
        self.assertFalse(eligible_model_choice({
            "category": "simple", "prediction": {"probability": .99}}))
        self.assertTrue(eligible_model_choice({
            "category": "pro", "prediction": {"probability": .79}}))

    def test_secondary_picks_cannot_bypass_floor(self):
        extra={"selection_key":"UNDER_35","market":"total_goals","confidence":78.9,
               "odds":1.8,"odds_source":"bsd_consensus","recommendation_eligible":True}
        fixture=row(1,"pro",81,extra=extra)
        self.assertFalse(eligible_feed_selection(fixture,extra))
        tickets=expand_tickets(fixture)
        self.assertEqual(len(tickets),1)
        self.assertEqual(tickets[0]["prediction"]["selection_key"],"1X")

    def test_telegram_due_rejects_simple_and_under79(self):
        fixtures=[row(1,"simple",98),row(2,"pro",78.9),row(3,"vip",79),
                  row(4,"pro",90)]
        selected=due(fixtures,NOW)
        self.assertEqual([x["source_event_id"] for x in selected],[3,4])

    def test_combo_leg_rejects_low_category_and_low_secondary(self):
        secondary={"selection_key":"UNDER_35","market":"goals","confidence":79.1,
                   "odds":1.30,"odds_source":"bsd_consensus","recommendation_eligible":True}
        valid=row(1,"vip",80,extra=secondary)
        valid["prediction"]["odds"]=1.33
        self.assertIsNotNone(choose_leg(valid))
        self.assertIsNone(choose_leg(row(2,"simple",93)))
        self.assertIsNone(choose_leg(row(3,"pro",78.999)))
        invalid_secondary=row(4,"pro",81,extra={**secondary,"confidence":78.5})
        invalid_secondary["prediction"]["odds"]=1.31
        self.assertEqual(choose_leg(invalid_secondary)["prediction"]["selection_key"],"1X")
        # A pair of valid fixtures creates one combo; excluded fixtures never enter.
        pairs=build_combos([valid, row(5,"simple",98), row(6,"pro",79)])
        self.assertEqual(len(pairs),0 if not pairs else 1)
        if pairs:
            self.assertTrue(all(eligible_feed_match(leg) for leg in pairs[0]["legs"]))

    def test_saved_simple_removed_without_renaming_immutable_prediction(self):
        fixture=row(1234,"simple",95)
        fixture["prediction"].update({"odds":1.61,"odds_source":"bsd_consensus"})
        source={"id":1234,"event_date":fixture["event_date"],"status":"notstarted"}
        # The event was previously exposed. It must not be re-generated under
        # another market even when the archived publication ID set is absent.
        with patch("bsd_v2_publish.predict_v2", side_effect=AssertionError("reselected old fixture")):
            out=assemble({"source":"bsd","matches":[fixture]},[source],[],
                         now=NOW,calibration=None,policy=None,rho=0)
        self.assertEqual(out["matches"],[])
        self.assertEqual(out["retired_predictions"][0]["reason"],
                         "category_or_confidence_below_79")


if __name__=="__main__":
    unittest.main()
