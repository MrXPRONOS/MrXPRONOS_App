"""Offline tests of the experimental historical multisource merge."""
import unittest
from scripts.football_history_shadow import build, normalized


def row(source, source_id, home=1, away=0, league="Premier League", home_team="Arsenal"):
    return {
        "source": source, "source_id": source_id * 64, "season": "2024-25",
        "league": league, "match_date": "2025-01-14",
        "home_team": home_team, "away_team": "Chelsea",
        "home_score": home, "away_score": away,
    }


class HistoryTests(unittest.TestCase):
    def test_diacritic_normalization(self):
        self.assertEqual(normalized("Atlético  Madrid"), "atletico madrid")

    def test_identical_results_have_two_providers(self):
        got, report = build([row("openfootball", "a"), row("football_data", "b")])
        self.assertEqual(report["unique_fixtures"], 1)
        self.assertEqual(report["multi_source_agreement"], 1)
        self.assertEqual(got[0]["verified_by_sources"], 2)
        self.assertFalse(got[0]["for_training"])

    def test_conflicting_scores_are_quarantined(self):
        got, report = build([row("openfootball", "a", home=2), row("football_data", "b", home=1)])
        self.assertEqual(report["conflicted_fixtures"], 1)
        self.assertEqual(got[0]["status"], "source_conflict")

    def test_different_leagues_do_not_merge(self):
        got, _ = build([row("openfootball", "a"), row("football_data", "b", league="Cup")])
        self.assertEqual(len(got), 2)

    def test_safe_trailing_fc_alias_matches(self):
        a = row("openfootball", "a", home_team="Arsenal FC")
        a["away_team"] = "Chelsea FC"
        b = row("football_data", "b", home_team="Arsenal")
        result, report = build([a, b])
        self.assertEqual(report["multi_source_agreement"], 1)
        self.assertEqual(result[0]["verified_by_sources"], 2)

    def test_invalid_score_not_allowed(self):
        got, report = build([row("openfootball", "a", home=-1)])
        self.assertEqual(got, [])
        self.assertEqual(report["invalid_rows"], 1)

    def test_identical_provider_not_double_counted(self):
        got, report = build([row("openfootball", "a"), row("openfootball", "a")])
        self.assertEqual(got[0]["verified_by_sources"], 1)
        self.assertEqual(report["multi_source_agreement"], 0)


if __name__ == "__main__":
    unittest.main()
