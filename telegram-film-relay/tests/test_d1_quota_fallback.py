"""Offline recovery tests for CineRadar D1's free-tier 7500 daily read quota.

Never skip authorizations, invent download links, or delete unverified videos.
"""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from film_relay.radar_download_registry import (
    RadarRegistry, RadarDailyQuotaError,
)
from film_relay.legacy_archive_repair import (
    optional_legacy_central_library, optional_legacy_central_store,
)


class RegistryQuotaTests(unittest.TestCase):
    def test_cloudflare_7500_has_unique_retryable_quota_error(self):
        response = NS(
            ok=False,
            json=lambda: {
                "success": False,
                "result": [],
                "errors": [{
                    "code": 7500,
                    "message": "Your account has exceeded D1's free tier daily row read limit",
                }],
            },
        )
        client = RadarRegistry(
            env={"CLOUDFLARE_API_TOKEN": "mock-test-token"},
            session=NS(post=Mock(return_value=response)),
        )
        with self.assertRaisesRegex(RadarDailyQuotaError, "7500"):
            client._query("SELECT 1")
        client.session.post.assert_called_once()

    def test_unrelated_cloudflare_errors_still_fail_closed(self):
        response = NS(
            ok=False,
            json=lambda: {
                "success": False,
                "result": [],
                "errors": [{"code": 10000, "message": "Not authorized"}],
            },
        )
        client = RadarRegistry(
            env={"CLOUDFLARE_API_TOKEN": "mock-test-token"},
            session=NS(post=Mock(return_value=response)),
        )
        with self.assertRaisesRegex(RuntimeError, "refusé"):
            client._query("SELECT 1")


class LegacyQuotaFallbackTests(unittest.IsolatedAsyncioTestCase):
    def test_d1_quota_falls_back_to_category_stock_only(self):
        with patch("film_relay.legacy_archive_repair.UnifiedLibrary",
                   side_effect=RadarDailyQuotaError("7500")):
            library, down = optional_legacy_central_library(
                NS(), apply=True)
        self.assertIsNone(library)
        self.assertTrue(down)

    def test_other_d1_errors_never_enable_fallback(self):
        with patch("film_relay.legacy_archive_repair.UnifiedLibrary",
                   side_effect=RuntimeError("invalid stock hash")):
            with self.assertRaisesRegex(RuntimeError, "invalid stock"):
                optional_legacy_central_library(NS(), apply=True)

    def test_midrun_quota_disables_registry_without_unsafe_retry(self):
        library = NS(store=AsyncMock(
            side_effect=RadarDailyQuotaError("7500")))
        opts = dict(category="films", title="Un Film", public=NS(),
                    poster=NS(), description="Affiche réelle")
        result = await optional_legacy_central_store(
            library, NS(), **opts)
        self.assertIsNone(result)
        self.assertTrue(library._d1_quota_exhausted)
        result2 = await optional_legacy_central_store(
            library, NS(), **opts)
        self.assertIsNone(result2)
        library.store.assert_awaited_once()

    async def test_healthy_cineradar_remains_four_button_capable(self):
        expected = "https://t.me/CineRadarFr_Bot?start=d_ABCDEFGHIJKLMNOPQRSTUVWX"
        library = NS(store=AsyncMock(return_value=expected))
        result = await optional_legacy_central_store(
            library, NS(), category="films", title="Un film",
            public=NS(), poster=NS(), description="Une description")
        self.assertEqual(result, expected)

    async def test_unrelated_midrun_errors_propagate(self):
        library = NS(store=AsyncMock(side_effect=RuntimeError("bad stock")))
        with self.assertRaisesRegex(RuntimeError, "bad stock"):
            await optional_legacy_central_store(
                library, NS(), category="films", title="Un film",
                public=NS(), poster=NS(), description="Une description")


if __name__ == "__main__":
    unittest.main()
