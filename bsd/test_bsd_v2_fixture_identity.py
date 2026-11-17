"""Regression: Kuwait–Honduras duplicate native IDs and odds precedence."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bsd_v2_fixture_identity import ambiguous_fixture_ids, quarantine_ambiguous
from bsd_v2_estimated_odds import estimated_quote, price_selected_market, ESTIMATED_SOURCE


def match(eid, time="2026-11-17T16:00:00+00:00", league=31, away=722):
    return {
        "id":"bsd:" + str(eid), "source_event_id":eid, "event_date":time,
        "home_team":"Kuwait", "away_team":"Honduras",
        "home_team_id":2215, "away_team_id":away, "league_id":league,
        "source":"bsd", "status":"notstarted",
    }


class IdentityRegression(unittest.TestCase):
    def test_real_incident_quarantines_both_native_ids(self):
        rows=[match(654419),match(655428,"2026-11-17T16:30:00+00:00")]
        safe, blocked=quarantine_ambiguous(rows)
        self.assertEqual(safe,[])
        self.assertEqual(blocked,{"654419","655428"})

    def test_different_day_league_or_team_are_not_collisions(self):
        rows=[match(1),match(2,"2026-11-18T16:30:00+00:00"),
              match(3,league=30),match(4,away=733)]
        self.assertEqual(ambiguous_fixture_ids(rows),set())

    def test_same_native_id_is_not_a_cross_id_collision(self):
        self.assertEqual(ambiguous_fixture_ids([match(1),match(1)]),set())

    def test_midnight_and_transitive_drift(self):
        rows=[match(1,"2026-11-17T23:55:00+00:00"),
              match(2,"2026-11-18T00:20:00+00:00"),
              match(3,"2026-11-18T01:35:00+00:00")]
        self.assertEqual(ambiguous_fixture_ids(rows),{"1","2","3"})

    def test_name_fallback_when_ids_missing(self):
        a=match(1);b=match(2)
        for item in (a,b):
            item.pop("home_team_id");item.pop("away_team_id")
        self.assertEqual(ambiguous_fixture_ids([a,b]),{"1","2"})


class OddsPrecedenceRegression(unittest.TestCase):
    def setUp(self):
        self.selection={"key":"1X","internal_market_code":"DC_1X_FT",
                        "market_code":"DC_1X_FT","probability":.76,
                        "conservative_probability":.73}
        self.now=datetime(2026,11,17,tzinfo=timezone.utc)

    def test_bsd_price_takes_priority_no_theoretical_double_price(self):
        quotes={"DC_1X_FT":{"odds":1.925,"origin":"bsd_consensus",
                              "updated_at":self.now.isoformat()}}
        pick=price_selected_market(self.selection,quotes,now=self.now)
        self.assertEqual(pick["bookmaker_odds"],1.925)
        self.assertEqual(pick["odds_source"],"bsd_consensus")
        self.assertIs(pick["estimated_odds"],False)
        self.assertIsNone(estimated_quote(self.selection,quotes,now=self.now))

    def test_invalid_bsd_quote_cannot_be_replaced_by_an_estimate(self):
        quotes={"DC_1X_FT":{"odds":None,"origin":"bsd_consensus"}}
        self.assertIsNone(price_selected_market(self.selection,quotes,now=self.now))
        self.assertIsNone(estimated_quote(self.selection,quotes,now=self.now))

    def test_missing_quote_allows_explicit_estimate(self):
        pick=price_selected_market(self.selection,{},now=self.now)
        self.assertEqual(pick["odds_source"],ESTIMATED_SOURCE)
        self.assertTrue(pick["estimated_odds"])


if __name__=="__main__":
    unittest.main()
