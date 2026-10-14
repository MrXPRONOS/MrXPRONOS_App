import unittest
from datetime import date, timedelta

from scripts.football_public_domain_backtest import clean_results, evaluate, league_prior


def raw(i, *, home_score=2, away_score=1, home="Arsenal FC", away="Chelsea FC"):
    day = date(2025, 1, 1) + timedelta(days=i)
    return {
        "source": "openfootball", "source_id": f"{i+1:064x}", "status": "finished",
        "match_date": day.isoformat(), "league": "Premier League",
        "home_team": home, "away_team": away,
        "home_score": home_score, "away_score": away_score,
    }


class HistoricalHoldoutTests(unittest.TestCase):
    def test_research_uses_separate_chronological_holdout(self):
        games = [raw(i, home_score=i % 3, away_score=(i+1) % 2) for i in range(80)]
        summary = evaluate(games)
        self.assertGreater(summary["evaluable_games"], 0)
        self.assertLess(summary["evaluable_games"], 80)
        self.assertTrue(summary["insufficient_evaluation_sample"])
        self.assertIn("home", str(summary["scoring_metrics"]["1x2_brier"]))
        self.assertFalse(summary["compared_to_bsd_v2"])
        self.assertFalse(summary["calibration_verified"])
        self.assertFalse(summary["production_activation_allowed"])

    def test_row_order_has_no_effect(self):
        games = [raw(i, home_score=i % 5, away_score=i % 3) for i in range(80)]
        self.assertEqual(evaluate(games), evaluate(list(reversed(games))))

    def test_same_day_outcomes_absent_from_league_prior(self):
        games = [raw(i) for i in range(50)]
        rows = clean_results(games)
        before = rows[45]["day"]
        stats = league_prior(rows, "premier league", before)
        altered = [dict(r) for r in rows]
        for r in altered:
            if r["day"] >= before:
                r["h"] = 0
                r["a"] = 30
        same = league_prior(altered, "premier league", before)
        self.assertEqual(stats, same)

    def test_conflicting_duplicate_result_is_excluded(self):
        a, b = raw(0, home_score=1), raw(0, home_score=3)
        self.assertEqual(clean_results([a, b]), [])

    def test_too_few_dates_fails_closed(self):
        report = evaluate([raw(i) for i in range(15)])
        self.assertEqual(report["test_matches"], 0)
        self.assertFalse(report["production_activation_allowed"])


if __name__ == "__main__":
    unittest.main()
