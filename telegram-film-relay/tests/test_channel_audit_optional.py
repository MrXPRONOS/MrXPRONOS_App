"""Non-publishing audit: disabled Series and Action are reported as unconfigured."""
import os
import unittest
from unittest.mock import patch

from scripts.channel_audit import requested_channels


class OptionalCategoryAuditTests(unittest.TestCase):
    def setUp(self):
        # CI has no classic channel IDs in local config. These tests only
        # inspect optional-category gating, not the production destinations.
        stub = patch("scripts.channel_audit.config_from", return_value={
            "sources": [], "private_channel": "-1001234567890",
            "public_channel": "@cinexfilms_vf",
        })
        stub.start()
        self.addCleanup(stub.stop)
        legacy = patch("scripts.channel_audit.category_config", return_value={
            "sources": [], "private": "-1001234567890",
            "public": "@cinexcomediefr",
        })
        legacy.start()
        self.addCleanup(legacy.stop)

    def test_unconfigured_series_action_do_not_raise(self):
        env = {
            "SERIES_SOURCE_CHANNELS": "",
            "ACTION_SOURCE_CHANNELS": "",
            "SERIES_RIGHTS_ATTESTED": "",
            "ACTION_RIGHTS_ATTESTED": "",
        }
        with patch.dict(os.environ, env):
            entries = dict((name, config) for name, config, _ in requested_channels())
        self.assertIsNone(entries["series"])
        self.assertIsNone(entries["action"])

    def test_series_action_are_checked_only_when_configured(self):
        env = {
            "SERIES_SOURCE_CHANNELS": "@allowed_series",
            "SERIES_PRIVATE_CHANNEL": "-1003887995735",
            "SERIES_RIGHTS_ATTESTED": "true",
            "ACTION_SOURCE_CHANNELS": "@allowed_action",
            "ACTION_PRIVATE_CHANNEL": "-1003545242931",
            "ACTION_RIGHTS_ATTESTED": "true",
        }
        with patch.dict(os.environ, env):
            entries = dict((name, config) for name, config, _ in requested_channels())
        self.assertTrue(callable(entries["series"]))
        self.assertTrue(callable(entries["action"]))

    def test_incomplete_external_setup_is_not_pre_authorized(self):
        env = {
            "SERIES_SOURCE_CHANNELS": "@allowed_series",
            "SERIES_PRIVATE_CHANNEL": "",
            "SERIES_RIGHTS_ATTESTED": "false",
            "ACTION_SOURCE_CHANNELS": "@allowed_action",
            "ACTION_PRIVATE_CHANNEL": "",
            "ACTION_RIGHTS_ATTESTED": "false",
        }
        with patch.dict(os.environ, env):
            entries = dict((name, config) for name, config, _ in requested_channels())
        self.assertIsNone(entries["series"])
        self.assertIsNone(entries["action"])


if __name__ == "__main__":
    unittest.main()
