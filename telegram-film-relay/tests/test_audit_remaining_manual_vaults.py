import unittest
from types import SimpleNamespace
from scripts.audit_remaining_manual_vaults import (
    REMAINING,AuditRow,configured_id,find_private,report
)

def peer(id,title,username=None,broadcast=True):
    return SimpleNamespace(id=id,title=title,username=username,broadcast=broadcast)

class InventoryNineTests(unittest.TestCase):
    def test_nine_remaining_categories(self):
        self.assertEqual(len(REMAINING),9)
        self.assertNotIn("action",REMAINING)
        self.assertNotIn("series",REMAINING)
    def test_existing_category_library_is_preferred(self):
        self.assertEqual(configured_id("films",{
            "TG_PRIVATE_CHANNEL":"-1001234567890"}),"-1001234567890")
    def test_formation_specialty_never_assumes_public_destination(self):
        self.assertEqual(configured_id("formation_business",{
            "FORMATION_DESTINATIONS_JSON":'{"business":-1001234567890}'}),"")
    def test_manual_private_override(self):
        self.assertEqual(configured_id("formation_business",{
            "CINEX_MANUAL_FORMATION_BUSINESS_CHAT":"-1001234567890"}),
                         "-1001234567890")
    def test_configured_peer_must_exist_in_owner_dialogs(self):
        code,found=find_private([peer(-1001234567890,"Source")],"films",
                                "-1009999999999",lambda p:p.id)
        self.assertEqual(code,"configured_not_in_owner_dialogs")
        self.assertIsNone(found)
    def test_unconfigured_exact_named_vault(self):
        code,found=find_private([peer(-1001234567890,"MRX — Stock manuel Films")],
                                "films","",lambda p:p.id)
        self.assertEqual(code,"found")
        self.assertEqual(found.id,-1001234567890)
    def test_duplicate_vault_name_must_not_create(self):
        c,found=find_private([
            peer(-1001234567890,"MRX — Stock manuel Films"),
            peer(-1002222222222,"MRX — Stock manuel Films")],
            "films","",lambda p:p.id)
        self.assertEqual(c,"ambiguous_duplicate_title")
        self.assertIsNone(found)
    def test_public_channel_cannot_be_a_source(self):
        code,found=find_private([peer(-1001234567890,"Broadcast",
                                      username="public_videos")],
                                "films","-1001234567890",lambda p:p.id)
        self.assertEqual(code,"not_private_broadcast")
        self.assertIsNone(found)
    def test_readiness_is_not_inferred_from_existing_channel(self):
        s=report([AuditRow("films","found","creator_verified",
                           "bot_missing_admin","verified",False)])
        self.assertEqual(s["ready"],0)
        self.assertEqual(s["needs_review"],1)

if __name__=="__main__":
    unittest.main()
