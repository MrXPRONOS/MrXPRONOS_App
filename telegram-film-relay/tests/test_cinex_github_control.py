"""Offline regression tests for GitHub-only CineX downloads."""
import unittest

from scripts.cinex_github_control import (
    eligible_links, github_enabled, queries_for_report, toggle_off_queries, valid_sequence
)


class GitHubControlTests(unittest.TestCase):
    def report(self):
        return {"libraries": [
            {"category": "action", "status": "scanned", "owner_access": "verified",
             "bot_access": "verified", "rights_attested": True,
             "media": [{"title_key": "a" * 32, "category": "action",
                        "season_number": None, "episode_number": None}]},
            {"category": "series", "status": "scanned", "owner_access": "verified",
             "bot_access": "verified", "rights_attested": True,
             "media": [
                 {"title_key": "b" * 32, "category": "series", "season_number": 1, "episode_number": 1},
                 {"title_key": "b" * 32, "category": "series", "season_number": 1, "episode_number": 2}
             ]}
        ]}

    def test_only_explicit_true_enables(self):
        for value in ("", "false", "1", "yes", "TRUEE"):
            self.assertFalse(github_enabled({"CINEX_DOWNLOADS_ENABLED": value}))
        self.assertTrue(github_enabled({"CINEX_DOWNLOADS_ENABLED": "true"}))
        self.assertTrue(github_enabled({"CINEX_DOWNLOADS_ENABLED": "TRUE"}))

    def test_complete_films_and_seasons_are_linked(self):
        self.assertEqual(eligible_links(self.report()), [
            ("action", "a" * 32, 0), ("series", "b" * 32, 1)
        ])
        queries = list(queries_for_report(self.report()))
        self.assertEqual(len(queries), 4)
        self.assertIn("enabled=0", queries[0]["sql"])
        self.assertTrue(all(len(q["params"][0]) == 24 for q in queries[1:3]))
        self.assertIn("cine_delivery_enabled", queries[-1]["sql"])

    def test_incomplete_season_is_not_enabled(self):
        r = self.report()
        r["libraries"][1]["media"].pop(0)
        self.assertEqual(eligible_links(r), [("action", "a" * 32, 0)])

    def test_duplicate_episode_is_not_enabled(self):
        r = self.report()
        r["libraries"][1]["media"].append(r["libraries"][1]["media"][0].copy())
        self.assertEqual(eligible_links(r), [("action", "a" * 32, 0)])

    def test_unverified_bot_or_rights_does_not_enable(self):
        r = self.report()
        r["libraries"][1]["bot_access"] = "not_member"
        r["libraries"][0]["rights_attested"] = False
        self.assertEqual(eligible_links(r), [])

    def test_missing_library_is_not_silently_accepted(self):
        r = self.report()
        r["libraries"].pop()
        with self.assertRaises(ValueError):
            eligible_links(r)

    def test_toggle_off_disables_flag_and_existing_links(self):
        queries = toggle_off_queries()
        self.assertEqual(len(queries), 2)
        self.assertIn("'0'", queries[0]["sql"])
        self.assertIn("enabled=0", queries[1]["sql"])

    def test_season_sequence_limit(self):
        self.assertFalse(valid_sequence("series", 1, []))
        self.assertFalse(valid_sequence("series", 1, [
            {"season_number": 1, "episode_number": 2}
        ]))
        self.assertFalse(valid_sequence("film", 0, [
            {"season_number": None, "episode_number": None}
        ] * 2))
        self.assertFalse(valid_sequence("series", 1, [
            {"season_number": 1, "episode_number": n} for n in range(1, 102)
        ]))


if __name__ == "__main__":
    unittest.main()
