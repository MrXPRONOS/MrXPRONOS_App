import os
import unittest
from pathlib import Path
from unittest.mock import patch
import requests
from scripts import neon_rest_compat as legacy
from scripts import supabase_live_cycle as cycle

ROOT=Path(__file__).resolve().parents[1]
LEGACY_FILES=["neon-functions-readiness.yml","neon-live-bundle.yml","neon-live-endpoints-test.yml","neon-live-instant-smoke.yml","neon-live-legacy-production-smoke.yml","neon-live-refresh.yml","neon-live-sql-probe.yml","neon-live-telegram.yml","neon-telegram-connectivity-audit.yml","neon-media-oidc.yml","neon-media-transfer-dispatch.yml"]

class NoNeonLiveTests(unittest.TestCase):
    def test_supabase_preferred_with_old_neon_secret(self):
        with patch.dict(os.environ,{
            "NEON_DATABASE_URL":"postgresql://example.invalid/unused",
            "ACTU_FOOT_BACKEND":"auto",
            "SUPABASE_URL":"https://nhwafcpndlufzzxexikh.supabase.co/",
            "SUPABASE_SERVICE_ROLE_KEY":"fake-test-key"}):
            self.assertEqual(legacy.database_config(),
                ("https://nhwafcpndlufzzxexikh.supabase.co","fake-test-key"))
        with patch.dict(os.environ,{"ACTU_FOOT_BACKEND":"neon"}):
            with self.assertRaisesRegex(RuntimeError,"retired"):
                legacy.database_config()
    def test_direct_legacy_neon_transport_rejected(self):
        class Forbidden:
            def post(self,*args,**kw):raise AssertionError("network called")
        with self.assertRaisesRegex(requests.RequestException,"retired"):
            legacy.NeonRestSession(Forbidden()).post("neon://private/rest/v1/live_predictions")
    def test_supabase_url_rejects_unknown_projects(self):
        for url in ("https://other-project.supabase.co/functions/v1/live",
                    "https://nhwafcpndlufzzxexikh.supabase.co.evil.test/functions/v1/live"):
            with self.assertRaises(cycle.LiveBackendError):
                cycle.base_url(url)
    def test_legacy_workflows_can_no_longer_call_neon(self):
        for name in LEGACY_FILES:
            with self.subTest(name=name):
                text=(ROOT/".github"/"workflows"/name).read_text(encoding="utf-8")
                self.assertNotIn("neon.tech",text.lower())
                self.assertNotIn("NEON_DATABASE_URL",text)
                self.assertNotIn("neon_live_telegram.py",text)
                self.assertNotIn("psycopg",text)
        self.assertIn("supabase_live_cycle",(ROOT/".github"/"workflows"/"neon-live-refresh.yml").read_text())
        self.assertNotIn("sendPhoto",(ROOT/".github"/"workflows"/"neon-live-telegram.yml").read_text())
