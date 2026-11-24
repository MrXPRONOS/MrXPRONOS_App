"""Offline guards for slower CineX MTProto personal-session traffic."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from scripts.check_personal_cooldown import (
    KNOWN_UNTIL, blocked_until, parse_utc, seconds_remaining,
)
from film_relay.catalog_scan import _pace_between_pages


ROOT = Path(__file__).resolve().parents[2]


class PersonalSessionPacingTests(unittest.IsolatedAsyncioTestCase):
    def test_latest_floodwait_blocks_until_november_24_1830_utc(self):
        self.assertEqual(KNOWN_UNTIL, datetime(2026, 11, 24, 18, 30, tzinfo=timezone.utc))
        # Telegram replied FloodWait(8420) at 15:51:36 UTC;
        # the extra ~18 minutes are deliberate safety margin.
        now = datetime(2026, 11, 24, 15, 51, 36, tzinfo=timezone.utc)
        self.assertEqual(seconds_remaining(now, {}), 2 * 3600 + 38 * 60 + 24)
        self.assertEqual(seconds_remaining(KNOWN_UNTIL, {}), 0)

    def test_future_cooldown_can_be_extended_but_not_shortened(self):
        self.assertEqual(blocked_until(
            {"TG_PERSONAL_COOLDOWN_UNTIL_UTC": "2026-11-20T11:00:00Z"}),
            KNOWN_UNTIL)
        self.assertEqual(blocked_until(
            {"TG_PERSONAL_COOLDOWN_UNTIL_UTC": "2026-11-25T18:30:00+00:00"}),
            datetime(2026, 11, 25, 18, 30, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            parse_utc("2026-11-20T12:00:00")

    async def test_catalogue_rpc_pacing_when_configured(self):
        with patch.dict(os.environ, {"CINEX_CATALOG_REQUEST_PAUSE_SECONDS": "12"}):
            with patch("film_relay.catalog_scan.asyncio.sleep", new_callable=AsyncMock) as sleep:
                await _pace_between_pages()
                sleep.assert_awaited_once_with(12.0)

    async def test_catalogue_rpc_pacing_zero_is_no_network_sleep(self):
        with patch.dict(os.environ, {"CINEX_CATALOG_REQUEST_PAUSE_SECONDS": "0"}):
            with patch("film_relay.catalog_scan.asyncio.sleep", new_callable=AsyncMock) as sleep:
                await _pace_between_pages()
                sleep.assert_not_awaited()

    def test_major_scheduled_personal_workflows_share_cooldown(self):
        names = (
            "telegram-film-relay.yml",
            "cinex-rescue-channels.yml",
            "cinex-trending-private.yml",
            "cinex-public-video-rotation.yml",
            "cinex-catalog-stage12.yml",
            "telegram-discovery-daily.yml",
            "telegram-channel-monitor-daily.yml",
            "cinex-anime-legacy-repair.yml",
        )
        for name in names:
            with self.subTest(workflow=name):
                text = (ROOT / ".github" / "workflows" / name).read_text(
                    encoding="utf8")
                self.assertIn("check_personal_cooldown.py", text)
                self.assertIn("group: mrx-telegram-personal-account", text)

    def test_main_relay_has_tripled_pacing(self):
        workflow = (ROOT / ".github/workflows/telegram-film-relay.yml").read_text(
            encoding="utf8")
        for required in (
            "CINEX_PAUSE_SECONDS: '60'",
            "CINEX_FORWARD_PAUSE_SECONDS: '54'",
            "CINEX_CATALOG_REQUEST_PAUSE_SECONDS: '12'",
            "run: sleep 60",
            "run: sleep 75",
            "run: sleep 135",
        ):
            with self.subTest(required=required):
                self.assertIn(required, workflow)

    def test_rescue_frequency_is_three_hourly(self):
        workflow = (ROOT / ".github/workflows/cinex-rescue-channels.yml").read_text(
            encoding="utf8")
        self.assertIn("43 */3 * * *", workflow)


if __name__ == "__main__":
    unittest.main()
