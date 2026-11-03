"""Safety regression: 1.40-2.00 ANALYSIS STREAM never becomes Pro/VIP."""
import math
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch

from bsd_markets import Candidate
from bsd_v2_market_range_analyses import (
    honest_indicative_price,build_market_range_analyses,
    MIN_ANALYSIS_ODDS,MAX_ANALYSIS_ODDS,MAX_PER_FIXTURE
)
NOW=datetime(2026,11,3,12,tzinfo=timezone.utc)

class StubPolicy:
    def check_fixture(self,features):return None
    def check_market(self,row):return None
class StubCalibrator:
    def score(self,c):return (.0,c.probability,100)
def make_c(key,family,probability):
    return Candidate(key,key.lower(),"yes" if key.endswith("YES") else "over",
                     key.replace("_"," "),family,probability,
                     2.5 if key=="OVER_25" else 3.5 if key=="UNDER_35" else None)

class IndicativeAnalysisTests(unittest.TestCase):
    def test_honest_60_percent_price_is_not_120(self):
        self.assertEqual(honest_indicative_price(.60),1.572)
        self.assertEqual(honest_indicative_price(.50),1.887)
        self.assertIsNone(honest_indicative_price(.80))
        self.assertEqual(honest_indicative_price(.70),1.348)
        self.assertIsNone(honest_indicative_price(.73))
    def test_bounds_invalid_and_no_invented_price(self):
        for p in (None,0.,1.,-1.,float("nan"),float("inf"),.2,.99):
            with self.subTest(p=p):
                self.assertIsNone(honest_indicative_price(p))
        self.assertIsNone(honest_indicative_price(.60,margin=-.1))
        self.assertIsNone(honest_indicative_price(.60,margin=.21))
    def test_fixture_analysis_keeps_btts_and_a_different_family(self):
        f={"id":123,"status":"notstarted",
           "event_date":(NOW+timedelta(hours=4)).isoformat(),
           "home_team":"A","away_team":"B","league_name":"L"}
        candidates=[
            make_c("BTTS_YES","btts",.60),
            make_c("BTTS_NO","btts",.40),
            make_c("OVER_25","goals",.55),
            make_c("UNDER_35","goals",.57),
        ]
        with patch("bsd_v2_market_range_analyses.estimate_goals",return_value=(
            {"home":1.4,"away":1.2},"ok")),patch(
            "bsd_v2_market_range_analyses._considered_candidates",
            return_value=candidates):
            rows,stats=build_market_range_analyses(
                [f],object(),now=NOW,rho=0,calibration=StubCalibrator(),
                quality_policy=StubPolicy())
        self.assertEqual(len(rows),2)
        self.assertTrue(any(r["selection_key"]=="BTTS_YES" for r in rows))
        self.assertEqual(len({r["market_family"] for r in rows}),2)
        self.assertEqual(stats["analyses_count"],2)
        for r in rows:
            self.assertTrue(MIN_ANALYSIS_ODDS<r["odds"]<=MAX_ANALYSIS_ODDS)
            self.assertIn(r["display_tier"],("safe","cotes15"))
            self.assertTrue(r["analysis_telegram_opt_in"])
            self.assertEqual(r["odds_source"],"mrxpronos_model")
            self.assertEqual(r["overround_assumption"],.06)
            self.assertTrue(r["analysis_only"])
            self.assertFalse(r["recommendation_eligible"])
            self.assertFalse(r["prediction_eligible"])
            self.assertTrue(r["do_not_send_to_telegram"])
            self.assertTrue(r["not_an_executable_bookmaker_quote"])
            self.assertNotEqual(r["category"],"pro")
            self.assertNotEqual(r["category"],"vip")
    def test_no_outdated_or_finished_games(self):
        f={"id":123,"status":"finished",
           "event_date":(NOW+timedelta(hours=4)).isoformat()}
        rows,stats=build_market_range_analyses([f],object(),now=NOW,
            rho=0,calibration=None,quality_policy=StubPolicy())
        self.assertEqual(rows,[])
        self.assertEqual(stats["analyses_count"],0)
        with self.assertRaises(ValueError):
            build_market_range_analyses([],object(),now=NOW,rho=0,
                calibration=None,quality_policy=StubPolicy(),max_per_day=0)
if __name__=="__main__":unittest.main()
