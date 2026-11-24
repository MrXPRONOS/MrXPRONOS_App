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


class WorkflowApprovalBoundaryTests(unittest.TestCase):
    def test_environment_only_for_destructive_restore(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]/".github"/"workflows"
        text=(root/"actu-foot-v2-maintenance.yml").read_text()
        normal,restore=text.split("  restore-live:\\n".replace("\\n","\n"),1)
        self.assertNotIn("environment: actu-foot-v2-maintenance",normal)
        self.assertIn("inputs.operation != 'restore'",normal)
        self.assertIn('ROTATE_ALL_ENCRYPTED_V2',normal)
        self.assertIn('recover-artifact',normal)
        self.assertIn("environment: actu-foot-v2-maintenance",restore)
        self.assertIn("inputs.operation == 'restore'",restore)
        self.assertIn("scripts.actu_foot_v2_release_guard",restore)
        for name in ("actu-foot-v2-recovery.yml","actu-foot-v3-maintenance.yml"):
            self.assertNotIn("environment: actu-foot-v2-maintenance",(root/name).read_text())
