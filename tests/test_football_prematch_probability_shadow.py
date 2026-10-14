import math
import unittest
from scripts.football_prematch_probability_shadow import baseline, predict_research, chronological_backtest


M = {"home_goals_for": 1.8, "home_goals_against": 1.1, "away_goals_for": 1.2, "away_goals_against": 1.6}


class ResearchProbabilityTests(unittest.TestCase):
    def test_1x2_sum_is_one(self):
        p = baseline(M)
        q = p["probabilities_uncalibrated"]
        self.assertAlmostEqual(q["home"] + q["draw"] + q["away"], 1, places=5)
        self.assertAlmostEqual(q["over_2_5"] + q["under_2_5"], 1, places=5)
        self.assertAlmostEqual(q["btts_yes"] + q["btts_no"], 1, places=5)
        self.assertFalse(p["calibration_verified"])
        self.assertFalse(p["betting_signal"])

    def test_safe_abstain_on_missing_goals(self):
        routed = [{"fixture_key": "abc", "families": {"goals": {"status": "missing", "reason": "no_valid_stats"}}}]
        rows, report = predict_research(routed)
        self.assertEqual(rows, [])
        self.assertEqual(report["unanalysable_reasons"]["no_valid_stats"], 1)
        self.assertFalse(report["ready_for_betting"])

    def test_provenance_on_profile(self):
        routed = [{
            "fixture_key": "abc",
            "families": {"goals": {"status": "ready", "provider": "espn", "provider_fixture_id": "9",
                                     "samples": {"home": 7, "away": 8}, "metrics": M}},
        }]
        rows, report = predict_research(routed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["statistics_provider"], "espn")
        self.assertTrue(rows[0]["not_validated_for_publication"])
        self.assertEqual(report["telegram_posts"], 0)

    def test_chronological_not_enough_sample_is_explicit(self):
        historic = [{"date": "2025-01-01", "status": "multi_source_agreement",
                     "verified_by_sources": 2, "competition": "Premier League",
                     "home_team": "Arsenal", "away_team": "Chelsea", "home_score": 2, "away_score": 0}]
        report = chronological_backtest(historic)
        self.assertEqual(report["chronologically_evaluable_games"], 0)
        self.assertFalse(report["production_activation_allowed"])
        self.assertIsNone(report["one_x_two_logloss"])

    def test_no_future_match_can_contribute_backtest_metrics(self):
        history = []
        for i in range(5):
            history.append({"date": f"2025-01-{i+1:02d}", "status": "multi_source_agreement",
                            "verified_by_sources": 2, "competition": "Premier League",
                            "home_team": "Arsenal", "away_team": "Chelsea", "home_score": 1, "away_score": 0})
        target = {"date": "2025-02-01", "status": "multi_source_agreement",
                  "verified_by_sources": 2, "competition": "Premier League",
                  "home_team": "Arsenal", "away_team": "Chelsea", "home_score": 2, "away_score": 1}
        past = chronological_backtest(history + [target])
        extended = chronological_backtest(history + [target, {"date": "2025-03-01", "status": "multi_source_agreement",
                  "verified_by_sources": 2, "competition": "Premier League",
                  "home_team": "Arsenal", "away_team": "Chelsea", "home_score": 4, "away_score": 4}])
        self.assertEqual(past["chronologically_evaluable_games"], 1)
        self.assertEqual(extended["chronologically_evaluable_games"], 2)


if __name__ == "__main__":
    unittest.main()
