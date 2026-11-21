"""CineX bot inventory never edits permissions, fetches updates or leaks IDs."""
from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from scripts.anime_existing_bots_audit import (
    audit_bot_candidates, stock_id,
)


class ExistingBotsAuditTests(unittest.TestCase):
    def test_stock_owner_sha256_must_match(self):
        self.assertEqual(stock_id({}), "-1004353068771")
        with self.assertRaises(RuntimeError):
            stock_id({"CINEX_UNIFIED_PRIVATE_CHANNEL": "-1009999999999"})

    def test_existing_bot_checks_do_not_modify_permissions_or_consume_updates(self):
        queries = []
        class Bot:
            async def identity(self):
                return NS(id=123, username="existing")
            async def call(self, method, args=None):
                queries.append(method)
                if method == "getWebhookInfo":
                    return {"url": ""}
                if method == "getChatMember":
                    return {"status": "administrator", "can_post_messages": True}
                raise AssertionError("Forbidden method " + method)
        env = {
            "ANIME_SOURCE_CHANNEL": "@orak_dessinanime",
            "ANIME_PRIVATE_CHANNEL": "-1001111111111",
            "ANIME_PUBLIC_CHANNEL": "@CineXAnimeFR",
            "ANIME_BOT_TOKEN": "123:existing-token",
        }
        result = asyncio.run(audit_bot_candidates(
            env, transport_factory=lambda token: Bot()))
        self.assertEqual(result["existing_bot_tokens_checked"], 1)
        self.assertEqual(result["bot_only_polling_candidates"], 1)
        self.assertFalse(result["publication_ready"])
        self.assertTrue(set(queries).issubset({"getWebhookInfo", "getChatMember"}))
        self.assertNotIn("-1001111111111", json.dumps(result))
        self.assertNotIn("123:existing-token", json.dumps(result))

    def test_webhook_bot_cannot_be_consumed_by_polling(self):
        class Bot:
            async def identity(self):
                return NS(id=123, username="existing")
            async def call(self, method, args=None):
                if method == "getWebhookInfo":
                    return {"url": "https://example.invalid/hook"}
                if method == "getChatMember":
                    return {"status": "administrator", "can_post_messages": True}
                raise AssertionError(method)
        env = {
            "ANIME_SOURCE_CHANNEL": "@orak_dessinanime",
            "ANIME_PRIVATE_CHANNEL": "-1001111111111",
            "ANIME_BOT_TOKEN": "123:existing",
        }
        result = asyncio.run(audit_bot_candidates(
            env, transport_factory=lambda token: Bot()))
        self.assertEqual(result["bot_only_polling_candidates"], 0)
        self.assertIn("webhook_active_on_some_bots_do_not_poll_those_tokens",
                      result["blockers"])

    def test_missing_sources_are_not_assumed_accessible(self):
        out = asyncio.run(audit_bot_candidates({}))
        self.assertEqual(out["source_capable_bot_count"], 0)
        self.assertEqual(out["source_channels_configured"], 0)
        self.assertFalse(out["publication_ready"])


if __name__ == "__main__":
    unittest.main()
