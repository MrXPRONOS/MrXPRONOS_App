"""Lot 2: offline-only strict readiness checks, no network or Telegram writes."""
from __future__ import annotations

import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts.unified_publishing_preflight import (
    token_for, verify_cineradar_registry
)
from film_relay.public_video_retention import validate_retention_targets


class Lot12ReadinessTests(unittest.TestCase):
    def test_no_partial_publication_coverage(self):
        pairs = [
            ("films", "@CineXFilms_vf", -1001111111111),
            ("series", "@seriesvf_cinex", -1002222222222),
            ("desir", "@CineXDesirfr", -1003333333333),
            ("comedie", "@CineXComediefr", -1004444444444),
            ("anime", "@CineXAnimeFR", -1005555555555),
            ("action", "@filmsaction2026vf", -1006666666666),
        ]
        validate_retention_targets(pairs)
        with self.assertRaisesRegex(RuntimeError, "six couples"):
            validate_retention_targets(pairs[:4])

    def test_dedicated_anime_cannot_pass_using_legacy_desir_token(self):
        env = {"FOOTBALL_NEWS_BOT_TOKEN": "common",
               "DESIR_BOT_TOKEN": "old",
               "CINEX_ANIME_LEGACY_RELAY_DISABLED": "true"}
        with patch("scripts.unified_publishing_preflight.os.environ", env):
            self.assertEqual(token_for("anime"), "")
            env["CINEX_ANIME_SOURCE_BOT_TOKEN"] = "dedicated"
            self.assertEqual(token_for("anime"), "dedicated")
            self.assertEqual(token_for("desir"), "old")
            env["CINEX_ANIME_LEGACY_RELAY_DISABLED"] = "false"
            self.assertEqual(token_for("anime"), "common")
            self.assertEqual(token_for("films"), token_for("anime"))
            self.assertEqual(token_for("series"), token_for("anime"))
            del env["FOOTBALL_NEWS_BOT_TOKEN"]
            env["TELEGRAM_BOT_TOKEN"] = "fallback"
            self.assertEqual(token_for("anime"), "fallback")
            del env["TELEGRAM_BOT_TOKEN"]
            self.assertEqual(token_for("anime"), "")

    def test_verified_stock_must_match_d1_and_enabled_gate(self):
        env = {"CINEX_UNIFIED_PRIVATE_CHANNEL": "-1001234567890"}
        queries = []
        def ask(sql):
            queries.append(sql)
            if "cine_private_stock_config" in sql:
                return {"results": [{"stock_chat_id": "-1001234567890",
                                     "radar_bot_id": 123}]}
            return {"results": [{"value": "1"}]}
        registry = SimpleNamespace(_query=ask)
        with (patch("scripts.unified_publishing_preflight.configured_private_id",
                    return_value=-1001234567890),
              patch("scripts.unified_publishing_preflight.RadarRegistry",
                    return_value=registry)):
            self.assertEqual(verify_cineradar_registry(env), -1001234567890)
            self.assertEqual(len(queries), 2)
            registry._query = lambda sql: {"results": [
                {"stock_chat_id": "-1000000000000", "radar_bot_id": 123}]}
            with self.assertRaisesRegex(RuntimeError, "non confirmé"):
                verify_cineradar_registry(env)

    def test_stock_gate_disabled_blocks_download_readiness(self):
        registry = SimpleNamespace(_query=lambda sql: {
            "results": [{"stock_chat_id": "-1001234567890", "radar_bot_id": 4}]
            if "cine_private_stock_config" in sql else [{"value": "0"}]
        })
        with (patch("scripts.unified_publishing_preflight.configured_private_id",
                    return_value=-1001234567890),
              patch("scripts.unified_publishing_preflight.RadarRegistry",
                    return_value=registry)):
            with self.assertRaisesRegex(RuntimeError, "désactivée"):
                verify_cineradar_registry({})


if __name__ == "__main__":
    unittest.main()
