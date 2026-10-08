"""Régressions BSD V2 avancées : calibration, qualité, odds, shadow."""
import unittest
from datetime import datetime, timezone
from bsd_v2_core import V2History, score_matrix, markets_from_matrix
from bsd_v2_policies import V2Calibration, V2QualityPolicy
from bsd_v2_odds import parse_odds
from bsd_v2_shadow import generate_shadow


class V2AdvancedTests(unittest.TestCase):
    def test_calibration_roundtrip_and_prior(self):
        item=markets_from_matrix(score_matrix(1.4,1.1))[0]
        cal=V2Calibration()
        self.assertAlmostEqual(cal.score(item)[1],item.probability)
        for _ in range(60):cal.observe(item,0)
        clone=V2Calibration.from_dict(cal.to_dict())
        self.assertAlmostEqual(clone.score(item)[1],cal.score(item)[1])
        self.assertLess(clone.score(item)[1],item.probability)

    def test_quality_policy_flags_overconfidence(self):
        policy=V2QualityPolicy({"UNDER_45":{"n":60,"wins":30,"sum_pred":48.}})
        item=next(x for x in markets_from_matrix(score_matrix(1.1,1.0)) if x.key=="UNDER_45")
        self.assertEqual(policy.check_market({"candidate":item}),"quality_market_overconfident")
        self.assertEqual(V2QualityPolicy.from_dict(policy.to_dict()).min_league,20)

    def test_quality_bad_league(self):
        p=V2QualityPolicy()
        info={"league_samples":5,"home_recent_matches":10,"away_recent_matches":10,
              "max_last_match_age_days":2}
        self.assertEqual(p.check_fixture(info),"quality_league_history")

    def test_quotes_require_correct_event_and_pre_match_timestamp(self):
        kickoff=datetime(2026,10,9,20,tzinfo=timezone.utc)
        now=datetime(2026,10,9,10,tzinfo=timezone.utc)
        items=[
            {"event_id":999,"market":"1x2","outcome":"HOME","period":"FT",
             "bookmaker_slug":"consensus","decimal_odds":"1.90","updated_at":"2026-10-09T09:00:00Z"},
            {"event_id":222,"market":"1x2","outcome":"HOME","period":"FT",
             "bookmaker_slug":"consensus","decimal_odds":"1.80","updated_at":"2026-10-09T09:00:00Z"},
            {"event_id":222,"market":"1x2","outcome":"DRAW","period":"1H",
             "bookmaker_slug":"consensus","decimal_odds":"3.00","updated_at":"2026-10-09T09:00:00Z"},
            {"event_id":222,"market":"btts","outcome":"yes","period":"FT",
             "bookmaker_slug":"consensus","decimal_odds":"1.75","updated_at":"2026-10-09T21:00:00Z"},
        ]
        result,skips=parse_odds(items,222,kickoff=kickoff,fetched_at=now)
        self.assertEqual(len(result),1)
        self.assertEqual(result["1X2_HOME_FT"]["odds"],1.80)
        self.assertIsNone(result["1X2_1_FT"]["bookmaker_selection_code"])

    def test_empty_shadow_no_publish(self):
        result=generate_shadow([],[],V2Calibration(),V2QualityPolicy(),0.,
            now=datetime(2026,10,8,5,tzinfo=timezone.utc))
        self.assertEqual(result["matches"],[])
        self.assertFalse(result["published"])
        self.assertEqual(len(result["fingerprint_sha256"]),64)


if __name__=="__main__":
    unittest.main()
