"""Offline tests: Telegram monitor uses local GitHub JSON, never Supabase."""
import importlib.util
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
def module_at(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

m = module_at("scripts/telegram_channel_monitor_v2.py", "cinex_github_monitor")
merge_mod = module_at("scripts/merge_channel_monitor.py", "cinex_monitor_merge")


class GitHubStorageTests(unittest.TestCase):
    def test_storage_does_not_depend_on_supabase(self):
        content = (ROOT / "scripts/telegram_channel_monitor_v2.py").read_text()
        self.assertNotIn("SUPABASE_", content)
        self.assertNotIn("requests.Session", content)
        workflow = (ROOT / ".github/workflows/telegram-channel-monitor-daily.yml").read_text()
        self.assertNotIn("SUPABASE_", workflow)

    def test_idempotent_json_rows_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            state = pathlib.Path(directory) / "state.json"
            db = m.DB(state)
            today=datetime.now(timezone.utc).date().isoformat()
            data = {"channel_id": 7, "observed_on": today, "subscriber_count": 100}
            db.put(m.METRICS, [data], "channel_id,observed_on")
            db.put(m.METRICS, [{**data, "subscriber_count": 105}], "channel_id,observed_on")
            db.save()
            reread=m.DB(state)
            rows=reread.read(m.METRICS, channel_id="eq.7",
                             observed_on="gte."+today, order="observed_on.asc")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["subscriber_count"], 105)
            self.assertEqual(len(reread.history(7,today,30)), 1)

    def test_one_daily_report_can_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory) / "state.json"
            db=m.DB(path)
            day=datetime.now(timezone.utc).date().isoformat()
            db.mark_part(day,1,901)
            reloaded=m.DB(path)
            self.assertEqual(reloaded.report(day)["parts"]["1"],901)
            with self.assertRaisesRegex(RuntimeError,"Incomplete"):
                reloaded.mark_complete(day,2,9)
            reloaded.mark_part(day,2,902)
            reloaded.mark_complete(day,2,9)
            self.assertEqual(m.DB(path).report(day)["status"],"sent")

    def test_merge_keeps_parts_and_metrics(self):
        today=datetime.now(timezone.utc).date().isoformat()
        old={"schema":1,"tables":{m.METRICS:[{"channel_id":7,"observed_on":today,"subscriber_count":100}]},
             "reports":{today:{"status":"pending","parts":{"1":90}}}}
        new={"schema":1,"tables":{m.METRICS:[{"channel_id":8,"observed_on":today,"subscriber_count":20}]},
             "reports":{today:{"status":"sent","sent_at":"2026-10-27T00:00:00Z","parts":{"2":91}}}}
        merged=merge_mod.merge(new,old)
        self.assertEqual(len(merged["tables"][m.METRICS]),2)
        self.assertEqual(merged["reports"][today]["status"],"sent")
        self.assertEqual(merged["reports"][today]["parts"],{"1":90,"2":91})

    def test_marker_unique_and_recoverable(self):
        self.assertEqual(m.marker("2026-10-27",2),"#MRX_CANAL_20261027_02")
        self.assertNotEqual(m.marker("2026-10-27",2,True),
                            m.marker("2026-10-27",2))


if __name__ == "__main__":
    unittest.main()
