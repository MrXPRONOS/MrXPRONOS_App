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

    def test_merge_does_not_restore_expired_snapshots(self):
        from datetime import timedelta
        today = datetime.now(timezone.utc).date()
        old_day = (today - timedelta(days=80)).isoformat()
        old_week = (today - timedelta(days=150)).isoformat()
        old = {"schema": 1, "tables": {
            m.METRICS: [{"channel_id": 7, "observed_on": old_day}],
            m.OFFICIAL: [{"channel_id": 7, "week_start": old_week}]
        }, "reports": {old_day: {"status": "sent", "parts": {"1": 5}}}}
        merged = merge_mod.merge({"schema": 1}, old)
        self.assertEqual(merged["tables"][m.METRICS], [])
        self.assertEqual(merged["tables"][m.OFFICIAL], [])
        self.assertEqual(merged["reports"], {})

    def test_report_parts_require_all_expected_indices(self):
        with tempfile.TemporaryDirectory() as directory:
            db=m.DB(pathlib.Path(directory) / "state.json")
            day=datetime.now(timezone.utc).date().isoformat()
            db.mark_part(day,2,900)
            with self.assertRaisesRegex(RuntimeError,"Incomplete"):
                db.mark_complete(day,1,1)

    def test_same_day_metric_is_not_historical_growth(self):
        day=datetime.now(timezone.utc).date().isoformat()
        rows=[{"observed_on":day,"subscriber_count":120}]
        self.assertIsNone(m.change(rows,120,day))
        self.assertEqual(m.change([{"observed_on":"2026-01-01","subscriber_count":100}],120,day),20)

    def test_read_only_mode_contains_no_sends_or_state_write(self):
        source=(ROOT / "scripts/telegram_channel_monitor_v2.py").read_text()
        self.assertIn("if dry_run:",source)
        self.assertIn("DRY_RUN_READ_ONLY",source)
        self.assertIn("if not dry_run:db.save()",source)

    def test_dry_run_does_not_send_or_persist(self):
        import asyncio
        from types import SimpleNamespace as NS
        from unittest.mock import AsyncMock, Mock, patch
        client=Mock()
        client.connect=AsyncMock()
        client.is_user_authorized=AsyncMock(return_value=True)
        client.disconnect=AsyncMock()
        client.send_message=AsyncMock()
        async def dialogs():
            yield NS(entity=NS(id=17,broadcast=True,username="examplechannel",
                               creator=True,admin_rights=None,title="Audit"))
        client.iter_dialogs=dialogs
        db=Mock()
        fake_row={"title":"Audit","subscriber_count":10}
        with patch.dict("os.environ",{"TELEGRAM_MONITOR_DRY_RUN":"true",
                                     "TELEGRAM_MONITOR_TEST_MODE":"false"}), \
             patch.object(m,"DB",return_value=db), \
             patch.object(m,"TelegramClient",return_value=client), \
             patch.object(m,"StringSession",return_value="session"), \
             patch.object(m,"Channel",NS), \
             patch.object(m,"env",side_effect=lambda key: "1234"), \
             patch.object(m,"collect",new_callable=AsyncMock,return_value=fake_row), \
             patch.object(m,"official",new_callable=AsyncMock):
            asyncio.run(m.main())
        db.save.assert_not_called()
        client.send_message.assert_not_called()
        client.disconnect.assert_awaited_once()

    def test_dispatch_exposes_read_only_option_and_disables_git_push(self):
        workflow=(ROOT / ".github/workflows/telegram-channel-monitor-daily.yml").read_text()
        self.assertIn("TELEGRAM_MONITOR_DRY_RUN:",workflow)
        self.assertIn("inputs.dry_run",workflow)
        self.assertIn("if: ${{ always() && !(github.event_name == 'workflow_dispatch' && inputs.dry_run) }}",workflow)

    def test_marker_unique_and_recoverable(self):
        self.assertEqual(m.marker("2026-10-27",2),"#MRX_CANAL_20261027_02")
        self.assertNotEqual(m.marker("2026-10-27",2,True),
                            m.marker("2026-10-27",2))


if __name__ == "__main__":
    unittest.main()
