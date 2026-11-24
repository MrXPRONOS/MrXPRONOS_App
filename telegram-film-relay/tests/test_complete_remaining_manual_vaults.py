"""Offline fail-closed preflight for the nine-category provisioning operation."""
import unittest
from unittest.mock import patch
from scripts.complete_remaining_manual_vaults import (
    authorized_for_activation,category_bot_tokens,register_source,
    REMAINING,PUBLISHER_SECRET
)

class NineVaultProvisionTests(unittest.TestCase):
    def test_only_explicit_manual_media_rights_enable_source(self):
        for category in REMAINING:
            self.assertFalse(authorized_for_activation(category,{}))
            env={"CINEX_MANUAL_RIGHTS_"+category.upper()+"_ATTESTED":"true"}
            self.assertTrue(authorized_for_activation(category,env))
            env["CINEX_MANUAL_RIGHTS_"+category.upper()+"_ATTESTED"]="false"
            self.assertFalse(authorized_for_activation(category,env))

    def test_generic_publisher_rights_do_not_automatically_authorize_manual_media(self):
        self.assertFalse(authorized_for_activation(
            "formation_business",{"FORMATION_RIGHTS_ATTESTED":"true"}))
        self.assertFalse(authorized_for_activation(
            "animes",{"ANIME_RIGHTS_ATTESTED":"true"}))

    def test_every_category_requires_actual_publisher_token(self):
        self.assertEqual(len(PUBLISHER_SECRET),len(REMAINING))
        with self.assertRaises(RuntimeError):
            category_bot_tokens({})
        found=category_bot_tokens({"CINE_RADAR_BOT_TOKEN":"radar"})
        self.assertEqual(list(found),["radar"])

    def test_wrong_or_missing_chat_never_enters_d1(self):
        with self.assertRaises(ValueError):
            register_source("@public","films",bot_verified=True,explicit_rights=True)
        with self.assertRaises(ValueError):
            register_source("-1001234567890","not-category",
                            bot_verified=True,explicit_rights=True)
        with self.assertRaises(RuntimeError):
            register_source("-1001234567890","films",
                            bot_verified=False,explicit_rights=True)

    def test_new_source_remains_disabled_without_independent_rights(self):
        statements=[]
        answers=[[],[],[{"category":"films","enabled":0,"owner_approved":1,
                         "bot_access_verified":1,"rights_attested":0}]]
        def fake_query(sql,params=()):
            statements.append((sql,params))
            return answers.pop(0)
        with patch("scripts.complete_remaining_manual_vaults.d1_query",side_effect=fake_query):
            self.assertFalse(register_source(
                "-1001234567890","films",bot_verified=True,explicit_rights=False))
        self.assertEqual(statements[1][1][-2:],[0,0])
        self.assertEqual(statements[0][1],["-1001234567890"])

    def test_approved_licensed_source_can_activate_with_real_receipt(self):
        answers=[[],[],[{"category":"films","enabled":1,"owner_approved":1,
                         "bot_access_verified":1,"rights_attested":1}]]
        with patch("scripts.complete_remaining_manual_vaults.d1_query",
                   side_effect=lambda *_:answers.pop(0)):
            self.assertTrue(register_source(
                "-1001234567890","films",bot_verified=True,explicit_rights=True))

    def test_existing_d1_rights_are_preserved_without_reinventing(self):
        answers=[[{"category":"animes","rights_attested":1}],[],
                 [{"category":"animes","enabled":1,"owner_approved":1,
                   "bot_access_verified":1,"rights_attested":1}]]
        with patch("scripts.complete_remaining_manual_vaults.d1_query",
                   side_effect=lambda *_:answers.pop(0)):
            self.assertTrue(register_source(
                "-1001234567890","animes",bot_verified=True,explicit_rights=False))

    def test_channel_cannot_be_taken_from_another_category(self):
        answers=[[{"category":"action","rights_attested":1}]]
        with patch("scripts.complete_remaining_manual_vaults.d1_query",
                   side_effect=lambda *_:answers.pop(0)):
            with self.assertRaises(RuntimeError):
                register_source("-1001234567890","films",
                                bot_verified=True,explicit_rights=True)

if __name__=="__main__":
    unittest.main()
