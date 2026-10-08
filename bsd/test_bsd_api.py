"""Tests hors ligne du client BSD, sans clé ni connexion réseau."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from bsd_api import BSDClient, BSDAPIError, BSDQuotaError, BSDRequestBudgetError, _rate_limit_remaining


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self.payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        return self.payload


class TestBSDClient(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = Mock()
        self.session.headers = {}
        self.client = BSDClient(
            api_key="test-only",
            cache_dir=Path(self.tmp.name),
            session=self.session,
            sleep=lambda _: None,
            min_interval=0,
            max_retries=0,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_quota_parser(self):
        self.assertEqual(_rate_limit_remaining('"football";r=7213;t=52800'), 7213)
        self.assertIsNone(_rate_limit_remaining('invalid'))

    def test_pagination_and_deduplication(self):
        self.session.get.side_effect = [
            FakeResponse({"count": 3, "results": [{"id": 1}, {"id": 2}]}),
            FakeResponse({"count": 3, "results": [{"id": 2}, {"id": 3}]}),
        ]
        out = self.client.list_events(date(2026, 10, 8), date(2026, 10, 8), page_size=2)
        self.assertEqual([e["id"] for e in out.events], [1, 2, 3])
        self.assertTrue(out.complete)
        self.assertEqual(self.client.requests_made, 2)

    def test_cache_avoids_new_request(self):
        self.session.get.return_value = FakeResponse({"count": 1, "results": [{"id": 4}]})
        self.client.list_events(date(2026, 10, 8), date(2026, 10, 8))
        self.client.list_events(date(2026, 10, 8), date(2026, 10, 8))
        self.assertEqual(self.session.get.call_count, 1)
        self.assertEqual(self.client.cache_hits, 1)

    def test_quota_exhausted(self):
        self.session.get.return_value = FakeResponse({"code": "taster_exhausted"}, 429, {"RateLimit": '"football";r=0;t=1'})
        with self.assertRaises(BSDQuotaError):
            self.client.get_json("/events/")

    def test_budget(self):
        self.client.max_requests = 1
        self.session.get.return_value = FakeResponse({"count": 0, "results": []})
        self.client.get_json("/events/")
        with self.assertRaises(BSDRequestBudgetError):
            self.client.get_json("/leagues/")

    def test_incomplete_page(self):
        self.session.get.return_value = FakeResponse({"count": 500, "results": [{"id": 1}]})
        out = self.client.list_events(date(2026, 10, 8), date(2026, 10, 8), page_size=200, max_pages=1)
        self.assertFalse(out.complete)

    def test_unexpected_schema(self):
        self.session.get.return_value = FakeResponse({"data": []})
        with self.assertRaises(BSDAPIError):
            self.client.list_events(date(2026, 10, 8), date(2026, 10, 8))


if __name__ == "__main__":
    unittest.main()
