"""Tests du coordinateur quotidien sans aucun accès Telegram réel."""
from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, patch

from scripts import discovery_inventory_daily as coordinator


class TestDailySingleSession(unittest.IsolatedAsyncioTestCase):
    async def test_same_personal_connection_used_for_both_tasks(self):
        dummy = type("Dummy", (), {})()
        dummy.connect = AsyncMock()
        dummy.disconnect = AsyncMock()
        dummy.is_user_authorized = AsyncMock(return_value=True)
        fake_env = {
            "TG_API_ID": "12345", "TG_API_HASH": "hash",
            "TG_SESSION_STRING": "fake-session",
            "CINERADAR_PUBLIC_INVENTORY_FILE": "/tmp/public-cineradar-dry-run.json",
        }
        with patch.dict(os.environ, fake_env), \
             patch.object(coordinator, "StringSession", return_value="session"), \
             patch.object(coordinator, "TelegramClient", return_value=dummy) as ctor, \
             patch.object(coordinator, "inventory_scan", new_callable=AsyncMock, return_value=0) as inventory, \
             patch.object(coordinator, "daily_discovery", new_callable=AsyncMock, return_value=0) as discovery:
            self.assertEqual(await coordinator.run(), 0)
            ctor.assert_called_once()
            dummy.connect.assert_awaited_once()
            dummy.disconnect.assert_awaited_once()
            self.assertIs(inventory.await_args.kwargs["client"], dummy)
            self.assertIs(discovery.await_args.kwargs["client"], dummy)
            self.assertEqual(inventory.await_args.kwargs["public_export_path"],
                             "/tmp/public-cineradar-dry-run.json")

    async def test_inventory_failure_stops_before_discovery(self):
        dummy = type("Dummy", (), {})()
        dummy.connect = AsyncMock()
        dummy.disconnect = AsyncMock()
        dummy.is_user_authorized = AsyncMock(return_value=True)
        fake_env = {
            "TG_API_ID": "12345", "TG_API_HASH": "hash",
            "TG_SESSION_STRING": "fake-session",
            "CINERADAR_PUBLIC_INVENTORY_FILE": "/tmp/public-cineradar-dry-run.json",
        }
        with patch.dict(os.environ, fake_env), \
             patch.object(coordinator, "StringSession", return_value="session"), \
             patch.object(coordinator, "TelegramClient", return_value=dummy), \
             patch.object(coordinator, "inventory_scan", new_callable=AsyncMock, return_value=2), \
             patch.object(coordinator, "daily_discovery", new_callable=AsyncMock) as discovery:
            self.assertEqual(await coordinator.run(), 2)
            discovery.assert_not_awaited()
            dummy.disconnect.assert_awaited_once()

    async def test_missing_config_never_connects(self):
        with patch.dict(os.environ, {
            "TG_API_ID": "", "TG_API_HASH": "", "TG_SESSION_STRING": "",
            "TG_STRING_SESSION": "", "TG_STREAM_SESSION": "",
            "CINERADAR_PUBLIC_INVENTORY_FILE": "",
        }), patch.object(coordinator, "TelegramClient") as client:
            self.assertEqual(await coordinator.run(), 1)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
