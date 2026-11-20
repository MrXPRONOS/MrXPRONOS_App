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
                 {"title_key": "b" * 32, "category": "series", "season_number": 1, "episode_number": 1, "declared_total": 2},
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
            ("action", "a" * 32, 0, 0), ("series", "b" * 32, 1, 2)
        ])
        r = self.report()
        r["scanned_at"] = "2026-11-20T00:00:00Z"
        queries = list(queries_for_report(r))
        self.assertEqual(len(queries), 6)
        self.assertIn("CREATE TABLE", queries[0]["sql"])
        self.assertIn("enabled=0", queries[1]["sql"])
        self.assertIn("DELETE FROM cine_delivery_season_evidence", queries[2]["sql"])
        self.assertEqual(queries[4]["params"][3], 2)

    def test_incomplete_season_is_not_enabled(self):
        r = self.report()
        r["libraries"][1]["media"].pop(0)
        self.assertEqual(eligible_links(r), [("action", "a" * 32, 0, 0)])

    def test_duplicate_episode_is_not_enabled(self):
        r = self.report()
        r["libraries"][1]["media"].append(r["libraries"][1]["media"][0].copy())
        self.assertEqual(eligible_links(r), [("action", "a" * 32, 0, 0)])

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
        self.assertIn("CREATE TABLE", queries[0]["sql"])
        self.assertEqual(queries[1]["params"], ["0"])

    def test_missing_or_wrong_total_blocks_auto_download(self):
        r = self.report()
        r["libraries"][1]["media"][0]["declared_total"] = 10
        self.assertEqual(eligible_links(r), [("action", "a" * 32, 0, 0)])
        r["libraries"][1]["media"][0].pop("declared_total")
        self.assertEqual(eligible_links(r), [("action", "a" * 32, 0, 0)])

    def test_true_restores_master_switch_without_scan(self):
        from scripts.cinex_github_control import toggle_queries
        self.assertEqual(toggle_queries(True)[-1]["params"], ["1"])
        self.assertIn("UPDATE cine_delivery_links", toggle_queries(True)[1]["sql"])
        self.assertFalse(any("UPDATE cine_delivery_links" in q["sql"] for q in toggle_queries(False)))

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
