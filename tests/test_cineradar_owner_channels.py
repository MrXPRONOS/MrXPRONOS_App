import unittest

from scripts.actu_foot_github_vault import VaultError
from scripts.cineradar_owner_channels import validate
from scripts.cineradar_reaction_multichannel import Runtime
from scripts.cineradar_reaction_store import LocalReactionDB

import sqlite3


class OwnerChannelsTests(unittest.TestCase):
    def sample(self):
        return {
            "version":1,"source":"personal_admin_dialogs","complete":True,
            "verified_at":"2026-11-25T18:00:00+00:00",
            "channels":["-1001111111111","-1002222222222"],
            "excluded":["-1003333333333"],
        }

    def test_valid_encrypted_owner_snapshot(self):
        included,excluded=validate(self.sample())
        self.assertEqual(len(included),2)
        self.assertEqual(len(excluded),1)
        self.assertFalse(included & excluded)

    def test_requires_full_personal_admin_scan(self):
        doc=self.sample()
        doc["complete"]=False
        with self.assertRaises(VaultError):
            validate(doc)

    def test_rejects_duplicate_or_ambiguous_channels(self):
        doc=self.sample()
        doc["channels"].append("-1003333333333")
        with self.assertRaises(VaultError):
            validate(doc)

    def test_invalid_ids_rejected(self):
        doc=self.sample()
        doc["excluded"]=["@Torrent9"]
        with self.assertRaises(VaultError):
            validate(doc)

    def test_owner_verification_filters_unowned_history(self):
        db=sqlite3.connect(":memory:")
        try:
            runner=Runtime(LocalReactionDB(db),{},
                transport=lambda *args:self.fail("network not allowed"),
                owner_inventory=({"-1001111111111"},{"-1003333333333"}))
            self.assertEqual(runner.classify("-1003333333333"),(False,False))
            self.assertEqual(runner.classify("-1002222222222"),(None,False))
        finally:
            db.close()


if __name__=="__main__":
    unittest.main()
