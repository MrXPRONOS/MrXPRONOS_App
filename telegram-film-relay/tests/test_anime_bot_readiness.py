"""Live cutover readiness is read-only, requires every external prerequisite."""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from scripts.anime_bot_readiness import local_diagnostics, remote_read_only, main, summarize_legacy


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
        client = NS(
            identity=AsyncMock(return_value=NS(id=123)),
            call=AsyncMock(return_value={"url": ""}),
            assert_permissions=AsyncMock(return_value=NS(id=123)),
        )
        with patch("scripts.anime_bot_readiness.AnimeBotTransport",
                   return_value=client):
            verified = asyncio.run(remote_read_only(BASE))
        self.assertTrue(verified["ready_to_publish"], verified)
        self.assertEqual(verified["live_bot_checks"], "permissions_validated")
        client.assert_permissions.assert_awaited_once()
        self.assertEqual(client.call.await_args.args[0], "getWebhookInfo")
        self.assertNotIn("getUpdates", [entry.args[0]
                                       for entry in client.call.await_args_list])

    def test_legacy_catalogue_failure_reports_blocker_and_fails(self):
        from io import StringIO
        from contextlib import redirect_stdout
        stream = StringIO()
        with (patch("scripts.anime_bot_readiness.remote_read_only",
                    new=AsyncMock(return_value={"ready_to_publish": True,
                                                "blockers": []})),
              patch("scripts.anime_bot_readiness.summarize_legacy",
                    side_effect=RuntimeError("private token must never be logged")),
              redirect_stdout(stream)):
            status = main()
        report = json.loads(stream.getvalue())
        self.assertEqual(status, 2)
        self.assertFalse(report["ready_to_publish"])
        self.assertIn("legacy_catalogue_audit_failed", report["blockers"])
        self.assertEqual(report["legacy_catalogue"]["failure_stage"], "legacy_catalogue")
        self.assertNotIn("private token", stream.getvalue())

    def test_unfinished_legacy_batch_blocks_clean_cutover(self):
        from io import StringIO
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "anime.json"
            path.write_text(json.dumps({
                "active_batch": {"episodes": [{"episode": 1}]},
                "series": {}
            }), encoding="utf-8")
            summary = summarize_legacy(str(path))
            self.assertTrue(summary["migration_blocked"])
            self.assertEqual(summary["reason"], "legacy_active_batch_unfinished")
            stream = StringIO()
            with (patch("scripts.anime_bot_readiness.remote_read_only",
                        new=AsyncMock(return_value={"ready_to_publish": True, "blockers": []})),
                  patch.dict("os.environ", {"CINEX_ANIME_LEGACY_CATALOGUE": str(path)}),
                  redirect_stdout(stream)):
                self.assertEqual(main(), 0)
            report = json.loads(stream.getvalue())
            self.assertFalse(report["ready_to_publish"])
            self.assertIn("legacy_active_batch_unfinished", report["blockers"])

    def test_missing_legacy_catalogue_blocks_cutover(self):
        from io import StringIO
        from contextlib import redirect_stdout
        stream = StringIO()
        with (patch("scripts.anime_bot_readiness.remote_read_only",
                    new=AsyncMock(return_value={"ready_to_publish": True, "blockers": []})),
              patch("scripts.anime_bot_readiness.summarize_legacy",
                    return_value={"available": False}),
              redirect_stdout(stream)):
            self.assertEqual(main(), 0)
        report = json.loads(stream.getvalue())
        self.assertFalse(report["ready_to_publish"])
        self.assertIn("legacy_catalogue_missing", report["blockers"])

    def test_unexpected_webhook_blocks_cutover(self):
        client = NS(
            identity=AsyncMock(return_value=NS(id=123)),
            call=AsyncMock(return_value={
                "url": "https://example.invalid/other"}),
            assert_permissions=AsyncMock(),
        )
        with patch("scripts.anime_bot_readiness.AnimeBotTransport",
                   return_value=client):
            report = asyncio.run(remote_read_only(BASE))
        self.assertFalse(report["ready_to_publish"])
        self.assertIn("bot_token_has_other_webhook", report["blockers"])


if __name__ == "__main__":
    unittest.main()
