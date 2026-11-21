#!/usr/bin/env python3
"""READ ONLY: inspect Telegram channel reaction targets without publishing or modifying messages.

Never print Telegram account/session credentials, media paths, or message contents.
All outputs are bounded metadata about known public CinéX channels.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

FILMS = "@CineXFilms_vf"
SERIES = "@seriesvf_cinex"
FILM_CHAT_ID = -1003921647496
SERIES_CHAT_ID = -1004406527554
FILM_MESSAGE_IDS = sorted(set(list(range(368, 436)) + list(range(346, 352))))
SERIES_MESSAGE_IDS = [153, 154, 155, 156, 157]


def summarize_message(requested_id: int, message: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"id": requested_id}
    if message is None or type(message).__name__ == "MessageEmpty":
        result["status"] = "not_visible_or_deleted"
        return result
    result["actual_id"] = getattr(message, "id", None)
    if type(message).__name__ == "MessageService":
        result["status"] = "service"
        result["service_action"] = type(getattr(message, "action", None)).__name__
    else:
        result["status"] = "content"
        result["media_type"] = type(getattr(message, "media", None)).__name__
        result["has_text"] = bool(getattr(message, "message", ""))
        result["has_grouped_id"] = bool(getattr(message, "grouped_id", None))
        result["is_pinned"] = bool(getattr(message, "pinned", False))
    dt = getattr(message, "date", None)
    result["posted_at_utc"] = dt.isoformat() if dt else None
    return result


async def audit_channel(client: Any, username: str, expected_chat_id: int,
                        ids: list[int]) -> None:
    from telethon import utils

    entity = await client.get_entity(username)
    actual = utils.get_peer_id(entity)
    if actual != expected_chat_id:
        raise RuntimeError("Telegram username points to a different channel; safe stop")
    newest = await client.get_messages(entity, limit=3)
    print("CHANNEL_SUMMARY " + json.dumps({
        "channel": username, "verified_chat_id": expected_chat_id,
        "latest_visible_ids": [int(m.id) for m in newest if m],
    }))
    results = await client.get_messages(entity, ids=ids)
    for requested_id, message in zip(ids, results):
        print("MESSAGE_METADATA " + json.dumps({
            "channel": username, **summarize_message(requested_id, message)
        }, ensure_ascii=False))
    if len(results) != len(ids):
        raise RuntimeError("Incomplete Telegram batch; no inference about missing messages")



def audit_webhook_state() -> None:
    """Read-only Bot API webhook status, without logging the token or raw URL."""
    from datetime import datetime, timezone
    from urllib.request import urlopen
    import re

    token = (os.getenv("CINE_RADAR_BOT_TOKEN") or "").strip()
    if not token:
        print("WEBHOOK_DIAGNOSTIC missing_bot_token")
        return
    try:
        with urlopen("https://api.telegram.org/bot" + token + "/getWebhookInfo", timeout=15) as response:
            payload = json.load(response)
        if not payload.get("ok"):
            print("WEBHOOK_DIAGNOSTIC telegram_query_rejected")
            return
        info = payload.get("result") or {}
        message = str(info.get("last_error_message") or "").casefold()
        code = re.search(r"(?<!\\d)([45]\\d{2})(?!\\d)", message)
        error_kind = (
            "timeout" if any(x in message for x in ("timeout", "timed out", "deadline"))
            else "forbidden" if "forbidden" in message
            else "http_error" if code
            else "connection_error" if any(x in message for x in ("connect", "refused", "reset"))
            else "other_error" if message else "none"
        )
        error_ts = int(info.get("last_error_date") or 0)
        last_error_utc = (datetime.fromtimestamp(error_ts, timezone.utc).isoformat()
                          if error_ts else None)
        # Last error is Telegram-generated, but redact transport addresses and
        # token-like substrings before emitting it to GitHub job logs.
        safe_description = re.sub(r"https?://[^\\s]+", "[url]", str(info.get("last_error_message") or ""), flags=re.I)
        safe_description = safe_description.replace(token, "[redacted]")
        safe_description = re.sub(r"(?<![A-Za-z0-9])[0-9]{6,}:[A-Za-z0-9_-]{18,}", "[redacted]", safe_description)
        print("WEBHOOK_DIAGNOSTIC " + json.dumps({
            "valid_target": info.get("url") == "https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/telegram",
            "pending_updates": int(info.get("pending_update_count") or 0),
            "last_error_utc": last_error_utc,
            "last_error_category": error_kind,
            "last_error_redacted": safe_description[:220],
            "last_error_http_code": code.group(1) if code else None,
            "max_connections": info.get("max_connections"),
            "subscribed_channel_posts": "channel_post" in (info.get("allowed_updates") or []),
        }))
    except Exception as exc:
        print("WEBHOOK_DIAGNOSTIC_ERROR " + type(exc).__name__)



async def main() -> int:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or "").strip()
    if not api_id or not api_hash or not session:
        print("FORENSIC_ERROR missing_existing_telegram_session")
        return 2
    audit_webhook_state()
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            request_retries=2, connection_retries=2)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("FORENSIC_ERROR unauthorized_existing_session")
            return 2
        await audit_channel(client, FILMS, FILM_CHAT_ID, FILM_MESSAGE_IDS)
        await audit_channel(client, SERIES, SERIES_CHAT_ID, SERIES_MESSAGE_IDS)
        print("FORENSIC_COMPLETE read_only")
        return 0
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        # Avoid raw transport exceptions that might contain session or sensitive URLs.
        print("FORENSIC_ERROR " + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
