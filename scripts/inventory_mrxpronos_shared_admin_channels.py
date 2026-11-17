#!/usr/bin/env python3
"""Verify personal AND @mrxpronos_canal_bot admin roles and store in Vault.

- Read-only Telegram interactions (no join, message or invite creation).
- Broadcast channels from the personal account's dialogs ONLY.
- Record only channels where both are confirmed admins.
- Private ID/title never printed or copied to plain registry.
- All writes use a service-role-only Supabase RPC -> Vault.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from collections import Counter
from urllib.parse import urlparse

import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel
from audit_mrxpronos_canal_bot import find_exact_bot, Telegram

BOT_USERNAME = "mrxpronos_canal_bot"
MAX_CHANNELS = 1000


def env(name):
    return (os.environ.get(name) or "").strip()


def role_from_permissions(entity, permissions):
    if getattr(entity, "creator", False) or getattr(permissions, "is_creator", False):
        return "creator"
    if getattr(entity, "admin_rights", None) or getattr(permissions, "is_admin", False):
        return "administrator"
    return None


def classify_public(username):
    return bool(username and username.strip())


def save_row(row, session):
    base = env("SUPABASE_URL").rstrip("/")
    if urlparse(base).scheme != "https" or not base.endswith(".supabase.co"):
        raise RuntimeError("invalid_supabase_target")
    r = session.post(
        base + "/rest/v1/rpc/mrx_telegram_inventory_upsert",
        json={"p_channel": row}, timeout=(8, 25)
    )
    if r.status_code != 200:
        # Only SQLSTATE is safe; never dump PostgREST descriptions (may contain IDs).
        try:
            pgcode = str(r.json().get("code") or "")
        except (ValueError, AttributeError):
            pgcode = ""
        if not pgcode.isalnum() or len(pgcode) > 10:
            pgcode = "unknown"
        possible_messages = {
            "Not authorized to register channel": "unapproved_rpc_role",
            "Unexpected Telegram bot": "unexpected_bot",
            "Invalid Telegram channel identity": "invalid_telegram_identity",
            "Unverified Telegram admin roles": "unverified_admin_roles",
            "Invalid public channel username": "invalid_public_username",
            "Missing server-side encryption index key": "vault_index_key_missing",
        }
        try:
            detail = possible_messages.get(str(r.json().get("message") or ""), "other")
        except (AttributeError, ValueError):
            detail = "other"
        raise RuntimeError("secure_registry_write_http_" + str(r.status_code) + "_sqlstate_" + pgcode + "_reason_" + detail)
    try:
        if r.json() is not True:
            raise ValueError("registry_rpc_not_confirmed")
    except ValueError:
        raise RuntimeError("secure_registry_result_invalid") from None


async def scan():
    api_id = env("TG_API_ID")
    api_hash = env("TG_API_HASH")
    string = env("TG_SESSION_STRING") or env("TG_STRING_SESSION") or env("TG_STREAM_SESSION")
    if not api_id.isdigit() or not api_hash or not string:
        raise RuntimeError("personal_telegram_session_missing")
    if not env("SUPABASE_SERVICE_ROLE_KEY") or not env("SUPABASE_URL"):
        raise RuntimeError("supabase_credentials_missing")

    bot_api, bot, _ = find_exact_bot()
    if bot_api is None or bot.get("username", "").lower() != BOT_USERNAME:
        raise RuntimeError("requested_bot_identity_not_verified")

    http = requests.Session()
    key = env("SUPABASE_SERVICE_ROLE_KEY")
    http.headers.update({"apikey":key, "Authorization":"Bearer "+key,
                         "Content-Type":"application/json"})

    counts = Counter()
    public_rows = []
    client = TelegramClient(StringSession(string), int(api_id), api_hash,
                            request_retries=1, connection_retries=2,
                            flood_sleep_threshold=0, receive_updates=False)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("personal_telegram_session_not_authorized")
        me = await client.get_me()
        if not me or me.bot:
            raise RuntimeError("personal_session_is_not_user")

        async for dialog in client.iter_dialogs():
            channel = dialog.entity
            if not isinstance(channel, Channel) or not channel.broadcast:
                continue
            counts["broadcast_seen"] += 1
            if counts["broadcast_seen"] > MAX_CHANNELS:
                raise RuntimeError("channel_limit_exceeded")
            try:
                # Verify account permissions on Telegram, not just channel membership.
                permissions = await client.get_permissions(channel, me)
            except Exception as exc:
                counts["personal_role_unavailable"] += 1
                print("PERSONAL_ADMIN_CHECK_UNAVAILABLE", type(exc).__name__)
                continue
            user_role = role_from_permissions(channel, permissions)
            if user_role is None:
                counts["personal_not_admin"] += 1
                continue
            counts["personal_admin"] += 1

            cid = "-100" + str(channel.id)
            try:
                member = bot_api.call("getChatMember", {"chat_id":cid,"user_id":int(bot["id"])})
                if member.get("status") not in ("administrator","creator"):
                    counts["bot_not_admin"] += 1
                    continue
                chat = bot_api.call("getChat", {"chat_id":cid})
            except RuntimeError:
                counts["bot_check_unavailable"] += 1
                continue
            if chat.get("type") != "channel" or str(chat.get("id")) != cid:
                counts["bot_check_unavailable"] += 1
                continue

            status = member["status"]
            can_post = status == "creator" or member.get("can_post_messages") is True
            username = (chat.get("username") or "").lstrip("@") or None
            title = str(chat.get("title") or "").strip()
            if not title:
                counts["missing_title"] += 1
                continue
            payload = {
                "bot_username": BOT_USERNAME,
                "bot_id": int(bot["id"]),
                "channel_id": cid,
                "title": title,
                "username": username,
                "user_role": user_role,
                "bot_role": status,
                "bot_can_post": bool(can_post),
            }
            save_row(payload, http)
            counts["verified_and_encrypted"] += 1
            if classify_public(username):
                counts["public"] += 1
                public_rows.append({
                    "title": title,
                    "username": "@"+username,
                    "url": "https://t.me/"+username,
                    "user_role": user_role,
                    "bot_role": status,
                    "bot_can_post": bool(can_post),
                })
            else:
                counts["private"] += 1
    finally:
        await client.disconnect()
        http.close()

    # Never leak private titles, IDs or invitation links in public Actions.
    public_rows.sort(key=lambda x:x["username"].casefold())
    print("TELEGRAM_ADMIN_INVENTORY_JSON", json.dumps({
        "bot":"@"+BOT_USERNAME,
        "scope":"personal broadcast dialogs; both administrators verified",
        "personal_broadcast_seen":counts["broadcast_seen"],
        "personal_admin":counts["personal_admin"],
        "confirmed_both_admins_and_encrypted":counts["verified_and_encrypted"],
        "public_count":counts["public"],
        "private_count":counts["private"],
        "bot_not_admin":counts["bot_not_admin"],
        "bot_checks_unavailable":counts["bot_check_unavailable"],
        "personal_role_unavailable":counts["personal_role_unavailable"],
        "public_channels":public_rows,
        "broadcast_enabled_by_scan": False
    },ensure_ascii=False))
    if counts["personal_role_unavailable"] or counts["bot_check_unavailable"]:
        print("WARNING_INCOMPLETE_PERMISSION_CHECKS")
    return 0


def main():
    try:
        return asyncio.run(scan())
    except Exception as exc:
        # Never print arbitrary exception messages containing private IDs or tokens.
        approved = {
            "personal_telegram_session_missing", "supabase_credentials_missing",
            "personal_telegram_session_not_authorized", "personal_session_is_not_user",
            "requested_bot_identity_not_verified", "invalid_supabase_target",
            "secure_registry_result_invalid", "registry_rpc_not_confirmed",
            "channel_limit_exceeded"
        }
        msg = str(exc)
        code = msg if msg in approved or (msg.startswith("secure_registry_write_http_")
                    and all(c.isalnum() or c == "_" for c in msg) and len(msg) < 120) else "unknown"
        print("::error::ADMIN_INVENTORY_FAILED",type(exc).__name__,code)
        return 1

if __name__ == "__main__":
    sys.exit(main())
