import unittest
from scripts.healthcheck import format_ok, record

class HealthcheckTests(unittest.TestCase):
    def test_private_channel_requires_id(self):
        self.assertTrue(format_ok("-1001234567890", private=True))
        self.assertFalse(format_ok("CinéX Vidéothèque", private=True))
        self.assertFalse(format_ok("@cine_x", private=True))
    def test_public_channel_accepts_username(self):
        self.assertTrue(format_ok("@cinexfilms"))
        self.assertTrue(format_ok("-1001234567890"))
        self.assertFalse(format_ok("CinéX Public"))

if __name__ == "__main__":
    unittest.main()
