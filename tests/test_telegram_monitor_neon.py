"""Offline Neon contract tests for Telegram private channel monitoring.

No real database, Telegram API, or production secrets are used.
"""
import os
import unittest
from unittest.mock import patch
from scripts import telegram_channel_monitor_v2 as monitor


class FakeCursor:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.rowcount = 1
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, sql, args=None):
        self.calls.append((str(sql), args))
    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, result):
        self.cursor_obj = FakeCursor(result)
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def cursor(self):
        return self.cursor_obj


class TelegramMonitorNeonTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"NEON_DATABASE_URL":"postgresql://test-only"},clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_acquire_is_atomic_and_owner_scoped(self):
        conn=FakeConnection(("test-owner",))
        with patch("psycopg.connect",return_value=conn):
            response=monitor.DB().rpc("telegram_monitor_acquire",
                p_owner="test-owner",p_minutes=25)
        self.assertEqual(response,"ok")
        self.assertEqual(len(conn.cursor_obj.calls),2)
        self.assertIn("telegram_monitor_runtime",conn.cursor_obj.calls[1][0])
        self.assertIn("lock_expires_at<now()",conn.cursor_obj.calls[1][0])
        self.assertEqual(conn.cursor_obj.calls[1][1],("test-owner",25))

    def test_acquire_busy_does_not_steal_lease(self):
        conn=FakeConnection(None)
        with patch("psycopg.connect",return_value=conn):
            outcome=monitor.DB().rpc("telegram_monitor_acquire",p_owner="second",p_minutes=25)
        self.assertEqual(outcome,"busy")

    def test_reservation_is_unique_and_requires_current_owner(self):
        conn=FakeConnection(("2026-10-24",))
        with patch("psycopg.connect",return_value=conn):
            ok=monitor.DB().rpc("telegram_monitor_reserve_report",
               p_on="2026-10-24",p_count=3,p_owner="owner")
        self.assertTrue(ok)
        sql,args=conn.cursor_obj.calls[-1]
        self.assertIn("ON CONFLICT(report_on) DO NOTHING",sql)
        self.assertIn("lock_owner=%s",sql)
        self.assertEqual(args,("2026-10-24",3,"owner","owner"))

    def test_release_keeps_ownership_check(self):
        conn=FakeConnection(None)
        with patch("psycopg.connect",return_value=conn):
            ok=monitor.DB().rpc("telegram_monitor_release",
                p_owner="owner",p_cooldown_seconds=30,p_error="FloodWaitError")
        self.assertTrue(ok)
        sql,args=conn.cursor_obj.calls[-1]
        self.assertIn("WHERE singleton=true AND lock_owner=%s",sql)
        self.assertEqual(args,(30,30,"FloodWaitError","owner"))

    def test_unknown_rpc_fails_closed(self):
        conn=FakeConnection(None)
        with patch("psycopg.connect",return_value=conn):
            with self.assertRaises(ValueError):
                monitor.DB().rpc("unauthorized_delete_all")


if __name__=="__main__":
    unittest.main()
