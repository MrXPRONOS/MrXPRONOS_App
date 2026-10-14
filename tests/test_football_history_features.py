"""Strict no-future-information tests for the shadow form features."""
import unittest
from scripts.football_history_features import eligible_history, form, features


def historic(i, day, h="Arsenal FC", a="Chelsea FC", home_score=2, away_score=1, status="multi_source_agreement"):
    return {"date": day, "home_team": h, "away_team": a, "competition": "Premier League",
            "home_score": home_score, "away_score": away_score, "status": status,
            "verified_by_sources": 2, "providers": [{"source": "openfootball"}, {"source": "football_data"}]}


def fixture(when="2025-03-01T15:00:00+00:00", league="Premier League"):
    return {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": when, "league_labels": [league]}


class HistoricalFeaturesTests(unittest.TestCase):
    def test_requires_two_sources(self):
        self.assertFalse(eligible_history(historic(0, "2025-02-01", status="confirmed_single_source")))

    def test_prior_five_but_not_same_day(self):
        rows = [historic(i, f"2025-02-{i+1:02d}") for i in range(5)]
        out, report = features([fixture()], rows)
        self.assertEqual(report["features_complete"], 1)
        self.assertEqual(out[0]["home_form"]["sample_matches"], 5)
        self.assertEqual(out[0]["home_form"]["points_per_match"], 3)
        self.assertIsNone(out[0]["calibrated_probability"])
        rows.append(historic(5, "2025-03-01", home_score=0, away_score=9))
        out2, _ = features([fixture()], rows)
        self.assertEqual(out, out2)

    def test_future_not_available(self):
        rows = [historic(i, "2025-04-01") for i in range(8)]
        out, report = features([fixture()], rows)
        self.assertEqual(out, [])
        self.assertEqual(report["coverage_reasons"]["insufficient_verified_history"], 1)

    def test_ambiguous_league_prevents_features(self):
        rows = [historic(i, f"2025-02-{i+1:02d}") for i in range(6)]
        f = fixture()
        f["league_labels"] = ["Premier League", "Bundesliga"]
        out, report = features([f], rows)
        self.assertEqual(out, [])
        self.assertEqual(report["coverage_reasons"]["ambiguous_or_missing_league"], 1)

    def test_competition_alias_is_explicit(self):
        rows = [historic(i, f"2025-02-{i+1:02d}") for i in range(5)]
        out, _ = features([fixture(league="English Premier League")], rows)
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
