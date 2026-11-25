"""Native Telegram scheduling. Import only; no network on import."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

UTC = timezone.utc
KNOWN_UNTIL = datetime(2026, 11, 24, 18, 30, tzinfo=UTC)


class SchedulerBlocked(RuntimeError):
    pass


class UncertainDelivery(RuntimeError):
    pass


def utc(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone required")
    return value.astimezone(UTC)


def window_slots(start, hours, clock_times):
    """Return UTC slots in [start,start+horizon), including next day."""
    start = utc(start)
    if hours not in (24, 168):
        raise ValueError("Horizon must be 24 or 168 hours")
    end = start + timedelta(hours=hours)
    slots = set()
    for day in range(hours // 24 + 1):
        date = (start + timedelta(days=day)).date()
        for hour, minute in clock_times:
            slot = datetime(date.year, date.month, date.day, hour, minute, tzinfo=UTC)
            if start <= slot < end:
                slots.add(slot)
    return sorted(slots)


def fingerprint(text, file=None, kind="text", parse_mode=None):
    digest = hashlib.sha256(json.dumps([kind, text, parse_mode], ensure_ascii=False).encode())
    if file is not None:
        with Path(file).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


class SupabaseRegistry:
    def __init__(self, url, key):
        if not url.startswith("https://") or not key:
            raise ValueError("Supabase backend credentials required")
        self.url = url.rstrip("/") + "/rest/v1/rpc/tg_scheduler_v1_rpc"
        self.key = key

    @classmethod
    def from_env(cls):
        return cls(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    async def rpc(self, action, owner, **data):
        def call():
            req = Request(self.url, data=json.dumps({
                "p_action": action, "p_owner": owner, "p_data": data
            }).encode(), headers={"Content-Type": "application/json",
                                  "apikey": self.key, "Authorization": "Bearer " + self.key})
            with urlopen(req, timeout=20) as response:
                result = json.load(response)
            if not isinstance(result, dict) or type(result.get("ok")) is not bool:
                raise RuntimeError("Invalid scheduler registry response")
            return result
        return await asyncio.to_thread(call)


def make_client():
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    session = (os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION")
               or os.getenv("TG_STREAM_SESSION"))
    if not session:
        raise ValueError("Missing personal session")
    return TelegramClient(StringSession(session), int(os.environ["TG_API_ID"]),
                          os.environ["TG_API_HASH"], flood_sleep_threshold=0,
                          request_retries=0, connection_retries=0, auto_reconnect=False)


def flood_pause(error):
    # Never automatically retry or rotate accounts after a Telegram restriction.
    if error is None:
        return 0
    name = type(error).__name__
    if name in ("FloodWaitError", "FloodPremiumWaitError", "SlowModeWaitError"):
        return max(1800, int(getattr(error, "seconds", 0)) + 300)
    if name in ("PeerFloodError", "UserRestrictedError", "AuthKeyDuplicatedError"):
        return 86400
    return 0


class TelegramScheduler:
    """Single managed session. All integrations must use the same DB lock."""
    def __init__(self, registry, client_factory, allowed_peers, hours=24,
                 clock=lambda: datetime.now(UTC), expected_account=None):
        if hours not in (24, 168):
            raise ValueError("Invalid horizon")
        self.registry, self.factory = registry, client_factory
        self.allowed = frozenset(int(x) for x in allowed_peers)
        if not self.allowed:
            raise ValueError("Explicit destination allowlist required")
        self.hours, self.clock = hours, clock
        self.expected_account = expected_account
        self.owner = str(uuid.uuid4())
        self.client = None
        self.held = False
        self.failed = False
        self.pause = 0
        self.start = None
        self._serial = asyncio.Lock()
        self._queue_counts = {}

    @classmethod
    def from_env(cls, hours=24):
        if os.getenv("TG_SCHEDULER_ENABLED") != "1":
            raise SchedulerBlocked("Scheduler disabled")
        return cls(SupabaseRegistry.from_env(), make_client,
                   os.environ["TG_SCHEDULER_ALLOWED_PEERS"].split(","),
                   hours=hours, expected_account=int(os.environ["TG_SCHEDULER_ACCOUNT_ID"]))

    async def __aenter__(self):
        if self.held or self.start is not None:
            raise RuntimeError("Session object is single-use")
        floor = KNOWN_UNTIL
        extra = os.getenv("TG_PERSONAL_COOLDOWN_UNTIL_UTC")
        if extra:
            floor = max(floor, utc(datetime.fromisoformat(extra.replace("Z", "+00:00"))))
        if utc(self.clock()) < floor:
            raise SchedulerBlocked("Existing Telegram cooldown")
        result = await self.registry.rpc("acquire", self.owner)
        if not result["ok"]:
            raise SchedulerBlocked("Global session unavailable")
        self.held = True
        self.start = utc(self.clock())
        try:
            self.client = self.factory()
            await self.client.connect()
            me = await self.client.get_me()
            if me is None or me.bot:
                raise SchedulerBlocked("Authorized personal account required")
            if self.expected_account is not None and me.id != self.expected_account:
                raise SchedulerBlocked("Unexpected Telegram account")
            return self
        except BaseException as error:
            await self._close(error)
            raise

    async def _close(self, error=None):
        self.pause = max(self.pause, flood_pause(error), 1800)
        if self.client is not None:
            try:
                await self.client.disconnect()
                if self.client.is_connected():
                    raise RuntimeError("Disconnect not confirmed")
            except BaseException:
                # Deliberately keep persistent lock; operator must confirm old runner stopped.
                self.failed = True
                raise
        if self.held:
            result = await self.registry.rpc("release", self.owner, wait_seconds=self.pause)
            if not result["ok"]:
                raise RuntimeError("Lock release not confirmed")
            self.held = False

    async def __aexit__(self, typ, error, tb):
        async with self._serial:
            await self._close(error)

    async def preflight_queue(self, planned):
        """Fail before first send if a peer would exceed a conservative queue cap."""
        if not self.held or self.failed:
            raise SchedulerBlocked("Session not active")
        for raw_peer, count in planned.items():
            peer = int(raw_peer)
            if peer not in self.allowed or int(count) < 0:
                raise ValueError("Unauthorized peer or invalid count")
            queued = await self.client.get_messages(peer, scheduled=True)
            existing = len(queued)
            if existing + int(count) > 90:
                raise SchedulerBlocked("Telegram scheduled queue capacity guard")
            self._queue_counts[peer] = existing

    def _slot(self, slot):
        slot = utc(slot)
        now = utc(self.clock())
        if slot.microsecond or slot < now + timedelta(seconds=60) or slot >= self.start + timedelta(hours=self.hours):
            raise ValueError("Slot outside rolling horizon or too close")
        return slot

    async def schedule(self, peer, slot, key, text="", file=None, kind="text", parse_mode=None):
        """One message, image, video or document. No live send fallback."""
        async with self._serial:
            if not self.held or self.failed:
                raise SchedulerBlocked("Session inactive or stopped")
            peer = int(peer)
            if peer not in self.allowed:
                raise ValueError("Destination not allowlisted")
            slot = self._slot(slot)
            if not key or len(key) > 256 or kind not in ("text", "image", "video", "document"):
                raise ValueError("Invalid publication")
            if (kind == "text") != (file is None) or (kind == "text" and not text):
                raise ValueError("Text or local file required")
            digest = fingerprint(text, file, kind, parse_mode)
            try:
                reservation = await self.registry.rpc("reserve", self.owner, peer=peer,
                    slot=slot.isoformat(), key=key, fingerprint=digest)
                if not reservation["ok"]:
                    if reservation["status"] == "verified" and reservation["fingerprint"] == digest:
                        queued = await self.client.get_messages(peer, scheduled=True)
                        if any(m and int(m.id) == int(reservation["scheduled_id"]) and utc(m.date) == slot for m in queued):
                            return {"status": "duplicate", "scheduled_id": reservation["scheduled_id"]}
                    raise UncertainDelivery("Existing slot conflict or missing queue entry; manual reconciliation required")
                row = reservation["id"]
                try:
                    # Check again after DB I/O; never schedule an expired message.
                    self._slot(slot)
                    if kind == "text":
                        msg = await self.client.send_message(peer, text, schedule=slot, parse_mode=parse_mode)
                    else:
                        msg = await self.client.send_file(peer, str(file), caption=text,
                            schedule=slot, parse_mode=parse_mode, force_document=(kind == "document"),
                            supports_streaming=(kind == "video"))
                    msg_id = int(msg.id)
                    if msg_id <= 0:
                        raise UncertainDelivery("Invalid scheduled ID")
                    await self.registry.rpc("accepted", self.owner, id=row, scheduled_id=msg_id)
                    queued = await self.client.get_messages(peer, scheduled=True)
                    if not any(m and m.id == msg_id and utc(m.date) == slot for m in queued):
                        raise UncertainDelivery("Telegram queue/date not confirmed")
                    await self.registry.rpc("verified", self.owner, id=row, scheduled_id=msg_id)
                    self._queue_counts[peer] = self._queue_counts.get(peer, len(queued)) + 1
                    return {"status": "verified", "scheduled_id": msg_id}
                except BaseException as error:
                    self.pause = max(self.pause, flood_pause(error))
                    try:
                        await self.registry.rpc("uncertain", self.owner, id=row)
                    except Exception:
                        pass  # Existing pending/accepted record blocks automatic resends.
                    raise
            except BaseException as error:
                self.failed = True
                self.pause = max(self.pause, flood_pause(error))
                raise
