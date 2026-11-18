#!/usr/bin/env python3
"""Index metadata (no media bytes) from the three user-designated public channels.

Read-only Telegram session; D1 writes only caption and message coordinates.
Bootstraps unbound IDs only from the explicitly configured, administrator-owned public channels.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from telethon import TelegramClient, utils
from telethon.sessions import StringSession

CHANNELS = {
    "films": "CineXFilms_vf",
    "series": "seriesvf_cinex",
    "animes": "CineXAnimeFR",
}
D1_ID = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"
ACCOUNT_ID = "9c86118191b804d91b5f5b2c89114999"


def query_d1(sql, params=None):
    token = (os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("cloudflare_token_missing")
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{D1_ID}/query"
    payload = json.dumps({"sql": sql, "params": params or []}).encode("utf-8")
    request = Request(url, data=payload, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }, method="POST")
    try:
        with urlopen(request, timeout=25) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"d1_http_{exc.code}") from None
    if not data.get("success") or not data.get("result") or not data["result"][0].get("success"):
        raise RuntimeError("d1_query_failed")
    return data["result"][0].get("results", [])


def query_d1_batch(statements):
    """Send small D1 batches instead of one HTTPS request per public message."""
    token = (os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("cloudflare_token_missing")
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{D1_ID}/query"
    for offset in range(0, len(statements), 35):
        chunk = statements[offset:offset + 35]
        payload = json.dumps({"batch": [{"sql": sql, "params": params} for sql, params in chunk]}).encode("utf-8")
        req = Request(url, data=payload, headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }, method="POST")
        try:
            with urlopen(req, timeout=30) as response:
                body = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"d1_batch_http_{exc.code}") from None
        if not body.get("success") or len(body.get("result", [])) != len(chunk) or not all(
            x.get("success") for x in body["result"]
        ):
            raise RuntimeError("d1_batch_query_failed")


async def backfill():
    api_id = (os.environ.get("TG_API_ID") or "").strip()
    api_hash = (os.environ.get("TG_API_HASH") or "").strip()
    session = (os.environ.get("TG_SESSION_STRING")
               or os.environ.get("TG_STRING_SESSION")
               or os.environ.get("TG_STREAM_SESSION") or "").strip()
    if not api_id.isdigit() or not api_hash or not session:
        raise RuntimeError("telegram_session_credentials_missing")
    # An existing Bot API verified ID is immutable; an unbound ID may be verified by the owner's admin session.
    rows = query_d1("SELECT kind,username,chat_id FROM radar_primary_channels")
    expected = {r["kind"]: r for r in rows}
    count = 0
    skipped = 0
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            request_retries=1, connection_retries=2,
                            flood_sleep_threshold=0, receive_updates=False)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("telegram_session_not_authorized")
        myself = await client.get_me()
        for kind, username in CHANNELS.items():
            record = expected.get(kind)
            if not record or record.get("username", "").lower() != username.lower():
                skipped += 1
                print("CINE_RADAR_BACKFILL_SKIPPED", kind, "channel_not_configured")
                continue
            try:
                entity = await client.get_entity(username)
                if (not getattr(entity, "broadcast", False)
                        or str(getattr(entity, "username", "")).lower() != username.lower()):
                    raise ValueError("channel_username_mismatch")
                channel_id = str(utils.get_peer_id(entity))
            except Exception as exc:
                skipped += 1
                print("CINE_RADAR_BACKFILL_SKIPPED", kind, "channel_not_accessible", type(exc).__name__)
                continue
            if record["chat_id"] and channel_id != str(record["chat_id"]):
                skipped += 1
                print("CINE_RADAR_BACKFILL_SKIPPED", kind, "immutable_identity_mismatch")
                continue
            if not record["chat_id"]:
                # The personal session must demonstrably administer this exact channel.
                try:
                    rights = await client.get_permissions(entity, myself)
                    owner_admin = bool(
                        getattr(rights, "is_creator", False)
                        or getattr(rights, "is_admin", False)
                        or getattr(entity, "creator", False)
                        or getattr(entity, "admin_rights", None)
                    )
                except Exception:
                    owner_admin = bool(getattr(entity, "creator", False) or getattr(entity, "admin_rights", None))
                if not owner_admin:
                    skipped += 1
                    print("CINE_RADAR_BACKFILL_SKIPPED", kind, "personal_session_not_administrator")
                    continue
                query_d1(
                    "UPDATE radar_primary_channels SET chat_id=?,updated_at=CURRENT_TIMESTAMP "
                    "WHERE kind=? AND LOWER(username)=LOWER(?) AND chat_id IS NULL",
                    [channel_id, kind, username],
                )
                current = query_d1(
                    "SELECT chat_id FROM radar_primary_channels WHERE kind=?", [kind]
                )
                if not current or str(current[0].get("chat_id") or "") != channel_id:
                    skipped += 1
                    print("CINE_RADAR_BACKFILL_SKIPPED", kind, "d1_binding_verification_failed")
                    continue
                print("CINE_RADAR_BACKFILL_OWNER_ADMIN_BOUND", kind)

            seen = 0
            pending = []
            async for message in client.iter_messages(entity, limit=250):
                if not message.id or not message.date:
                    continue
                # Do not download, copy or forward media: only the public post metadata.
                if getattr(message, "video", None) is not None or (
                    getattr(message, "document", None) is not None
                    and str(getattr(message.document, "mime_type", "")).startswith("video/")
                ):
                    media_kind = "video"
                elif getattr(message, "photo", None) is not None:
                    media_kind = "photo"
                else:
                    media_kind = "text"
                caption = str(message.message or "").strip()[:500]
                when = message.date.astimezone(timezone.utc).isoformat()
                pending.append((
                    "INSERT INTO radar_posts(chat_id,message_id,kind,username,caption,media_kind,posted_at) "
                    "VALUES(?,?,?,?,?,?,?) "
                    "ON CONFLICT(chat_id,message_id) DO UPDATE SET "
                    "caption=excluded.caption,media_kind=excluded.media_kind,updated_at=CURRENT_TIMESTAMP",
                    [channel_id, str(message.id), kind, username, caption, media_kind, when],
                ))
                seen += 1
                if len(pending) >= 35:
                    query_d1_batch(pending)
                    pending.clear()
                await asyncio.sleep(0.04)
            if pending:
                query_d1_batch(pending)
            count += seen
            print("CINE_RADAR_BACKFILL", kind, "indexed", seen)
    finally:
        await client.disconnect()
    print("CINE_RADAR_BACKFILL_RESULT", json.dumps({"indexed": count, "skipped_channels": skipped}))


if __name__ == "__main__":
    asyncio.run(backfill())
