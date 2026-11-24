import unittest
from unittest.mock import MagicMock
from scripts import ensure_actufoot_v13_cron as cron


class V13CronTests(unittest.TestCase):
    def responses(self, existing=False):
        job = {"url": cron.TARGET, "title": cron.TITLE, "jobId": 42}
        source = {"jobDetails": {"url": cron.SOURCE, "extendedData": {
            "headers": {"authorization": "Bearer fake", "Other": "do not copy"}}}}
        detail = {"jobDetails": {**job, "enabled": True, "requestMethod": 1,
            "schedule": cron.SCHEDULE, "extendedData": {"body": __import__("json").dumps(cron.BODY)}}}
        return [{"jobs": [job] if existing else []}, source, {"jobId": 42}, detail]

    def test_create_readback_and_nothing_else(self):
        call = MagicMock(side_effect=self.responses())
        result = cron.ensure(call)
        self.assertEqual(result["job_id"], 42)
        self.assertEqual(result["action"], "created")
        method, path, payload = call.call_args_list[2].args
        self.assertEqual((method, path), ("PUT", "/jobs"))
        self.assertEqual(payload["job"]["url"], cron.TARGET)
        self.assertNotIn("Other", payload["job"]["extendedData"]["headers"])
        self.assertFalse(cron.BODY["inputs"]["test_private_alert"])

    def test_update_only_existing_target(self):
        call = MagicMock(side_effect=self.responses(True))
        self.assertEqual(cron.ensure(call)["action"], "updated")
        self.assertEqual(call.call_args_list[2].args[:2], ("PATCH", "/jobs/42"))

    def test_conflict_fails_before_write(self):
        call = MagicMock(return_value={"jobs": [{"url": cron.TARGET, "title": "other"}]})
        with self.assertRaisesRegex(RuntimeError, "CONFLICT"):
            cron.ensure(call)
        self.assertEqual(call.call_count, 1)

    def test_readback_mismatch_is_failure(self):
        responses = self.responses()
        responses[-1]["jobDetails"]["enabled"] = False
        with self.assertRaisesRegex(RuntimeError, "READBACK"):
            cron.ensure(MagicMock(side_effect=responses))
