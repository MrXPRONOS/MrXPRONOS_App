"""V2.1 regression tests: publish gates only, no model or staking changes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bsd_v2_guardrails import (
    v21_accept_priced, v21_signal_tier, v21_market_shadow,
    v21_league_market_performance, V21_DAILY_NEW_PICKS,
)

def pick(key="UNDER_35", probability=.84, odds=1.5, source="bsd_consensus"):
    return {"key":key, "conservative_probability":probability,
            "probability":probability, "bookmaker_odds":odds,
            "odds_source":source}

class V21SafetyTests(unittest.TestCase):
    def test_no_draw_market(self):
        self.assertFalse(v21_accept_priced(pick("12"))[0])

    def test_model_quotes_have_separate_confidence_gate_without_fake_value(self):
        model=pick(probability=.82, odds=1.20, source="mrxpronos_model")
        passed,reason=v21_accept_priced(model)
        self.assertTrue(passed)
        self.assertEqual(reason,"ok_model_indicative")
        self.assertEqual(v21_signal_tier(model),"INDICATIF")
        self.assertTrue(v21_accept_priced(pick(probability=.80, odds=1.20, source="mrxpronos_model"))[0])
        self.assertEqual(v21_signal_tier(pick(probability=.80, odds=1.20, source="mrxpronos_model")), "INDICATIF")
        self.assertFalse(v21_accept_priced(pick(probability=.799, odds=1.20, source="mrxpronos_model"))[0])
        self.assertFalse(v21_accept_priced(pick(probability=.82, odds=1.19, source="mrxpronos_model"))[0])
        self.assertFalse(v21_accept_priced(pick(probability=.82, odds=1.35, source="mrxpronos_model"))[0])
        self.assertFalse(v21_accept_priced(pick("OVER_15", .82, 1.20, source="mrxpronos_model"))[0])
        self.assertFalse(v21_accept_priced(pick(probability=.82, odds=1.2, source="other"))[0])

    def test_over15_strict_floor(self):
        self.assertFalse(v21_accept_priced(pick("OVER_15", .84, 1.4))[0])
        self.assertTrue(v21_accept_priced(pick("OVER_15", .87, 1.4))[0])

    def test_real_price_edge(self):
        self.assertFalse(v21_accept_priced(pick(probability=.80, odds=1.2))[0])
        self.assertTrue(v21_accept_priced(pick(probability=.84, odds=1.5))[0])

    def test_tiers(self):
        self.assertEqual(v21_signal_tier(pick(probability=.84)), "PREMIUM")
        self.assertEqual(v21_signal_tier(pick(probability=.79)), "QUALIFIE")
        self.assertEqual(v21_signal_tier(pick(probability=.70)), "OBSERVATION")

    def test_market_circuit_breaker(self):
        tracker={"by_selection":{"OVER_15":{"n":100,"wins":65,"sum_pred":80}}}
        self.assertTrue(v21_market_shadow(tracker,"OVER_15"))
        self.assertFalse(v21_accept_priced(pick("OVER_15",.9),tracker)[0])

    def test_small_sample_protected(self):
        tracker={"by_selection":{"UNDER_35":{"n":10,"wins":0,"sum_pred":8}}}
        self.assertFalse(v21_market_shadow(tracker,"UNDER_35"))

    def test_league_market_risk(self):
        bucket={"n":50,"wins":30,"sum_pred":40}
        self.assertFalse(v21_accept_priced(pick(),league_market=bucket)[0])

    def test_league_history(self):
        rows=[{"league":"A","is_finished":True,"verified_prediction":False,
               "prediction":{"selection_key":"OVER_15","confidence":80}}]
        self.assertEqual(v21_league_market_performance(rows)["A|OVER_15"]["n"],1)

    def test_daily_limit_configured(self):
        self.assertEqual(V21_DAILY_NEW_PICKS,10)

if __name__=="__main__":
    unittest.main()
