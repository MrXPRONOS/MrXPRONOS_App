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
    def test_legacy_workflow_is_permanently_disabled_and_replaced(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        legacy = (root / ".github/workflows/telegram-reactions-github.yml").read_text(encoding="utf-8")
        current = (root / ".github/workflows/cineradar-reactions-github-only.yml").read_text(encoding="utf-8")
        self.assertEqual(legacy.count("if: ${{ false }}"), 2)
        self.assertIn("Permanently disabled", legacy)
        self.assertIn("python -m scripts.cineradar_reactions_github_only", current)
        self.assertNotIn("CLOUDFLARE", current)
        self.assertIn("contents: write", current)

    def test_10_distinct_slots_and_emoji_parity(self):
        self.assertEqual(tuple(react.EXTRA_SLOTS[:10]), tuple(range(3, 13)))
        self.assertIn(13, react.EXTRA_SLOTS)
        self.assertIn(99, react.EXTRA_SLOTS)
        self.assertIn(1000, react.EXTRA_SLOTS)
        for seq in (1, 2, 3, 48):
            emojis = [react.reaction_for(seq, s) for s in react.EXTRA_SLOTS[:10]]
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

    def test_due_jobs_uses_full_capacity_on_newest_posts(self):
        seen = []
        class FakeDB:
            def query(self, sql, params):
                seen.append((sql, params))
                return {"results": [
                    {"post_seq": 199, "bot_slot": 13},
                    {"post_seq": 199, "bot_slot": 14},
                    {"post_seq": 198, "bot_slot": 13},
                ]}
        selected = react.due_jobs(FakeDB(), (3, 13, 14))
        self.assertEqual([(r["post_seq"],r["bot_slot"]) for r in selected],
                         [(199,13), (199,14), (198,13)])
        self.assertEqual(len(seen), 1)
        self.assertIn("ORDER BY j.post_seq DESC,j.bot_slot ASC LIMIT ?", seen[0][0])
        self.assertNotIn("ORDER BY j.post_seq ASC", seen[0][0])
        self.assertEqual(seen[0][1], (3,13,14,react.MAX_JOBS_PER_RUN))

    def test_no_configured_bot_means_no_query(self):
        class FakeDB:
            def query(self, sql, params):
                self.fail("unexpected database call")
        self.assertEqual(react.due_jobs(FakeDB(), ()), [])

    def test_enqueue_newest_posts_first(self):
        statements = []
        class FakeDB:
            def query(self, sql):
                statements.append(sql)
                return {"results": []}
        react.prepare_jobs(FakeDB(), (3,13))
        self.assertIn("ORDER BY p.seq DESC", statements[1])

    def test_diagnose_primary_channel_admin_access_without_posting(self):
        import contextlib
        import io
        calls = []
        class FakeDB:
            def query(self, sql):
                self_sql = str(sql)
                self_assert = self_sql.startswith("SELECT kind,chat_id")
                if not self_assert:
                    raise AssertionError("Unexpected audit SQL")
                return {"results": [
                    {"kind": "films", "chat_id": "-100123"},
                    {"kind": "series", "chat_id": "-100124"},
                ]}
        def transport(url, data, headers):
            method=url.rsplit("/",1)[-1]
            calls.append(method)
            if method == "getMe":
                return 200, {"ok":True,"result":{"id":1234,"is_bot":True,"username":"demo_bot"}}
            if data["chat_id"] == "-100123":
                return 200, {"ok":True,"result":{"status":"administrator"}}
            return 400, {"ok":False,"description":"Bad Request: chat not found"}
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            react.audit_primary_channel_access(FakeDB(), {13:"test-token"}, transport)
        self.assertIn("channel=films status=admin",output.getvalue())
        self.assertIn("channel=series status=not_accessible",output.getvalue())
        self.assertEqual(calls,["getMe","getChatMember","getChatMember"])
        self.assertNotIn("test-token", output.getvalue())

    def test_token_selection_skips_empty_and_duplicate(self):
        env = {
            "TELEGRAM_REACTION_BOT_03_TOKEN": "token-three",
            "TELEGRAM_REACTION_BOT_04_TOKEN": "token-three",
            "TELEGRAM_REACTION_BOT_05_TOKEN": "token-five",
        }
        self.assertEqual(react.configured_tokens(env), {3: "token-three", 5: "token-five"})

    def test_extended_numbered_and_bundled_tokens(self):
        env = {
            "TELEGRAM_REACTION_BOT_03_TOKEN": "three",
            "TELEGRAM_REACTION_BOT_13_TOKEN": "thirteen",
            "TELEGRAM_REACTION_BOT_16_TOKEN": "sixteen",
            "TELEGRAM_REACTION_BOT_99_TOKEN": "ninety-nine",
            "TELEGRAM_REACTION_BOTS_JSON": '{"100":"one-hundred","101":"one-hundred-one"}',
        }
        self.assertEqual(react.configured_tokens(env), {
            3: "three", 13: "thirteen", 16: "sixteen",
            99: "ninety-nine", 100: "one-hundred", 101: "one-hundred-one",
        })

    def test_bundle_duplicate_and_bad_json_fail_closed(self):
        env = {
            "TELEGRAM_REACTION_BOT_13_TOKEN": "first",
            "TELEGRAM_REACTION_BOTS_JSON": '{"13":"ignored","100":"first","101":"new"}',
        }
        self.assertEqual(react.configured_tokens(env), {13: "first", 101: "new"})
        with self.assertRaises(react.APIError):
            react.configured_tokens({"TELEGRAM_REACTION_BOTS_JSON": "not-json"})

    def test_safe_telegram_error_classification(self):
        self.assertEqual(react.safe_reaction_error(
            400, {"description": "Bad Request: message to react not found"}
        ), "telegram_http_400:message_not_found")
        self.assertEqual(react.safe_reaction_error(
            400, {"description": "Bad Request: chat not found"}
        ), "telegram_http_400:chat_not_found")
        self.assertEqual(react.safe_reaction_error(
            400, {"description": "Bot token SENSITIVEVALUE"}
        ), "telegram_http_400:unknown")

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

    def test_slot16_reusing_existing_bot_never_duplicates_identity(self):
        env = {"TELEGRAM_REACTION_BOT_03_TOKEN": "main-key",
               "TELEGRAM_REACTION_BOT_16_TOKEN": "main-key"}
        self.assertEqual(react.configured_tokens(env), {3: "main-key"})
        def fake(url, data, headers):
            return 200, {"ok": True, "result": {
                "id": 123, "is_bot": True, "username": "CineRadarFr_Bot"}}
        self.assertEqual(react.verify_bots({16: "main-key"}, fake), {})

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

    def test_temporary_channel_access_loss_is_retryable(self):
        for response in (
            {"description": "Bad Request: chat not found"},
            {"description": "Bad Request: not enough rights"},
            {"description": "Bad Request: bot is not a member"},
        ):
            row = {"post_seq": 72, "bot_slot": 13, "attempts": 1}
            sql, params = react.make_update(row, 400, response)
            self.assertIn("state='retry'", sql)
            self.assertEqual(params[-2:], (72, 13))
            seconds = (datetime.strptime(params[0], "%Y-%m-%d %H:%M:%S")
                       - datetime.utcnow()).total_seconds()
            self.assertGreater(seconds, 43000)
            self.assertLess(seconds, 43500)

    def test_missing_slots_between_03_and_16_are_not_required(self):
        self.assertEqual(react.configured_tokens({
            "TELEGRAM_REACTION_BOT_03_TOKEN": "token-three",
            "TELEGRAM_REACTION_BOT_13_TOKEN": "token-thirteen",
            "TELEGRAM_REACTION_BOT_16_TOKEN": "token-sixteen",
        }), {3: "token-three", 13: "token-thirteen", 16: "token-sixteen"})

    def test_permanent_rejection_is_blocked_not_retried(self):
        row = {"post_seq": 65, "bot_slot": 12, "attempts": 0}
        sql, params = react.make_update(row, 403, {"description": "Forbidden"})
        self.assertIn("state='blocked'", sql)
        self.assertEqual(params, ("telegram_http_403:forbidden", 65, 12))

    def test_successful_delivery_creates_only_one_update(self):
        row = {"post_seq": 65, "bot_slot": 5, "attempts": 0}
        sql, params = react.make_update(row, 200, {"ok": True, "result": True})
        self.assertIn("state='sent'", sql)
        self.assertEqual(params, (65, 5))


    def test_primary_verification_requires_both_expected_owners(self):
        def fake(url, data, headers):
            token = url.split("/bot", 1)[1].split("/")[0]
            names = {"radar-key": "CineRadarFr_Bot", "canal-key": "mrxpronos_canal_bot"}
            return 200, {"ok": True, "result": {
                "id": 111 if token == "radar-key" else 222,
                "is_bot": True, "username": names.get(token, "wrong_bot"),
            }}
        valid = {"CINE_RADAR_BOT_TOKEN": "radar-key", "MRXPRONOS_CANAL_BOT_TOKEN": "canal-key"}
        self.assertEqual(react.verify_primary_bots(valid, fake), {"radar": "radar-key", "canal": "canal-key"})
        self.assertEqual(react.verify_primary_bots({"CINE_RADAR_BOT_TOKEN": "radar-key"}, fake), {})

    def test_primary_jobs_ordering_and_terminal_exclusion(self):
        queries = []
        class FakeDB:
            def query(self, sql, params=()):
                queries.append((sql, params))
                return {"results": []}
        db = FakeDB()
        react.prepare_primary_jobs(db)
        self.assertEqual(len(queries), 2)
        self.assertIn("ORDER BY p.seq DESC", queries[0][0])
        self.assertIn("channel_reaction_terminal_posts", queries[0][0])
        react.due_primary_jobs(db)
        self.assertIn("ORDER BY j.post_seq DESC", queries[2][0])
        self.assertIn("WHEN 'radar' THEN 0 ELSE 1", queries[2][0])
        self.assertEqual(queries[2][1], (react.MAX_PRIMARY_JOBS_PER_RUN,))

    def test_missing_message_on_primary_quarantines_all_bot_jobs(self):
        class FakeDB:
            def __init__(self):
                self.updates = []
            def query(self, sql, params=()):
                return {"results": [
                    {"post_seq": 22, "bot_role": "radar", "emoji": "❤️",
                     "attempts": 0, "chat_id": "-100123", "message_id": 371,
                     "radar_state": "pending"},
                    {"post_seq": 22, "bot_role": "canal", "emoji": "👍",
                     "attempts": 0, "chat_id": "-100123", "message_id": 371,
                     "radar_state": "pending"},
                ]}
            def batch(self, updates):
                self.updates.extend(updates)
        db = FakeDB()
        def telegram(url, data, headers):
            return 400, {"ok": False, "description": "Bad Request: message to react not found"}
        import unittest.mock
        with unittest.mock.patch.object(react.time, "sleep", return_value=None):
            result = react.process_primary_jobs(db, {"radar": "a", "canal": "b"}, telegram)
        self.assertEqual(result, (0, 1, 0))
        self.assertEqual(len(db.updates), 3)
        self.assertIn("channel_reaction_terminal_posts", db.updates[0][0])
        self.assertIn("channel_reaction_extra_jobs", db.updates[2][0])

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
