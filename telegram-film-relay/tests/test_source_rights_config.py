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

    def test_github_boolean_overrides_technical_json(self):
        with patch.dict(os.environ, {
            "CINEX_MIRROR_WITH_ATTRIBUTION": "false",
            "CINEX_SOURCE_1_ARCHIVE_CYCLE": "false",
            "CINEX_SOURCE_1_DISABLED": "true",
            "CINEX_BOOTSTRAP_MESSAGES": "200",
            "CINEX_SOURCE_CHANNELS": "",
            "FILM_SOURCE_CHANNELS": "",
            "SERIES_SOURCE_CHANNELS": "",
        }):
            cfg = self.load([
                {"channel":"@source_one","archive_cycle":True,
                 "redistribution_authorized":True}], "")
        self.assertFalse(cfg["mirror_with_attribution"])
        self.assertFalse(cfg["sources"][0]["archive_cycle"])
        self.assertTrue(cfg["sources"][0]["source_disabled"])
        self.assertEqual(cfg["bootstrap_messages"], 200)
        self.assertTrue(cfg["sources"][0]["redistribution_authorized"])

    def test_invalid_boolean_rejected(self):
        with patch.dict(os.environ, {"CINEX_MIRROR_WITH_ATTRIBUTION":"perhaps"}):
            with self.assertRaisesRegex(ValueError, "true ou false"):
                self.load([], "")

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

    def test_disablement_survives_environment_source_lists(self):
        from film_relay.series_catalog import series_config
        config=[{"channel":"@pleziyisliye1","redistribution_authorized":False,
                 "source_disabled":True},
                {"channel":"@filmcomplets","redistribution_authorized":True}]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"channels.json"
            path.write_text(json.dumps({"sources":config,
                "private_channel":"-1007777777777","public_channel":"@cinex_example"}))
            with patch.dict(os.environ,{"CHANNELS_CONFIG":str(path),
                     "SERIES_SOURCE_CHANNELS":"@pleziyisliye1 @filmcomplets",
                     "SERIES_SOURCE_CHANNEL":"","TG_PRIVATE_CHANNEL":"",
                     "TG_PUBLIC_CHANNEL":""}):
                resolved=series_config()
        self.assertEqual(resolved["sources"],["@filmcomplets"])

    def test_mixed_sources_only_authorize_explicit_entry(self):
        existing=[{"channel":"@licensed_films",
                   "redistribution_authorized":True}]
        cfg=self.load(existing,"@another_films")
        self.assertEqual([x["redistribution_authorized"] for x in cfg["sources"]],
                         [True,False])


if __name__ == "__main__":
    unittest.main()
