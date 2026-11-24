"""Offline safety checks for mirroring existing checkpointed rescue invites in D1."""
import hashlib
import unittest
from unittest.mock import patch
from scripts.sync_verified_rescues_to_d1 import (
    source_checkpoint_valid,register_existing_rescue
)

INVITE="https://t.me/+abcdefghijklmnopqrstuvwx"
SHA=hashlib.sha256(INVITE.encode()).hexdigest()
REC={
    "public_username":"@cinexfilms_vf",
    "public_id":-1001111111111,
    "rescue_channel_id":-1002222222222,
    "invite_sha256":SHA,
}

class RescueD1SyncTests(unittest.TestCase):
    def test_valid_checkpoint(self):
        self.assertTrue(source_checkpoint_valid("@cinexfilms_vf",REC))
    def test_missing_id_and_wrong_public_handle(self):
        self.assertFalse(source_checkpoint_valid("@wrong_films",REC))
        self.assertFalse(source_checkpoint_valid(
            "@cinexfilms_vf",{**REC,"rescue_channel_id":0}))
    def test_does_not_store_invalid_invitation(self):
        with self.assertRaises(ValueError):
            register_existing_rescue("@cinexfilms_vf",REC,"https://example.invalid")
    def test_wrong_checksum_prevents_modification(self):
        with self.assertRaises(ValueError):
            register_existing_rescue("@cinexfilms_vf",
                                     {**REC,"invite_sha256":"0"*64},INVITE)
    def test_existing_mapping_cannot_be_redirected(self):
        with patch("scripts.sync_verified_rescues_to_d1.d1_query",
                   return_value=[{"rescue_chat_id":"-1009999999999"}]):
            with self.assertRaises(RuntimeError):
                register_existing_rescue("@cinexfilms_vf",REC,INVITE)
    def test_verified_live_invite_is_written_privately_and_confirmed(self):
        outputs=[[],[],[{"rescue_chat_id":str(REC["rescue_channel_id"]),
                         "invite_url":INVITE}]]
        history=[]
        def query(sql,params):
            history.append((sql,params))
            return outputs.pop(0)
        with patch("scripts.sync_verified_rescues_to_d1.d1_query",
                   side_effect=query):
            self.assertTrue(register_existing_rescue("@cinexfilms_vf",REC,INVITE))
        self.assertEqual(len(history),3)
        self.assertTrue("INSERT INTO cine_classic_rescue_config" in history[1][0])
        self.assertEqual(history[1][1][2],INVITE)

if __name__=="__main__":
    unittest.main()
