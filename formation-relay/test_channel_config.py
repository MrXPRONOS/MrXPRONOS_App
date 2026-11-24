import os
import unittest
from unittest.mock import patch
from relay import channel_ref, read_config_json, config

class ChannelConfigTests(unittest.TestCase):
    def test_public_aliases(self):
        for value in ("@Formation360_FR","Formation360_FR","https://t.me/Formation360_FR","t.me/Formation360_FR"):
            self.assertEqual(channel_ref(value),"@formation360_fr")
    def test_private_numeric(self):
        self.assertEqual(channel_ref("-1001234567890"),-1001234567890)
        self.assertEqual(channel_ref(-1001234567890),-1001234567890)
    def test_reject_invites(self):
        for value in ("https://t.me/+abcdefgh","https://t.me/joinchat/abcdef","https://t.me/channel/123",True):
            with self.assertRaises(ValueError): channel_ref(value)
    def test_bare_public_values(self):
        with patch.dict(os.environ,{"TEST_JSON":'[{"chat":@PublicSource,"authorized":true,"credit":"Auteur @nom"}]'}):
            result=read_config_json("TEST_JSON",list)
            self.assertEqual(result[0]["chat"],"@PublicSource")
            self.assertEqual(result[0]["credit"],"Auteur @nom")
    def test_mixed_config(self):
        env={"FORMATION_SOURCES_JSON":'[{"chat":@PublicSource,"authorized":true,"credit":"Auteur Exemple"}]',
             "FORMATION_DESTINATIONS_JSON":'{"general":@Formation360_FR,"business":-1001111111111,"finance":-1002222222222,"digitale":-1003333333333,"mindset":-1004444444444}',
             "FORMATION_STAGE_CHAT":"-1005555555555","FORMATION_STATE_KEY":"x"*64}
        with patch.dict(os.environ,env):
            sources,dest,stage,key=config()
        self.assertEqual(sources[0]["chat"],"@publicsource")
        self.assertEqual(dest["general"],"@formation360_fr")
        self.assertEqual(stage,-1005555555555)
    def test_invalid_json_is_named(self):
        with patch.dict(os.environ,{"TEST_JSON":"{broken"}):
            with self.assertRaisesRegex(RuntimeError,"TEST_JSON: invalid JSON"):
                read_config_json("TEST_JSON",dict)

if __name__=="__main__": unittest.main()
