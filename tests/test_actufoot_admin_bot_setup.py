import os,sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from actufoot_admin_bot_setup import clean_secret_candidates,compact,expected_rights,full_rights
from telethon.tl.types import ChatAdminRights

TOKEN_A="12345678:"+"a"*35
TOKEN_B="12345679:"+"b"*35
class AuditTest(unittest.TestCase):
    def test_unicode_folder_name(self):
        self.assertEqual(compact("⚽ Actu Foot"),"actufoot")
        self.assertEqual(compact("ACTU-FOOT"),"actufoot")
    def test_numbered_reaction_secrets_included_and_deduplicated(self):
        found,n=clean_secret_candidates({"FOOTBALL_NEWS_BOT_TOKEN":TOKEN_A,
          "TELEGRAM_REACTION_BOT_03_TOKEN":TOKEN_B,"CANAL_BOT_TOKEN":TOKEN_A})
        self.assertEqual(len(found),2)
        self.assertEqual(n,3)
    def test_json_reaction_bot_secret(self):
        found,n=clean_secret_candidates({"TELEGRAM_REACTION_BOTS_JSON":json.dumps({"100":TOKEN_B})})
        self.assertEqual(n,1)
        self.assertEqual(len(found),1)
    def test_admin_rights_no_promotions(self):
        rights,flags=full_rights()
        self.assertFalse(rights.add_admins)
        self.assertTrue(rights.post_messages)
        self.assertTrue(rights.delete_messages)
        self.assertTrue(rights.edit_messages)
        self.assertTrue(expected_rights(rights,flags))
    def test_no_grant_on_mismatch(self):
        rights,flags=full_rights()
        self.assertFalse(expected_rights(ChatAdminRights(add_admins=True),flags))

if __name__=="__main__":unittest.main()
