#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest
from datetime import datetime

MODULE_FILE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "telegram_reactions_github.py"
SPEC = importlib.util.spec_from_file_location("reaction_module", MODULE_FILE)
react = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(react)


class ReactionTests(unittest.TestCase):
    def test_10_distinct_slots_and_emoji_parity(self):
        self.assertEqual(react.EXTRA_SLOTS, tuple(range(3, 13)))
        for seq in (1, 2, 3, 48):
            emojis = [react.reaction_for(seq, s) for s in react.EXTRA_SLOTS]
            self.assertEqual(emojis.count("❤️"), 5)
            self.assertEqual(emojis.count("👍"), 5)
        self.assertEqual(react.reaction_for(1, 3), "❤️")
        self.assertEqual(react.reaction_for(2, 3), "👍")

    def test_progressive_registration_uses_d1_values_and_only_verified_bots(self):
        statements = []
        class FakeD1:
            def query(self, sql):
                statements.append(sql)
                return {"results": []}

        react.prepare_jobs(FakeD1(), (3, 4, 5, 6, 7))
        self.assertEqual(len(statements), 2)
        self.assertIn("(VALUES(3),(4),(5),(6),(7))", statements[0])
        self.assertIn("(VALUES(3),(4),(5),(6),(7))", statements[1])
        self.assertIn("channel_reaction_extra_bot_activation", statements[0])
        self.assertIn("p.seq > a.start_after_seq", statements[1])
        self.assertNotIn("UNION", statements[1])

        statements.clear()
        react.prepare_jobs(FakeD1(), ())
        self.assertEqual(statements, [])
        react.prepare_jobs(FakeD1(), (8,))
        self.assertIn("(VALUES(8))", statements[0])
        self.assertIn("p.seq > a.start_after_seq", statements[1])

    def test_token_selection_skips_empty_and_duplicate(self):
        env = {
            "TELEGRAM_REACTION_BOT_03_TOKEN": "token-three",
            "TELEGRAM_REACTION_BOT_04_TOKEN": "token-three",
            "TELEGRAM_REACTION_BOT_05_TOKEN": "token-five",
        }
        self.assertEqual(react.configured_tokens(env), {3: "token-three", 5: "token-five"})

    def test_existing_two_bots_are_not_registered_as_extras(self):
        def fake(url, data, headers):
            key = "existing" if "existing" in url else "fresh"
            return 200, {"ok": True, "result": {
                "is_bot": True,
                "id": 1 if key == "existing" else 2,
                "username": "CineRadarFr_Bot" if key == "existing" else "my_reaction_bot",
            }}
        accepted = react.verify_bots({3: "existing", 4: "fresh"}, fake)
        self.assertEqual(accepted, {4: "fresh"})

    def test_missing_bots_does_not_contact_cloudflare(self):
        self.assertEqual(react.run({}, lambda *args: self.fail("External call")), 0)

    def test_transient_error_backoff(self):
        row = {"post_seq": 65, "bot_slot": 3, "attempts": 2}
        query, params = react.make_update(row, 429, {
            "ok": False, "parameters": {"retry_after": 120},
            "description": "Too Many Requests",
        })
        self.assertIn("state='retry'", query)
        self.assertEqual(params[-2:], (65, 3))
        self.assertGreaterEqual(datetime.strptime(params[0], "%Y-%m-%d %H:%M:%S"), datetime(2026, 1, 1))

    def test_permanent_rejection_is_blocked_not_retried(self):
        row = {"post_seq": 65, "bot_slot": 12, "attempts": 0}
        sql, params = react.make_update(row, 403, {"description": "Forbidden"})
        self.assertIn("state='blocked'", sql)
        self.assertEqual(params, ("telegram_http_403", 65, 12))

    def test_successful_delivery_creates_only_one_update(self):
        row = {"post_seq": 65, "bot_slot": 5, "attempts": 0}
        sql, params = react.make_update(row, 200, {"ok": True, "result": True})
        self.assertIn("state='sent'", sql)
        self.assertEqual(params, (65, 5))

    def test_d1_does_not_log_secret(self):
        calls = []
        def fake(url, data, headers):
            calls.append((url, data, headers))
            return 200, {"success": True, "result": [{"success": True, "results": []}]}
        db = react.D1("secret-token", "account-id", fake)
        db.query("SELECT 1")
        self.assertNotIn("secret-token", calls[0][0])
        self.assertIn("Bearer secret-token", calls[0][2].values())


if __name__ == "__main__":
    unittest.main()
