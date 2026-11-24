"""Never allow a missing/expired session to evade Telegram's cooldown."""
import unittest
from datetime import datetime,timezone,timedelta
from scripts.probe_personal_session_for_fallback import classify_credentials

class PersonalFallbackProbeTests(unittest.TestCase):
    def test_missing_session_without_cooldown(self):
        self.assertEqual(classify_credentials({}),"session_missing")
    def test_cooldown_overrides_missing_session(self):
        until=(datetime.now(timezone.utc)+timedelta(hours=3)).isoformat()
        self.assertEqual(classify_credentials({
            "TG_PERSONAL_COOLDOWN_UNTIL_UTC":until}),"flood_wait")
    def test_broken_cooldown_format_is_not_permission_to_fallback(self):
        self.assertEqual(classify_credentials({
            "TG_PERSONAL_COOLDOWN_UNTIL_UTC":"not-a-timestamp"}),"unknown")
    def test_configured_session_must_still_be_verified_live(self):
        self.assertIsNone(classify_credentials({
            "TG_STRING_SESSION":"dummy","TG_API_ID":"12345","TG_API_HASH":"test"
        }))
    def test_past_cooldown_does_not_permanently_lock(self):
        until=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
        self.assertEqual(classify_credentials({
            "TG_PERSONAL_COOLDOWN_UNTIL_UTC":until}),"session_missing")

if __name__=="__main__":
    unittest.main()
