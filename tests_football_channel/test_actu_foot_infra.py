import os
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import actu_foot_observability as observability
import actu_foot_source_cache as source_cache
import actu_foot_provider_health as provider_health


class _Response:
    def __init__(self, payload=None):
        self._payload = [] if payload is None else payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Session:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if url.endswith("/rest/v1/actu_foot_publications"):
            return _Response([{
                "event_key": "x",
                "status": "failed",
                "attempts": 1,
                "max_attempts": 5,
                "expires_at": "2099-01-01T00:00:00+00:00",
            }])
        return _Response([])

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return _Response()


class ActuFootInfrastructureTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_source_cache_is_noop_without_supabase_credentials(self):
        session = _Session()
        self.assertIsNone(source_cache.fetch_shared_source_snapshot(session, date(2026, 10, 15)))
        source_cache.persist_shared_source_snapshot(
            session,
            date(2026, 10, 15),
            [{"source": "espn", "id": "1"}],
        )
        self.assertEqual(session.get_calls, [])
        self.assertEqual(session.post_calls, [])

    @patch.dict(os.environ, {}, clear=True)
    def test_metrics_are_noop_when_disabled(self):
        session = _Session()
        observability.persist_run_metrics(
            session,
            mode="lifecycle",
            started_at=datetime.now(timezone.utc),
            dry_run=False,
            counter={"sent": 1, "skipped": 0, "errors": 0},
            tracked_pending=2,
            ranking={"eligible": 3, "selected": 2},
        )
        self.assertEqual(session.get_calls, [])
        self.assertEqual(session.post_calls, [])

    @patch.dict(os.environ, {}, clear=True)
    def test_provider_quality_drops_on_failures_and_recovers_on_success(self):
        quality = {"espn": {"overall": 98}}
        state = provider_health.load_provider_health(_Session(), quality)

        class Snapshot:
            def __init__(self, rows, error=""):
                self.rows = rows
                self.error = error

        session = _Session()
        state = provider_health.record_provider_health(
            session,
            {"espn": Snapshot([], "timeout")},
            quality,
            state,
        )
        degraded = provider_health.effective_quality("espn", quality, state)
        self.assertLess(degraded, 98)

        state = provider_health.record_provider_health(
            session,
            {"espn": Snapshot([{"id": "1"}])},
            quality,
            state,
        )
        recovered = provider_health.effective_quality("espn", quality, state)
        self.assertGreater(recovered, degraded)
        self.assertLessEqual(recovered, 98)

    @patch.dict(os.environ, {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "secret",
    }, clear=True)
    def test_outbox_pending_ignores_quarantine_and_terminal_failures(self):
        class Session(_Session):
            def get(self, url, **kwargs):
                self.get_calls.append((url, kwargs))
                return _Response([
                    {
                        "event_key": "uncertain",
                        "status": "uncertain",
                        "attempts": 1,
                        "max_attempts": 5,
                        "expires_at": "2099-01-01T00:00:00+00:00",
                    },
                    {
                        "event_key": "terminal",
                        "status": "failed",
                        "attempts": 5,
                        "max_attempts": 5,
                        "expires_at": "2099-01-01T00:00:00+00:00",
                    },
                    {
                        "event_key": "retryable",
                        "status": "failed",
                        "attempts": 2,
                        "max_attempts": 5,
                        "expires_at": "2099-01-01T00:00:00+00:00",
                    },
                ])

        self.assertEqual(observability._outbox_pending(Session()), 1)

    @patch.dict(os.environ, {
        "FOOTBALL_RUN_METRICS": "1",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "secret",
        "GITHUB_RUN_ID": "123",
    }, clear=True)
    def test_metrics_persist_private_health_snapshot(self):
        session = _Session()
        observability.persist_run_metrics(
            session,
            mode="full",
            started_at=datetime.now(timezone.utc),
            dry_run=False,
            counter={"sent": 2, "skipped": 1, "errors": 0},
            tracked_pending=4,
            ranking={"eligible": 7, "selected": 6, "matches": []},
        )
        self.assertEqual(len(session.get_calls), 1)
        self.assertEqual(len(session.post_calls), 1)
        url, kwargs = session.post_calls[0]
        self.assertTrue(url.endswith("/rest/v1/actu_foot_run_metrics"))
        self.assertEqual(kwargs["json"]["tracked_pending"], 4)
        self.assertEqual(kwargs["json"]["ranking_selected"], 6)
        self.assertEqual(kwargs["json"]["outbox_pending"], 1)


if __name__ == "__main__":
    unittest.main()
