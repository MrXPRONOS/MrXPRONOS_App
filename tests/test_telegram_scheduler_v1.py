import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from telegram_scheduler.core import TelegramScheduler, SchedulerBlocked, UncertainDelivery, window_slots, flood_pause

NOW = datetime(2026, 11, 25, 9, tzinfo=timezone.utc)
SLOT = NOW + timedelta(hours=1)

class FakeRegistry:
    def __init__(self):
        self.owner = None
        self.blocked = False
        self.rows = {}
        self.wait = None

    async def rpc(self, action, owner, **data):
        if action == "acquire":
            if self.owner or self.blocked:
                return {"ok": False}
            self.owner = owner
            return {"ok": True}
        assert owner == self.owner
        if action == "release":
            self.owner = None
            self.blocked = True
            self.wait = data["wait_seconds"]
        elif action == "reserve":
            key = (data["peer"], data["slot"], data["key"])
            if key in self.rows:
                return {"ok": False, **self.rows[key]}
            self.rows[key] = {"id": len(self.rows)+1, "status":"pending", "fingerprint":data["fingerprint"]}
            return {"ok": True, "id":self.rows[key]["id"]}
        else:
            row = next(r for r in self.rows.values() if r["id"] == data["id"])
            row.update(status=action, **({"scheduled_id":data["scheduled_id"]} if "scheduled_id" in data else {}))
        return {"ok":True}

def client():
    c = Mock()
    c.connect = AsyncMock()
    c.disconnect = AsyncMock()
    c.is_connected.return_value = False
    c.get_me = AsyncMock(return_value=SimpleNamespace(id=1, bot=False))
    c.send_message = AsyncMock(return_value=SimpleNamespace(id=12))
    c.send_file = AsyncMock(return_value=SimpleNamespace(id=12))
    c.get_messages = AsyncMock(return_value=[SimpleNamespace(id=12,date=SLOT)])
    return c

class Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.r, self.c = FakeRegistry(), client()
        self.env = patch.dict(os.environ, {"TG_PERSONAL_COOLDOWN_UNTIL_UTC":""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def scheduler(self, hours=24):
        return TelegramScheduler(self.r, lambda:self.c, [-100123], hours, lambda:NOW, 1)

    def test_rolling(self):
        self.assertEqual(window_slots(NOW,24,[(8,0),(20,0)]), [
            NOW.replace(hour=20), (NOW+timedelta(days=1)).replace(hour=8)])
        self.assertEqual(len(window_slots(NOW,168,[(8,0)])),7)
        with self.assertRaises(ValueError):
            window_slots(NOW.replace(tzinfo=None),24,[(8,0)])

    async def test_native_and_duplicate(self):
        async with self.scheduler() as s:
            self.assertEqual((await s.schedule(-100123,SLOT,"a",text="test"))["status"],"verified")
            self.assertEqual((await s.schedule(-100123,SLOT,"a",text="test"))["status"],"duplicate")
        self.c.send_message.assert_awaited_once_with(-100123,"test",schedule=SLOT,parse_mode=None)
        self.assertEqual(self.r.wait,1800)

    async def test_lock_and_cooldown(self):
        async with self.scheduler():
            with self.assertRaises(SchedulerBlocked):
                async with self.scheduler(): pass
        with self.assertRaises(SchedulerBlocked):
            async with self.scheduler(): pass
        self.c.connect.assert_awaited_once()

    async def test_uncertain_stops_batch(self):
        self.c.get_messages.return_value=[]
        async with self.scheduler() as s:
            with self.assertRaises(UncertainDelivery):
                await s.schedule(-100123,SLOT,"a",text="x")
            with self.assertRaises(SchedulerBlocked):
                await s.schedule(-100123,SLOT,"b",text="y")
        self.assertEqual(next(iter(self.r.rows.values()))["status"],"uncertain")
        self.c.send_message.assert_awaited_once()

    async def test_no_send_past_or_unapproved(self):
        async with self.scheduler() as s:
            for p, slot in [(-1,SLOT),(-100123,NOW),(-100123,NOW+timedelta(days=1))]:
                with self.assertRaises(ValueError):
                    await s.schedule(p,slot,"a",text="x")
        self.c.send_message.assert_not_awaited()

    async def test_flood(self):
        err = type("FloodWaitError",(Exception,),{"seconds":8420})()
        self.c.send_message.side_effect=err
        async with self.scheduler() as s:
            with self.assertRaises(type(err)):
                await s.schedule(-100123,SLOT,"a",text="x")
        self.assertEqual(self.r.wait,8720)
        self.assertEqual(flood_pause(err),8720)

    async def test_disconnect_uncertain_keeps_lock(self):
        self.c.disconnect.side_effect=RuntimeError("failure")
        with self.assertRaises(RuntimeError):
            async with self.scheduler(): pass
        self.assertIsNotNone(self.r.owner)

    async def test_bot_rejected(self):
        self.c.get_me.return_value=SimpleNamespace(id=1,bot=True)
        with self.assertRaises(SchedulerBlocked):
            async with self.scheduler(): pass
        self.c.send_message.assert_not_awaited()
        self.assertEqual(self.r.wait,1800)

    async def test_weekly_media(self):
        import tempfile
        from pathlib import Path
        slot=NOW+timedelta(days=6)
        self.c.get_messages.return_value=[SimpleNamespace(id=12,date=slot)]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"file.bin"; p.write_bytes(b"fixture")
            async with self.scheduler(168) as s:
                await s.schedule(-100123,slot,"media",text="caption",file=p,kind="document")
        self.c.send_file.assert_awaited_once_with(-100123,str(p),caption="caption",schedule=slot,parse_mode=None,force_document=True,supports_streaming=False)

    async def test_existing_cooldown(self):
        with patch.dict(os.environ,{"TG_PERSONAL_COOLDOWN_UNTIL_UTC":"2026-11-26T00:00:00Z"}):
            with self.assertRaises(SchedulerBlocked):
                async with self.scheduler(): pass
        self.c.connect.assert_not_awaited()
