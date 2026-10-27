"""Fail-closed rights tests for environment-provided source suggestions."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from film_relay.runner import config_from


class SourceRightsConfigTests(unittest.TestCase):
    def load(self, configured, env_source):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"channels.json"
            path.write_text(json.dumps({
                "sources": configured,
                "private_channel": "-1007777777777",
                "public_channel": "@cinex_example"
            }), encoding="utf-8")
            with patch.dict(os.environ, {
                "CINEX_SOURCE_CHANNELS": env_source,
                "FILM_SOURCE_CHANNELS": "",
                "SERIES_SOURCE_CHANNELS": "",
                "TG_PRIVATE_CHANNEL": "",
                "TG_PUBLIC_CHANNEL": "",
            }):
                return config_from(str(path))

    def test_new_environment_source_is_not_authorized(self):
        cfg=self.load([], "@suggested_films")
        self.assertEqual(len(cfg["sources"]), 1)
        self.assertFalse(cfg["sources"][0]["redistribution_authorized"])
        self.assertIn("documenter", cfg["sources"][0]["rights_basis"])

    def test_existing_explicit_permission_is_preserved(self):
        existing=[{"channel":"@licensed_films",
                   "redistribution_authorized":True,
                   "rights_basis":"Documentary approval recorded externally"}]
        cfg=self.load(existing,"@licensed_films")
        self.assertEqual(len(cfg["sources"]),1)
        self.assertTrue(cfg["sources"][0]["redistribution_authorized"])

    def test_mixed_sources_only_authorize_explicit_entry(self):
        existing=[{"channel":"@licensed_films",
                   "redistribution_authorized":True}]
        cfg=self.load(existing,"@another_films")
        self.assertEqual([x["redistribution_authorized"] for x in cfg["sources"]],
                         [True,False])


if __name__ == "__main__":
    unittest.main()
