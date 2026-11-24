import unittest
from scripts.actu_foot_v2_release_guard import validate
from scripts.actu_foot_github_vault import VaultError

class ReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.env={"protection_rules":[{"type":"required_reviewers","reviewers":[{"type":"User"}]}],
                  "deployment_branch_policy":{"custom_branch_policies":True,"protected_branches":False},
                  "can_admins_bypass":False}
        self.policies=[{"name":"main","type":"branch"}]
    def test_verified(self):
        self.assertTrue(validate(self.env,self.policies))
    def test_missing_reviewers(self):
        self.env["protection_rules"]=[]
        with self.assertRaises(VaultError):validate(self.env,self.policies)
    def test_bypass_or_other_branch_refused(self):
        with self.assertRaises(VaultError):validate(self.env,self.policies+[{"name":"dev","type":"branch"}])
        self.env["can_admins_bypass"]=True
        with self.assertRaises(VaultError):validate(self.env,self.policies)
