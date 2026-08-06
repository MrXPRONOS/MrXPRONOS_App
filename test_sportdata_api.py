#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import unittest
from datetime import date
from unittest.mock import Mock, patch

import sportdata_api


class SportDataParserTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "SPORTDATA_API_KEY_1": "test-key",
                "SPORTDATA_API_KEY_2": "",
                "SPORTDATA_API_KEY_3": "",
                "SPORTDATA_API_KEY_4": "",
                "SPORTDATA_API_KEY_5": "",
                "SPORTDATA_API_KEY": "",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    @staticmethod
    def response(payload, status=200):
        response = Mock()
        response.status_code = status
        response.json.return_value = payload
        response.text = ""
        return response

    @patch("sportdata_api.requests.get")
    def test_current_data_envelope(self, mocked_get):
        mocked_get.return_value = self.response(
            {
                "success": True,
                "type": "games-by-date",
                "cacheHit": False,
                "data": {
                    "lastUpdateId": 5715699779,
                    "requestedUpdateId": -1,
                    "ttl": 5,
                    "liveGamesCount": 22,
                    "sports": [{"id": 1, "totalGames": 151}],
                    "games": [{"id": 123, "sportId": 1}],
                },
            }
        )

        result = sportdata_api.fetch_games(
            date(2026, 8, 6),
            date(2026, 8, 6),
            sleep_between_attempts=0,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.schema_path, "root.data")
        self.assertEqual([game["id"] for game in result.games], [123])
        self.assertEqual(result.payload["ttl"], 5)

    @patch("sportdata_api.requests.get")
    def test_legacy_root_schema(self, mocked_get):
        mocked_get.return_value = self.response(
            {
                "lastUpdateId": 1,
                "ttl": 300,
                "games": [{"id": 456}],
            }
        )

        result = sportdata_api.fetch_games(
            date(2026, 8, 6),
            date(2026, 8, 6),
            sleep_between_attempts=0,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.schema_path, "root")
        self.assertEqual(result.games[0]["id"], 456)

    @patch("sportdata_api.requests.get")
    def test_valid_empty_current_schema(self, mocked_get):
        mocked_get.return_value = self.response(
            {
                "success": True,
                "data": {
                    "lastUpdateId": 1,
                    "ttl": 300,
                    "sports": [{"id": 1, "totalGames": 0}],
                    "games": [],
                },
            }
        )

        result = sportdata_api.fetch_games(
            date(2026, 8, 6),
            date(2026, 8, 6),
            sleep_between_attempts=0,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.games, [])
        self.assertEqual(result.schema_path, "root.data")

    @patch("sportdata_api.requests.get")
    def test_success_false_is_rejected(self, mocked_get):
        mocked_get.return_value = self.response(
            {"success": False, "message": "Quota exceeded"}
        )

        result = sportdata_api.fetch_games(
            date(2026, 8, 6),
            date(2026, 8, 6),
            sleep_between_attempts=0,
        )

        self.assertFalse(result.ok)
        self.assertIn("Quota exceeded", result.reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
