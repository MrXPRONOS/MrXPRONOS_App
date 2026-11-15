#!/usr/bin/env python3
"""Read-only audit of the ambiguous 2026-11-14 Telegram Shorts validation.

Never sends, edits, deletes or downloads media. Does not change D1.
Verify the destination against a previously D1-confirmed Telegram message
before searching the same channel for the uncertain delivery.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

UTC = timezone.utc
TARGET = "2026-11-14"
ANCHOR_DATE = "2026-11-13"
ANCHOR_MESSAGE_ID = 7032
START = datetime(2026, 11, 14, 22, 35, tzinfo=UTC)
END = datetime(2026, 11, 14, 23, 15, tzinfo=UTC)


def expected_caption(day: str) -> str:
    return "📊 Résultats Mr XPRONOS — " + day


def is_expected_video(message, *, day: str = TARGET, start=START, end=END) -> bool:
    timestamp = getattr(message, "date", None)
    if not isinstance(timestamp, datetime):
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    if not start <= timestamp.astimezone(UTC) <= end:
        return False
    text = str(getattr(message, "message", "") or "")
    if not text.startswith(expected_caption(day) + "\n"):
        return False
    return getattr(message, "video", None) is not None


async def audit():
    # Only approved workflow secrets, never printed in logs.
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    session = os.environ.get("TG_SESSION_STRING", "").strip()
    channel = os.environ.get("VALIDATION_CHAT", "").strip()
    if not (api_id.isdecimal() and api_hash and session and channel):
        print("TELEGRAM_VALIDATION_AUDIT_CONFIG_UNAVAILABLE")
        return 3

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    try:
        async with TelegramClient(StringSession(session), int(api_id), api_hash) as client:
            if not await client.is_user_authorized():
                print("TELEGRAM_VALIDATION_AUDIT_SESSION_UNAUTHORIZED")
                return 3
            peer = await client.get_entity(channel)
            anchor = await client.get_messages(peer, ids=ANCHOR_MESSAGE_ID)
            # The 13-Nov video was verified by the provider with message_id 7032
            # in D1. The exact caption and video confirm the channel identity.
            if (not anchor or getattr(anchor, "video", None) is None or
                    not str(getattr(anchor, "message", "") or "").startswith(
                        expected_caption(ANCHOR_DATE) + "\n")):
                print("TELEGRAM_VALIDATION_AUDIT_CHANNEL_UNVERIFIED")
                return 4

            matching_ids = set()
            async for message in client.iter_messages(
                    peer, offset_date=datetime(2026, 11, 15, 0, 30, tzinfo=UTC),
                    limit=450):
                timestamp = getattr(message, "date", None)
                if timestamp is not None:
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=UTC)
                    if timestamp.astimezone(UTC) < START:
                        break
                if is_expected_video(message):
                    matching_ids.add(int(message.id))
            if len(matching_ids) == 1:
                print("TELEGRAM_VALIDATION_AUDIT_CONFIRMED",
                      f"target={TARGET}", f"message_id={next(iter(matching_ids))}",
                      "channel_anchor=verified")
                return 0
            if len(matching_ids) > 1:
                print("TELEGRAM_VALIDATION_AUDIT_MULTIPLE_MATCHES",
                      f"target={TARGET}", f"count={len(matching_ids)}")
                return 5
            print("TELEGRAM_VALIDATION_AUDIT_NOT_FOUND",
                  f"target={TARGET}", "manual_review_required=true")
            return 2
    except Exception as exc:
        print("TELEGRAM_VALIDATION_AUDIT_READ_FAILED",
              "exception=" + type(exc).__name__)
        return 6


if __name__ == "__main__":
    sys.exit(asyncio.run(audit()))
