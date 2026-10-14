import unittest
from scripts.football_alias_candidates import propose


def rec(source, home, away, score=(2, 1), day="2025-01-04"):
    return {
        "source": source, "source_id": ("a" if source == "openfootball" else "b") * 64,
        "season": "2024-25", "league": "Premier League",
        "match_date": day, "home_team": home, "away_team": away,
        "home_score": score[0], "away_score": score[1],
    }


class AliasCandidatesTest(unittest.TestCase):
    def test_proposes_but_never_applies_alias(self):
        report = propose([rec("openfootball", "Manchester United FC", "Liverpool FC"), rec("football_data", "Man United", "Liverpool")])
        self.assertEqual(report["distinct_alias_proposals"], 1)
        self.assertEqual(report["automatic_aliases_applied"], 0)
        self.assertFalse(report["proposals"][0]["approved"])

    def test_no_proposal_with_different_scores(self):
        report = propose([rec("openfootball", "Manchester United FC", "Liverpool FC"), rec("football_data", "Man United", "Liverpool", score=(0, 2))])
        self.assertEqual(report["distinct_alias_proposals"], 0)

    def test_exact_name_pair_needs_no_alias(self):
        report = propose([rec("openfootball", "Arsenal FC", "Liverpool FC"), rec("football_data", "Arsenal", "Liverpool")])
        self.assertEqual(report["distinct_alias_proposals"], 0)


if __name__ == "__main__":
    unittest.main()
