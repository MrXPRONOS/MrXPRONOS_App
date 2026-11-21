"""Live cutover readiness is read-only, requires every external prerequisite."""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from scripts.anime_bot_readiness import local_diagnostics, remote_read_only


BASE = {
    "CINEX_ANIME_SOURCE_BOT_TOKEN": "123:test-token",
    "CINEX_ANIME_EXPECTED_BOT_ID": "123",
    "ANIME_AUTHORIZED_SOURCE_IDS": "-1001234567890",
    "ANIME_PRIVATE_CHANNEL": "-1001111111111",
    "ANIME_PUBLIC_CHANNEL_ID": "-1002222222222",
    "ANIME_RIGHTS_ATTESTED": "true",
    "CINEX_ANIME_PRIVATE_PERSISTENCE_ATTESTED": "true",
    "CINEX_ANIME_BOT_STATE_PATH": "/srv/cinex-private/episode-store.json",
    "CINEX_ANIME_LEGACY_RELAY_DISABLED": "true",
    "CINEX_ANIME_CUTOVER_VERIFIED": "true",
    "CINEX_ANIME_UNIFIED_LIBRARY_RECONCILED": "true",
}


class AnimeBotReadinessTests(unittest.TestCase):
    def test_missing_prerequisites_are_explained_without_secrets(self):
        report = local_diagnostics({})
        self.assertFalse(report["ready_to_publish"])
        self.assertIn("dedicated_bot_missing", report["blockers"])
        self.assertIn("source_rights_not_attested", report["blockers"])
        self.assertIn("unified_download_library_not_reconciled", report["blockers"])
        self.assertNotIn("123:test-token", json.dumps(report))

    def test_configured_values_do_not_consume_bot_updates(self):
        report = local_diagnostics(BASE)
        self.assertTrue(report["ready_to_publish"])
        client = AsyncMock()
        client.identity.return_value.id = 123
        client.call.return_value = {"url": ""}
        with patch("scripts.anime_bot_readiness.AnimeBotTransport",
                   return_value=client):
            verified = asyncio.run(remote_read_only(BASE))
        self.assertTrue(verified["ready_to_publish"], verified)
        self.assertEqual(verified["live_bot_checks"], "permissions_validated")
        client.assert_permissions.assert_awaited_once()
        self.assertEqual(client.call.await_args.args[0], "getWebhookInfo")
        self.assertNotIn("getUpdates", [entry.args[0]
                                       for entry in client.call.await_args_list])

    def test_unexpected_webhook_blocks_cutover(self):
        client = AsyncMock()
        client.identity.return_value.id = 123
        client.call.return_value = {"url": "https://example.invalid/other"}
        with patch("scripts.anime_bot_readiness.AnimeBotTransport",
                   return_value=client):
            report = asyncio.run(remote_read_only(BASE))
        self.assertFalse(report["ready_to_publish"])
        self.assertIn("bot_token_has_other_webhook", report["blockers"])


if __name__ == "__main__":
    unittest.main()
