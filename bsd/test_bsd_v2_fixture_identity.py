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


class PipelineRegression(unittest.TestCase):
    def test_publisher_does_not_score_two_ids_for_same_fixture(self):
        from unittest.mock import patch
        from bsd_v2_publish import assemble
        from bsd_v2_core import V2History
        now = datetime(2026,11,17,10,tzinfo=timezone.utc)
        fixtures=[]
        for row in (match(654419), match(655428,"2026-11-17T16:30:00+00:00")):
            fixture={**row,"id":row["source_event_id"],"league_name":"International Friendly"}
            fixture["home_team"]={"id":2215,"name":"Kuwait"}
            fixture["away_team"]={"id":722,"name":"Honduras"}
            fixtures.append(fixture)
        with patch("bsd_v2_publish.predict_v2",side_effect=AssertionError("ambiguous fixture scored")):
            out=assemble({"source":"bsd","matches":[]},fixtures,[],now=now,
                         calibration=None,policy=None,rho=0,
                         historical_published_ids=set())
        self.assertEqual(out["matches"],[])
        self.assertEqual(out["diagnostics"]["rejections"]["cross_native_fixture_ids_quarantined"],2)

    def test_saved_upcoming_fixture_stops_new_identity(self):
        from unittest.mock import patch
        from bsd_v2_publish import assemble
        now=datetime(2026,11,17,10,tzinfo=timezone.utc)
        existing={"source":"bsd","matches":[{
            **match(654419), "date":"2026-11-17", "category":"pro",
            "recommendation_eligible":True,"signal_tier":"QUALIFIE",
            "prediction":{"selection_key":"1X","market_code":"DC_1X_FT",
                          "odds":1.2,"odds_source":"bsd_consensus",
                          "confidence":80.1,"recommendation_eligible":True}
        }]}
        fresh=match(655428,"2026-11-17T16:30:00+00:00")
        fresh["id"]=655428
        fresh["home_team"]={"id":2215,"name":"Kuwait"}
        fresh["away_team"]={"id":722,"name":"Honduras"}
        fresh["league_name"]="International Friendly"
        with patch("bsd_v2_publish.predict_v2",side_effect=AssertionError("duplicate fixture scored")):
            out=assemble(existing,[fresh],[],now=now,
                         calibration=None,policy=None,rho=0,
                         historical_published_ids={"654419"})
        self.assertEqual(out["matches"],[])
        self.assertTrue(any(r.get("reason")=="cross_native_fixture_identity_ambiguous"
                            for r in out["retired_predictions"]))

    def test_telegram_singles_and_combos_quarantine(self):
        from bsd_v2_telegram import due, combos_due
        now=datetime(2026,11,17,15,tzinfo=timezone.utc)
        rows=[match(654419),match(655428,"2026-11-17T16:30:00+00:00")]
        for row in rows:
            row.update({"category":"pro","recommendation_eligible":True,
                        "signal_tier":"QUALIFIE",
                        "prediction":{"selection_key":"1X","market_code":"DC_1X_FT",
                                      "odds":1.925,"odds_source":"bsd_consensus",
                                      "confidence":82,"recommendation_eligible":True}})
        self.assertEqual(due(rows,now),[])
        self.assertEqual(combos_due(rows,now),[])


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
