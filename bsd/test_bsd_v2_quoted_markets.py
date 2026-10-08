"""Sélections BSD V2 : la cote est obligatoire AVANT le choix du marché."""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from bsd_v2_core import choose_market, markets_from_matrix, score_matrix
from bsd_v2_publish import assemble, MIN_BSD_ODDS, EXCLUDED_SELECTIONS
from bsd_v2_telegram import due


class PricedSelectionTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,8,10,tzinfo=timezone.utc)
        self.fixture={"id":17,"event_date":(self.now+timedelta(hours=4)).isoformat(),
                      "status":"notstarted","home_team_id":1,"away_team_id":2,
                      "home_team":"Equipe A","away_team":"Equipe B","league_id":99}
        self.history=[{"id":i,"event_date":(self.now-timedelta(days=20-i)).isoformat(),
                       "status":"finished","home_team_id":1,"away_team_id":2,
                       "home_score":1,"away_score":0,"league_id":99} for i in range(1,14)]

    def test_banned_market_and_all_unpriced_selections_excluded(self):
        markets=markets_from_matrix(score_matrix(1.4,1.0))
        quotes={m.market_code:1.50 for m in markets}
        selected,ranks=choose_market(markets,odds_by_market=quotes,require_odds=True,
                                     excluded_keys=EXCLUDED_SELECTIONS)
        self.assertNotEqual(selected["candidate"].key,"UNDER_45")
        self.assertTrue(all(r["candidate"].key!="UNDER_45" for r in ranks))

    def test_below_120_and_missing_quote_never_picked(self):
        markets=markets_from_matrix(score_matrix(1.6,.9))
        allowed=next(m for m in markets if m.key=="OVER_15")
        choice,ranks=choose_market(markets,odds_by_market={allowed.market_code:1.19},
                                   require_odds=True,min_probability=.1)
        self.assertIsNone(choice)
        # A minimum 1.20 price is necessary, not sufficient: the conservative
        # probability must also beat break-even by at least 2.5 points.
        choice,ranks=choose_market(markets,odds_by_market={allowed.market_code:1.20},
                                   require_odds=True,min_probability=.1)
        self.assertIsNone(choice)
        from dataclasses import replace
        confident=replace(allowed,probability=.90)
        choice,ranks=choose_market([confident],odds_by_market={allowed.market_code:1.20},
                                   require_odds=True,min_probability=.1)
        self.assertEqual(choice["candidate"].key,"OVER_15")
        self.assertEqual(choice["bookmaker_odds"],1.20)

    def test_no_quote_skips_match_before_publication(self):
        out=assemble({},[self.fixture],self.history,now=self.now,
            calibration=None,policy=None,rho=0,
            odds_fetcher=lambda *a: ({},{}),max_odds_requests=2)
        self.assertEqual(out["matches"],[])
        self.assertEqual(out["diagnostics"]["rejections"]["no_qualified_bsd_odds"],1)

    def test_market_selection_uses_verifiable_bsd_price(self):
        from bsd_v2_core import markets_from_matrix
        candidate=next(c for c in markets_from_matrix(score_matrix(1.7,1.0)) if c.key=="OVER_15")
        quotes={candidate.market_code:{"odds":1.25,"origin":"bsd_consensus",
                                       "updated_at":self.now.isoformat()}}
        class DummyPolicy:
            def check_fixture(self, features):return None
            def check_market(self, choice):return None
        out=assemble({},[self.fixture],self.history,now=self.now,
            calibration=None,policy=DummyPolicy(),rho=0,
            odds_fetcher=lambda *a:(quotes,{}),max_odds_requests=2)
        self.assertTrue(all(m["prediction"]["odds"]>=1.20 and
                            m["prediction"]["selection_key"]!="UNDER_45"
                            for m in out["matches"]))
        if out["matches"]:
            self.assertEqual(out["matches"][0]["prediction"]["odds_source"],"bsd_consensus")

    def test_expired_unquoted_feed_entries_are_removed(self):
        ko=(self.now+timedelta(hours=3)).isoformat()
        past=(self.now-timedelta(days=1)).isoformat()
        old={"source":"bsd","matches":[
            {"id":"bsd:1","source":"bsd","source_event_id":1,
             "event_date":ko,"status":"notstarted",
             "prediction":{"selection_key":"UNDER_45","odds":None}},
            {"id":"bsd:2","source":"bsd","source_event_id":2,
             "event_date":past,"status":"finished",
             "prediction":{"selection_key":"1X","odds":1.18,"odds_source":"bsd_consensus"}},
        ]}
        out=assemble(old,[],self.history,now=self.now,calibration=None,policy=None,rho=0)
        self.assertEqual(out["matches"],[])


if __name__=="__main__":
    unittest.main()
