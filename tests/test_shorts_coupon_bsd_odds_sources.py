"""Video generator selects actual BSD V2 picks from every approved odds source."""
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/"bsd"),str(ROOT/"scripts")]
from create_short_from_telegram_coupons import _valid_match

NOW=datetime(2026,10,20,16,55,tzinfo=timezone.utc)

def example(source,estimated=False):
    return {
        "source":"bsd","id":"bsd:1234","status":"notstarted",
        "is_finished":False,"category":"vip","recommendation_eligible":True,
        "event_date":(NOW+timedelta(hours=2)).isoformat(),
        "prediction":{"selection_key":"UNDER_35","odds":1.38,
            "odds_source":source,"estimated_odds":estimated,
            "recommendation_eligible":True}
    }

class VideoSourceTests(unittest.TestCase):
    def test_all_approved_real_sources_are_included(self):
        for src in ("bsd_consensus","bsd_bookmaker","pinnwire","oddslink","moviodds","oddsharvester"):
            with self.subTest(src=src):
                self.assertTrue(_valid_match(example(src),NOW))

    def test_only_explicitly_estimated_model_quotes_are_allowed(self):
        self.assertTrue(_valid_match(example("mrxpronos_model",True),NOW))
        self.assertFalse(_valid_match(example("mrxpronos_model",False),NOW))

    def test_observation_and_past_fixture_are_excluded(self):
        r=example("pinnwire")
        r["recommendation_eligible"]=False
        self.assertFalse(_valid_match(r,NOW))
        r=example("pinnwire")
        r["event_date"]=(NOW-timedelta(hours=1)).isoformat()
        self.assertFalse(_valid_match(r,NOW))

    def test_unapproved_price_sources_are_never_included(self):
        self.assertFalse(_valid_match(example("unknown"),NOW))

if __name__=="__main__":
    unittest.main()
