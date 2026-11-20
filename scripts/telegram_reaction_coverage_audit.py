#!/usr/bin/env python3
"""Read-only health audit of Telegram channel reaction coverage.

This script NEVER posts or reacts. Bot tokens are used only for getMe,
getWebhookInfo, getChat and getChatMember; no token URLs or credentials logged.
"""
from __future__ import annotations

import os
import sys
from telegram_reactions_github import APIError, D1, telegram_call

EXPECTED_BOT = "cineradarfr_bot"
CANDIDATE_TOKEN_NAMES = (
    "CINE_RADAR_BOT_TOKEN", "CINEX_BOT_TOKEN", "TELEGRAM_BOT_TOKEN",
    "EDITORIAL_TELEGRAM_BOT_TOKEN", "PARTNERSHIP_BOT_TOKEN",
    "MRXPRONOS_CANAL_BOT_TOKEN",
)
EXPECTED_WEBHOOK = "https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/telegram"


def locate_radar_bot(env, transport):
    seen = set()
    for name in CANDIDATE_TOKEN_NAMES:
        token = env.get(name, "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        try:
            status, response = telegram_call(token, "getMe", {}, transport)
        except APIError:
            continue
        me = response.get("result") or {}
        if status == 200 and response.get("ok") and (
            str(me.get("username") or "").casefold() == EXPECTED_BOT
        ) and isinstance(me.get("id"), int):
            return token, me["id"]
    return "", None


def reaction_policy(info):
    available = info.get("available_reactions")
    if available is None:
        return "unspecified"
    if not isinstance(available, list):
        return "unknown"
    if not available:
        return "disabled"
    emojis = {str(x.get("emoji") or "") for x in available if isinstance(x, dict)}
    return "heart_and_thumb_allowed" if {"❤️", "👍"}.issubset(emojis) else "restricted"


def audit(env, transport):
    token, bot_id = locate_radar_bot(env, transport)
    if not token:
        print("reaction_coverage_audit: radar_bot_token_not_available_in_github")
        return
    status, webhook = telegram_call(token, "getWebhookInfo", {}, transport)
    current = webhook.get("result") or {}
    valid_webhook = (status == 200 and webhook.get("ok") is True
                     and current.get("url") == EXPECTED_WEBHOOK
                     and "channel_post" in (current.get("allowed_updates") or []))
    print(f"radar_webhook_valid={bool(valid_webhook)} "
          f"pending_updates={int(current.get('pending_update_count') or 0)}")
    db = D1(env.get("CLOUDFLARE_API_TOKEN") or env.get("CF_API_TOKEN") or "",
            env.get("CLOUDFLARE_ACCOUNT_ID") or "", transport)
    rows = db.query(
        "SELECT kind,username,chat_id FROM radar_primary_channels ORDER BY kind"
    ).get("results") or []
    for row in rows:
        chat_id = row.get("chat_id")
        kind = str(row.get("kind") or "other")
        if not chat_id:
            print(f"channel={kind} status=unbound")
            continue
        try:
            status, ch = telegram_call(token, "getChat", {"chat_id": chat_id}, transport)
            chat = ch.get("result") or {}
            if status != 200 or ch.get("ok") is not True:
                print(f"channel={kind} get_chat=failed_{status}")
                continue
            status, member = telegram_call(token, "getChatMember", {
                "chat_id": chat_id, "user_id": bot_id,
            }, transport)
            membership = str((member.get("result") or {}).get("status") or "unavailable")
            present = membership in ("administrator", "creator")
            count = db.query(
                "SELECT COUNT(*) AS n, MAX(observed_at) AS last_seen "
                "FROM channel_reaction_posts WHERE chat_id=?", (str(chat_id),)
            ).get("results") or []
            last = count[0] if count else {}
            print(f"channel={kind} radar_admin={present} "
                  f"chat_type={str(chat.get('type') or 'unknown')} "
                  f"reactions={reaction_policy(chat)} "
                  f"posts_in_reaction_ledger={int(last.get('n') or 0)} "
                  f"last_reaction_ledger_post={str(last.get('last_seen') or 'none')}")
        except APIError:
            print(f"channel={kind} audit=temporarily_unavailable")


if __name__ == "__main__":
    try:
        audit(dict(os.environ), __import__(
            "telegram_reactions_github"
        )._request_json)
    except APIError as e:
        # The error text comes exclusively from our sanitized own client.
        print("REACTION_COVERAGE_AUDIT_ERROR:", str(e), file=sys.stderr)
        sys.exit(1)
