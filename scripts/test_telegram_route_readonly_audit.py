"""Offline safety regressions: audit does not publish or reveal private IDs."""
from __future__ import annotations

import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from scripts import telegram_route_readonly_audit as audit


class SafeRouteAuditTests(unittest.TestCase):
    def test_scrub_untrusted_telegram_error(self):
        self.assertEqual(audit.safe_reason(RuntimeError("private ID -100123, token AAA")),
                         "RuntimeError")
        # Only the existing hardened Bot error wrapper is allowed to provide detail.
        self.assertIn("chat not found", audit.safe_reason(
            RuntimeError("Bot API getChat [stage]: 400 - chat not found")))

    def test_formation_stage_not_found_does_not_abort_other_destinations(self):
        stage = -1001234567890
        destinations = {
            "general": "@public_course", "business": -1001111111111,
            "finance": -1002222222222, "digitale": -1003333333333,
            "mindset": -1004444444444,
        }
        def bot_call(method, *, context, **params):
            if method == "getMe":
                return {"id": 12345}
            if method == "getChat":
                if context == "stage":
                    raise RuntimeError("Bot API getChat [stage]: 400 - chat not found")
                is_general = context == "general"
                return {"id": 42, "type": "channel",
                        **({"username": "public_course"} if is_general else {})}
            if method == "getChatMember":
                return {"status": "administrator", "can_post_messages": True}
            raise AssertionError("unexpected method " + method)

        fake_bot = Mock()
        fake_bot.call.side_effect = bot_call
        output = StringIO()
        with patch.dict(os.environ, {
            "FORMATION_DESTINATIONS_JSON": __import__("json").dumps(destinations),
            "FORMATION_STAGE_CHAT": str(stage), "FORMATION_BOT_TOKEN": "dummy",
        }), patch.object(audit, "Bot", return_value=fake_bot), redirect_stdout(output):
            self.assertFalse(audit.audit_formation())
        text = output.getvalue()
        self.assertIn("FORMATION_ROUTE_FAIL category=stage operation=getChat", text)
        self.assertEqual(text.count("FORMATION_ROUTE_OK"), 5)
        for sensitive in (str(stage), "dummy"):
            self.assertNotIn(sensitive, text)
        self.assertEqual(fake_bot.call.call_count, 12)  # 1 auth + 5*2 + 1 failing stage

    def test_crypto_multichannel_continues_after_legacy_failure(self):
        bot = Mock(spec=audit.multi.Telegram)
        bot.assert_correct_bot.return_value = 123
        bot.verify_destination.return_value = -100123
        bot.get.side_effect = RuntimeError("Telegram private ID -100999")
        target = {"chat_id": "@crypto_test", "key": "public-name-irrelevant"}
        db = Mock()
        db.targets.return_value = [target]
        output = StringIO()
        with patch.dict(os.environ, {"ACTU_CRYPTO_CHAT_ID": "@legacy_channel"}):
            with patch.object(audit.multi, "Supabase", return_value=db), \
                 patch.object(audit.multi, "Telegram", return_value=bot), \
                 redirect_stdout(output):
                self.assertFalse(audit.audit_multichannel())
        text = output.getvalue()
        self.assertIn("CRYPTO_MULTICHANNEL_TARGET_OK index=1", text)
        self.assertIn("CRYPTO_LEGACY_ROUTE_FAIL operation=getChat", text)
        for sensitive in ("-100999", "@legacy_channel"):
            self.assertNotIn(sensitive, text)
        bot.verify_destination.assert_called_once_with(target, 123)

    def test_all_components_are_checked_after_a_failed_formation(self):
        output = StringIO()
        with patch.object(audit, "audit_formation", return_value=False) as formation, \
             patch.object(audit, "audit_premium", return_value=True) as premium, \
             patch.object(audit, "audit_multichannel", return_value=True) as world, \
             redirect_stdout(output):
            self.assertEqual(audit.main(), 1)
        formation.assert_called_once()
        premium.assert_called_once()
        world.assert_called_once()
        self.assertIn("formation=FAILED premium=OK multichannel=OK", output.getvalue())


if __name__ == "__main__":
    unittest.main()
