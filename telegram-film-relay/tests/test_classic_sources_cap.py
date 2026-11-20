"""Source-limit regression for independently owner-configured film feeds."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from film_relay.runner import config_from


class ClassicFilmSourceLimitTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "channels.json"
        self.path.write_text(json.dumps({
            "sources": [
                {"channel": "@baselineone", "redistribution_authorized": True},
                {"channel": "@baselinetwo", "redistribution_authorized": True}
            ],
            "private_channel": "-1009876543210",
            "public_channel": "@cinexfilms_vf",
            "mirror_channel": "@Torrent9SeriesFilms"
        }), encoding="utf-8")

    def test_fourteen_external_plus_two_baseline_allowed(self):
        sources = " ".join(f"@filmsource{i:02d}" for i in range(14))
        with patch.dict(os.environ, {"FILM_SOURCE_CHANNELS": sources,
                                      "TG_PRIVATE_CHANNEL": "-1009876543210",
                                      "TG_PUBLIC_CHANNEL": "@cinexfilms_vf"}):
            config = config_from(str(self.path))
        self.assertEqual(len(config["sources"]), 16)
        self.assertEqual(config["sources"][0]["channel"], "@baselineone")

    def test_fifteen_external_plus_two_baseline_rejected(self):
        sources = " ".join(f"@filmsource{i:02d}" for i in range(15))
        with patch.dict(os.environ, {"FILM_SOURCE_CHANNELS": sources,
                                      "TG_PRIVATE_CHANNEL": "-1009876543210",
                                      "TG_PUBLIC_CHANNEL": "@cinexfilms_vf"}):
            with self.assertRaisesRegex(ValueError, "Maximum 16 sources"):
                config_from(str(self.path))


if __name__ == "__main__":
    unittest.main()
