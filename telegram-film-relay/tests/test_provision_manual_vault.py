"""Offline tests for owner-approved manual vault selection."""
import unittest
from scripts.provision_manual_vault import (
    CATS,MARKER,configured_chat,channel_title,Outcome
)


class OwnerVaultSetupTests(unittest.TestCase):
    def test_all_eleven_categories_have_distinct_titles(self):
        self.assertEqual(len(CATS),11)
        self.assertEqual(len(set(map(channel_title,CATS))),11)
        self.assertTrue(MARKER.startswith("MRX_"))

    def test_existing_cinex_library_is_preferred(self):
        env={"TG_PRIVATE_CHANNEL":"-1001111111111"}
        self.assertEqual(configured_chat("films",env),"-1001111111111")

    def test_manual_override_over_existing_library(self):
        env={"TG_PRIVATE_CHANNEL":"-1001111111111",
             "CINEX_MANUAL_FILMS_CHAT":"-1002222222222"}
        self.assertEqual(configured_chat("films",env),"-1002222222222")

    def test_formation_existing_private_destinations_reused(self):
        env={"FORMATION_DESTINATIONS_JSON":
             '{"general":"@formation360","business":-1001111111111,'
             '"finance":-1002222222222,"digitale":-1003333333333,'
             '"mindset":-1004444444444}'}
        self.assertEqual(configured_chat("formation_business",env),"-1001111111111")
        self.assertEqual(configured_chat("formation_mindset",env),"-1004444444444")

    def test_general_formation_uses_private_stage(self):
        env={"FORMATION_STAGE_CHAT":"-1001111111111"}
        self.assertEqual(configured_chat("formation_general",env),"-1001111111111")

    def test_absent_channel_is_missing_not_invented(self):
        self.assertEqual(configured_chat("series",{}),"")

    def test_public_channel_handle_refused(self):
        with self.assertRaises(ValueError):
            configured_chat("films",{"TG_PRIVATE_CHANNEL":"@public"})

    def test_bad_overrides_never_silently_fallback(self):
        with self.assertRaises(ValueError):
            configured_chat("films",{
                "CINEX_MANUAL_FILMS_CHAT":"not-a-private-id",
                "TG_PRIVATE_CHANNEL":"-1001111111111"})

    def test_invalid_formation_json_rejected(self):
        with self.assertRaises(ValueError):
            configured_chat("formation_business",{
                "FORMATION_DESTINATIONS_JSON":"{broken}"})

    def test_outcome_preserves_no_live_activation_in_simulation(self):
        row=Outcome("films","simulation",True,False,True,False,False)
        self.assertFalse(row.registered)


if __name__=="__main__":
    unittest.main()
