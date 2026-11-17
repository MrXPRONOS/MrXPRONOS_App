#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Telegram audit -> private Supabase registry (no Telegram publication).

All titles and IDs (especially private channels) are sent directly to the
service-role-only Supabase table. Never print sensitive row payloads.
Each destination is confirmed with @mrxpronos_canal_bot using getChat /
getChatMember, not inferred solely from the user's Telegram session.

Rows are disabled for broadcast by default; the table never stores tokens.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import requests

from audit_mrxpronos_canal_bot import (
    TARGET_USERNAME,
    Telegram,
    configured_candidates,
    find_exact_bot,
    telethon_candidates,
)

SUPABASE_TABLE = "telegram_channel_registry"


def safe_telegram_lookup(api: Telegram, method: str, params: dict):
    try:
        return api.call(method, params)
    except RuntimeError:
        return None


def collect():
    api, me, _detected = find_exact_bot()
    if api is None or not isinstance(me.get("id"), int):
        raise RuntimeError("exact_target_bot_token_not_found")
    bot_id = int(me["id"])
    possible, secret_sources = configured_candidates()
    dialogs, scan_status = asyncio.run(telethon_candidates())
    print("DISCOVERY", "telegram_session_status", scan_status, "dialogs", len(dialogs),
          "configured_sources", len(secret_sources))
    for ch in dialogs:
        key = ch["chat_id"].strip().casefold()
        if key not in possible:
            possible[key] = {"chat_id": ch["chat_id"], "sources": ["personal_dialogs"]}

    rows_by_id = {}
    unavailable = 0
    for entry in possible.values():
        candidate = entry["chat_id"]
        # A failed check is not equivalent to a channel where the bot is not admin.
        membership = safe_telegram_lookup(api, "getChatMember",
                                           {"chat_id": candidate, "user_id": bot_id})
        if membership is None:
            unavailable += 1
            continue
        status = membership.get("status")
        if status not in ("administrator", "creator"):
            continue
        channel = safe_telegram_lookup(api, "getChat", {"chat_id": candidate})
        if channel is None or channel.get("type") != "channel":
            unavailable += 1
            continue
        cid = channel.get("id")
        if not isinstance(cid, int):
            continue
        username = str(channel.get("username") or "").strip().lstrip("@") or None
        can_post = status == "creator" or membership.get("can_post_messages") is True
        rows_by_id[cid] = {
            "bot_id": bot_id,
            "channel_id": cid,
            "title": str(channel.get("title") or ""),
            "username": username,
            "is_private": not bool(username),
            "bot_status": status,
            "can_post_messages": bool(can_post),
            "source": "telegram_verified_bot_api",
            "last_verified_at": "now()",  # replaced by Postgres default on insert
        }
        # Restraint on Telegram API requests and logging.
        time.sleep(0.04)

    rows = list(rows_by_id.values())
    for row in rows:
        row.pop("last_verified_at", None)
    print("VERIFIED_DESTINATIONS", len(rows), "private", sum(r["is_private"] for r in rows),
          "public", sum(not r["is_private"] for r in rows),
          "unavailable_checks", unavailable)
    return rows, scan_status


def save(rows):
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("server_side_supabase_credentials_missing")
    if not url.startswith("https://") or not url.endswith(".supabase.co"):
        raise RuntimeError("invalid_supabase_url")
    if not rows:
        raise RuntimeError("no_verified_destinations_to_save")
    try:
        r = requests.post(
            url + "/rest/v1/" + SUPABASE_TABLE,
            params={"on_conflict": "bot_id,channel_id"},
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=rows,
            timeout=(10, 40),
        )
    except requests.RequestException:
        raise RuntimeError("private_registry_transport_error") from None
    if r.status_code not in (200, 201, 204):
        # Do not dump server responses which could contain channel data.
        raise RuntimeError("private_registry_http_" + str(r.status_code))
    print("PRIVATE_REGISTRY_UPSERT_CONFIRMED", len(rows))
    print("BROADCAST_DISABLED_BY_DEFAULT: no messages were sent")


def main():
    try:
        rows, scan_status = collect()
        save(rows)
    except RuntimeError as e:
        print("::error::REGISTRY_FAILURE", str(e))
        return 1
    if scan_status != "complete_personal_dialog_scan":
        print("WARNING: discovery is partial:", scan_status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
