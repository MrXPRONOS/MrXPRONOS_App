import unittest
from scripts.authorize_manual_source_rights import (
 categories_for,authorized_request,REMAINING
)

OWNER={
 "GITHUB_REPOSITORY":"MrXPRONOS/MrXPRONOS_App",
 "GITHUB_ACTOR":"MrXPRONOS",
 "GITHUB_REF":"refs/heads/main",
}

class OwnerRightsActivationTests(unittest.TestCase):
    def test_all_contains_exactly_nine_manual_categories(self):
        self.assertEqual(categories_for("all"),list(REMAINING))
        self.assertEqual(len(categories_for("all")),9)
        self.assertNotIn("series",categories_for("all"))
        self.assertNotIn("action",categories_for("all"))

    def test_single_category_must_be_known(self):
        self.assertEqual(categories_for("films"),["films"])
        with self.assertRaises(ValueError):
            categories_for("unknown")

    def test_must_have_explicit_confirmation(self):
        self.assertFalse(authorized_request(OWNER,False))
        self.assertTrue(authorized_request(OWNER,True))

    def test_cannot_activate_from_pr_or_fork(self):
        self.assertFalse(authorized_request({**OWNER,
            "GITHUB_REF":"refs/pull/17/merge"},True))
        self.assertFalse(authorized_request({**OWNER,
            "GITHUB_REPOSITORY":"other/fork"},True))

    def test_only_explicit_repository_owner_actor(self):
        self.assertFalse(authorized_request({**OWNER,"GITHUB_ACTOR":"collaborator"},True))
        self.assertFalse(authorized_request({**OWNER,"GITHUB_ACTOR":""},True))

if __name__=="__main__":
    unittest.main()
