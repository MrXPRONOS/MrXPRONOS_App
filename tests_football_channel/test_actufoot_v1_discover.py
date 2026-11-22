import unittest
from types import SimpleNamespace
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from actufoot_v1_discover import role_for_channel, ROLE_SIGNATURES

class TestRoles(unittest.TestCase):
    def test_every_role(self):
        for role,words in ROLE_SIGNATURES.items():
            self.assertEqual(role_for_channel(SimpleNamespace(username=words[0],title="Autre")),role)
    def test_titles_and_symbols(self):
        self.assertEqual(role_for_channel(SimpleNamespace(username="xcode",title="🌍🔥 Foot Afrique Actu ⚽")),"africa")
        self.assertEqual(role_for_channel(SimpleNamespace(username="xcode",title="⚡ Foot Flash 24/7")),"flash")
    def test_collision_rejected(self):
        with self.assertRaises(ValueError):
            role_for_channel(SimpleNamespace(username="xcode",title="Mercato Ligue 1"))
if __name__=="__main__":
    unittest.main()
