"""Deterministic, offline safety tests for the daily source index."""
import unittest
from scripts.football_daily_multisource_shadow import BudgetSession, clean_row, merge, compatible, kickoff, api_football_rows


def mk(source, home="Arsenal", away="Chelsea", when="2026-10-14T18:00:00Z", home_score=None, away_score=None, state="pre"):
    return {
        "source": source, "provider_event_id": f"{source}-1",
        "home_team": home, "away_team": away, "event_date": when,
        "state": state, "home_score": home_score, "away_score": away_score,
    }


class DailyMultisourceTests(unittest.TestCase):
    def test_two_sources_are_collapsed(self):
        fixtures, report = merge({"espn": {"rows": [mk("espn")]}, "sportscore": {"rows": [mk("sportscore")]}})
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]["source_count"], 2)
        self.assertFalse(fixtures[0]["eligible_for_model"])
        self.assertEqual(report["corroborated_by_two_or_more"], 1)

    def test_terminal_fc_suffix_can_match_with_same_kickoff(self):
        fixtures, report = merge({"espn": {"rows": [mk("espn", home="Arsenal FC", away="Chelsea FC")]}, "sportscore": {"rows": [mk("sportscore", home="Arsenal", away="Chelsea")]}})
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(report["corroborated_by_two_or_more"], 1)

    def test_near_kickoff_same_teams_is_one(self):
        fixtures, _ = merge({"espn": {"rows": [mk("espn")]}, "sportscore": {"rows": [mk("sportscore", when="2026-10-14T18:45:00Z")]}})
        self.assertEqual(len(fixtures), 1)

    def test_far_kickoff_is_not_the_same_match(self):
        fixtures, _ = merge({"espn": {"rows": [mk("espn")]}, "sportscore": {"rows": [mk("sportscore", when="2026-10-14T21:00:00Z")]}})
        self.assertEqual(len(fixtures), 2)

    def test_home_away_reversed_must_not_join(self):
        fixtures, _ = merge({"espn": {"rows": [mk("espn")]}, "sportscore": {"rows": [mk("sportscore", home="Chelsea", away="Arsenal")]}})
        self.assertEqual(len(fixtures), 2)

    def test_conflicting_finished_scores_is_quarantined(self):
        fixtures, report = merge({"espn": {"rows": [mk("espn", home_score=2, away_score=1, state="post")]}, "sportscore": {"rows": [mk("sportscore", home_score=2, away_score=2, state="post")]}})
        self.assertEqual(report["score_conflicts"], 1)
        self.assertTrue(fixtures[0]["scores_conflict"])

    def test_unsafe_naive_kickoff_not_matched(self):
        self.assertIsNone(kickoff("2026-10-14T18:00:00"))
        self.assertIsNone(clean_row(mk("espn", when="2026-10-14T18:00:00"), "espn"))

    def test_bsd_can_be_added_without_becoming_betting_model(self):
        fixtures, report = merge({"espn": {"rows": [mk("espn")]}}, bsd_events=[{
            "id": 123, "home_team": {"name": "Arsenal"},
            "away_team": {"name": "Chelsea"}, "event_date": "2026-10-14T18:00:00Z",
        }])
        self.assertEqual(report["bsd_matches_corrobated"], 1)
        self.assertTrue(fixtures[0]["matched_with_bsd"])
        self.assertFalse(report["model_input_enabled"])

    def test_api_football_bridge_proves_provenance_no_new_http(self):
        api_fixture = {"response": [{"fixture": {"id": 918, "date": "2026-10-14T18:00:00Z", "status": {"short": "NS"}}, "teams": {"home": {"id": 1, "name": "Arsenal"}, "away": {"id": 2, "name": "Chelsea"}}, "goals": {"home": None, "away": None}, "league": {"name": "Premier League"}}]}
        entries = api_football_rows(api_fixture)
        self.assertEqual(len(entries), 1)
        fixtures, report = merge({"api_football": {"rows": entries}, "espn": {"rows": [mk("espn")]}})
        self.assertEqual(report["corroborated_by_two_or_more"], 1)
        self.assertEqual(fixtures[0]["sources"]["api_football"]["id"], "918")
        self.assertFalse(fixtures[0]["eligible_for_model"])

    def test_request_host_is_allowlisted(self):
        client = BudgetSession(max_requests=1)
        with self.assertRaises(ValueError):
            client.get("http://site.api.espn.com/test")
        with self.assertRaises(ValueError):
            client.get("https://evil.example.test/")
        self.assertEqual(client.total, 0)


if __name__ == "__main__":
    unittest.main()
