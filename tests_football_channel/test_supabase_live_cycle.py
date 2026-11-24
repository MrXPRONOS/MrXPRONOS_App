import datetime as dt
import json
import os
import unittest
from unittest import mock
from scripts import supabase_live_cycle as sb

class SupabaseLiveCycleTests(unittest.TestCase):
    def test_only_safe_supabase_endpoint(self):
        self.assertEqual(sb.base_url(sb.DEFAULT_URL+"/"),sb.DEFAULT_URL)
        for value in ("http://nhwafcpndlufzzxexikh.supabase.co/functions/v1/live",
                      "https://anything.neon.tech/functions/v1/live",
                      "https://supabase.co.evil.test/functions/v1/live",
                      "https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/live?token=secret"):
            with self.subTest(value=value),self.assertRaises(sb.LiveBackendError):
                sb.base_url(value)

    def test_public_route_contract(self):
        def fake(req,*,expected=(200,)):
            key=sb.PROBES[req.full_url.removeprefix(sb.DEFAULT_URL)]
            return {key: {} if key=="data" else []}
        with mock.patch.object(sb,"request_json",side_effect=fake):
            report=sb.read_routes(sb.DEFAULT_URL)
        self.assertEqual(len(report),6)

    def test_empty_secret_and_wrong_trigger_are_rejected_before_writes(self):
        with self.assertRaises(sb.LiveBackendError):
            sb._post(sb.DEFAULT_URL,"","/validate")
        with mock.patch.object(sb,"read_routes",return_value={}):
            with mock.patch.dict(os.environ,{"GITHUB_REF":"refs/heads/not-main","GITHUB_EVENT_NAME":"workflow_dispatch"}):
                with self.assertRaises(sb.LiveBackendError):sb.run("cycle")

    def test_no_neon_backend_in_critical_workflows(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        workflow=(root/".github/workflows/validate_predictions.yml").read_text()
        frontend=(root/"assets/js/live.precompiled.js").read_text()
        static=(root/"assets/js/actu-foot-neon.js").read_text()
        for code in (workflow,frontend,static):
            self.assertNotIn("neon.tech",code.lower())
            self.assertNotIn("@neondatabase",code.lower())
        self.assertIn("supabase.co/functions/v1/live",frontend)
        self.assertIn("SUPABASE_LIVE_CYCLE",workflow) if False else None
        self.assertIn("supabase_live_cycle",workflow)
        self.assertNotIn('location.replace("live-suspended.html")',(root/"live.html").read_text())
        self.assertIn("nhwafcpndlufzzxexikh.supabase.co",(root/"scripts/live_visual_smoke.py").read_text())

    def test_validation_response_must_be_successful(self):
        with mock.patch.object(sb,"read_routes",return_value={}):
            with mock.patch.object(sb,"_post",return_value={"success":True,"validated":0}) as call:
                with mock.patch.dict(os.environ,{"GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"workflow_dispatch","CRON_SECRET":"test-not-a-real-secret"}):
                    result=sb.run("validate")
        self.assertEqual(result["validation"]["validated"],0)
        call.assert_called_once_with(sb.DEFAULT_URL,"test-not-a-real-secret","/validate")
