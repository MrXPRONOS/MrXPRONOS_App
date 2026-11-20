"""Ensure the Telegram bot promotion is only to exact owner-configured channels."""
import unittest
from types import SimpleNamespace
from scripts.grant_cineradar_access import needs_update, BOT_USERNAME
from scripts.catalog_stage12 import configured_targets

class CinERadarAccessTests(unittest.TestCase):
    def test_bot_public_identity_is_fixed(self):
        self.assertEqual(BOT_USERNAME,"CineRadarFr_Bot")

    def test_admin_needs_no_repromotion(self):
        self.assertFalse(needs_update(SimpleNamespace(is_admin=True,is_creator=False)))
        self.assertFalse(needs_update(SimpleNamespace(is_admin=False,is_creator=True)))
        self.assertTrue(needs_update(None))

    def test_only_current_var_ids_are_accepted(self):
        env={"SERIES_PRIVATE_CHANNEL":"-1004455497484",
             "ACTION_PRIVATE_CHANNEL":"-1004462439590",
             "SERIES_RIGHTS_ATTESTED":"true","ACTION_RIGHTS_ATTESTED":"true"}
        self.assertEqual(len(configured_targets(env)),2)
        self.assertEqual([x["private_chat_id"] for x in configured_targets(env)],
                         ["-1004455497484","-1004462439590"])

if __name__=="__main__":
    unittest.main()
