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
import actu_foot_health_report as health_report
import football_five_systems_test as five_systems


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
                "status": "failed",
                "attempts": 1,
                "max_attempts": 5,
                "expires_at": None,
            }])
        return _Response([])

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return _Response()


class ActuFootInfrastructureTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch as mock_patch
        for module in (source_cache,observability,provider_health):
            adapter=mock_patch.object(module,"NeonRestSession",side_effect=lambda session:session)
            adapter.start()
            self.addCleanup(adapter.stop)

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

    @patch.dict(os.environ, {
        "NEON_DATABASE_URL": "postgresql://fake-neon-test",
    }, clear=True)
    def test_source_cache_default_ttl_covers_next_lifecycle_run(self):
        session = _Session()
        source_cache.persist_shared_source_snapshot(
            session,
            date(2026, 10, 15),
            [{"source": "espn", "id": "1"}],
        )
        self.assertEqual(len(session.post_calls), 1)
        _url, kwargs = session.post_calls[0]
        payload = kwargs["json"]
        fetched = datetime.fromisoformat(payload["fetched_at"])
        expires = datetime.fromisoformat(payload["expires_at"])
        self.assertGreaterEqual((expires - fetched).total_seconds(), 150)

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

    def test_outbox_count_excludes_expired_exhausted_and_uncertain(self):
        now = datetime(2026, 10, 15, 5, 0, tzinfo=timezone.utc)
        rows = [
            {"status": "failed", "attempts": 1, "max_attempts": 5, "expires_at": None},
            {"status": "claimed", "attempts": 1, "max_attempts": 5, "expires_at": None},
            {"status": "failed", "attempts": 5, "max_attempts": 5, "expires_at": None},
            {"status": "failed", "attempts": 2, "max_attempts": 5,
             "expires_at": "2026-10-15T04:59:00+00:00"},
            {"status": "uncertain", "attempts": 0, "max_attempts": 5, "expires_at": None},
            {"status": "archived", "attempts": 5, "max_attempts": 5, "expires_at": None},
        ]
        self.assertEqual(observability._actionable_outbox_count(rows, now), 2)

    def test_outbox_count_keeps_unexpired_retry_even_if_retry_is_later(self):
        now = datetime(2026, 10, 15, 5, 0, tzinfo=timezone.utc)
        rows = [{
            "status": "failed",
            "attempts": 2,
            "max_attempts": 5,
            "expires_at": "2026-10-15T05:30:00Z",
        }]
        self.assertEqual(observability._actionable_outbox_count(rows, now), 1)

    @patch.dict(os.environ, {
        "FOOTBALL_RUN_METRICS": "1",
        "NEON_DATABASE_URL": "postgresql://fake-neon-test",
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


    def test_news_workflows_restore_public_static_feed_without_neon(self):
        production = (ROOT / ".github/workflows/football-production.yml").read_text(encoding="utf-8")
        update_news = (ROOT / ".github/workflows/update-footnews.yml").read_text(encoding="utf-8")
        self.assertNotIn("git add footnews.json", production)
        self.assertIn("FOOTNEWS_BACKEND", update_news)
        self.assertIn("git add footnews.json", update_news)
        self.assertIn("scripts/actu_foot_d1_news.py", update_news)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", update_news)

    def test_site_prefers_fresh_git_news_with_optional_neon_read_fallback(self):
        js = (ROOT / "assets/js/main.js").read_text(encoding="utf-8")
        neon = (ROOT / "assets/js/actu-foot-neon.js").read_text(encoding="utf-8")
        self.assertIn('import("./actu-foot-neon.js")', js)
        self.assertIn("loadNeonFootNews()", js)
        self.assertIn('from("actu_foot_news_snapshot")', neon)
        self.assertIn("allowAnonymous:true", neon)
        self.assertIn('fetch(`footnews.json?t=${Date.now()}`', js)
        self.assertLess(js.index('fetch(`footnews.json?t=${Date.now()}`'),
                        js.index("rssNews=await loadNeonFootNews()"))
        self.assertIn("source_image || n.image", js)
        self.assertNotIn("Snapshot Infos Foot Supabase", js)

    def test_deprecated_one_shot_workflows_are_removed(self):
        removed = [
            ROOT / ".github/workflows/telegram-programme-recovery-once.yml",
            ROOT / ".github/workflows/telegram-real-e2e-once.yml",
            ROOT / "scripts/telegram_test_programme_recovery.py",
            ROOT / "scripts/telegram_live_e2e.py",
        ]
        self.assertTrue(all(not path.exists() for path in removed))

    def test_run_metrics_count_only_ranking_locked_followups(self):
        channel = (ROOT / "scripts/football_channel.py").read_text(encoding="utf-8")
        self.assertEqual(
            channel.count("tracked_pending=len(followup.locked_pending(state.followed, now))"),
            2,
        )
        self.assertNotIn(
            "tracked_pending=len(followup.pending(state.followed, now))",
            channel,
        )

    def test_health_report_contains_private_operational_summary(self):
        rows = {
            "actu_foot_run_metrics": [
                {"mode": "full", "finished_at": "2026-10-15T07:00:00Z",
                 "duration_ms": 5000, "sent": 1, "skipped": 2, "errors": 0,
                 "tracked_pending": 4, "ranking_selected": 2, "outbox_pending": 0},
                {"mode": "lifecycle", "finished_at": "2026-10-15T07:02:00Z",
                 "duration_ms": 3000, "sent": 0, "skipped": 0, "errors": 0,
                 "tracked_pending": 4, "ranking_selected": 2, "outbox_pending": 0},
            ],
            "actu_foot_provider_health": [
                {"provider": "espn", "base_quality": 98, "effective_quality": 98,
                 "consecutive_failures": 0, "last_success_at": "2026-10-15T07:01:00Z"},
                {"provider": "openligadb", "base_quality": 72, "effective_quality": 60,
                 "consecutive_failures": 2, "last_success_at": "2026-10-15T06:30:00Z"},
            ],
            "actu_foot_publications": [
                {"event_key": "x", "status": "failed", "category": "goal",
                 "attempts": 1, "max_attempts": 5, "expires_at": None},
                {"event_key": "y", "status": "uncertain", "category": "goal",
                 "attempts": 1, "max_attempts": 5, "expires_at": None},
            ],
            "actu_foot_live_events": [],
            "actu_foot_news_snapshot": [
                {"generated_at": "2026-10-15T07:00:00Z", "payload": [{}, {}, {}]},
            ],
        }
        with patch.object(health_report, "_get", side_effect=lambda _s, table, _p: rows[table]):
            report = health_report.build_report(_Session())
        self.assertIn("Dernier FULL", report)
        self.assertIn("Dernier LIFECYCLE", report)
        self.assertIn("Outbox actionnable : **1**", report)
        self.assertIn("Fournisseurs dégradés : **1 / 2**", report)
        self.assertIn("Infos Foot : **3** éléments", report)

    def test_five_systems_review_runs_when_harness_changes(self):
        workflow = (ROOT / ".github/workflows/football-five-systems-review.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/football_five_systems_test.py", workflow)

    def test_five_systems_review_treats_unavailable_as_editorial_skip(self):
        self.assertEqual(
            five_systems.review_exit_code({
                "sent": {"programme": {}},
                "unavailable": {"goal": "Aucun buteur certifié"},
                "errors": {},
            }),
            0,
        )
        self.assertEqual(
            five_systems.review_exit_code({
                "sent": {},
                "unavailable": {},
                "errors": {"goal": "RuntimeError"},
            }),
            1,
        )

    def test_production_workflow_health_summary_is_non_blocking(self):
        workflow = (ROOT / ".github/workflows/football-production.yml").read_text(encoding="utf-8")
        self.assertIn("Tableau de santé Actu Foot", workflow)
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("actu_foot_health_report.py", workflow)
        self.assertIn("GITHUB_STEP_SUMMARY", workflow)

if __name__ == "__main__":
    unittest.main()
