#!/usr/bin/env python3
"""Read-only GitHub-only Telegram channel reaction coverage audit.

Loads an authenticated encrypted GitHub history snapshot. Checks channel/bot
administrator rights via Telegram only. Never calls Cloudflare, sends Telegram
messages, or mutates the encrypted snapshot. No channel IDs, tokens, or user
identifiers are printed. The old ledger contains historical channels that may
not belong to CineRadar and must not be automatically enrolled.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import time

from scripts.cineradar_reaction_core import (
    APIError, configured_tokens, telegram_call, verify_primary_bots,
)
from scripts.cineradar_reactions_github_only import PRIMARY_PUBLIC_CHANNELS, allowed_channels
from scripts.cineradar_reaction_store import ReactionVault, load


def policy_for(channel_info):
    available = channel_info.get("available_reactions")
    if available is None:
        return "unspecified"
    if not isinstance(available, list):
        return "unknown"
    if not available:
        return "disabled"
    emojis = {
        str(item.get("emoji") or "") for item in available
        if isinstance(item, dict) and item.get("type") == "emoji"
    }
    return "heart_thumb_allowed" if {"❤️", "👍"}.issubset(emojis) else "restricted"


def bot_coverage(label, token, channels):
    """Independent per-bot Telegram API session; only admin rights qualify."""
    status, resp = telegram_call(token, "getMe", {})
    profile = resp.get("result") or {}
    if status != 200 or resp.get("ok") is not True or not profile.get("is_bot"):
        return {"label": label, "id": None, "admin": set(), "no_webhook": False, "errors": len(channels)}
    bot_id = profile.get("id")
    if not isinstance(bot_id, int):
        return {"label": label, "id": None, "admin": set(), "no_webhook": False, "errors": len(channels)}
    status, resp = telegram_call(token, "getWebhookInfo", {})
    no_webhook = (status == 200 and resp.get("ok") is True
                  and not (resp.get("result") or {}).get("url"))
    admin, errors = set(), 0
    for channel_id in sorted(channels):
        try:
            status, response = telegram_call(
                token, "getChatMember",
                {"chat_id": channel_id, "user_id": bot_id},
            )
            if (status == 200 and response.get("ok") is True
                and (response.get("result") or {}).get("status")
                in ("administrator", "creator")):
                admin.add(channel_id)
            elif status in (429, 0, 500, 502, 503, 504):
                errors += 1
        except APIError:
            errors += 1
        time.sleep(0.14)
    return {"label": label, "id": bot_id, "admin": admin,
            "no_webhook": no_webhook, "errors": errors}


def audit(env):
    vault = ReactionVault(branch="main")
    db, _, sha = load(vault)
    try:
        rows = db.query(
            "SELECT chat_id, COUNT(*) AS posts FROM channel_reaction_posts "
            "GROUP BY chat_id ORDER BY chat_id"
        )["results"]
        historical = {str(x["chat_id"]): int(x["posts"]) for x in rows}
        official = allowed_channels(db, env)
        if len(official) != len(PRIMARY_PUBLIC_CHANNELS):
            raise RuntimeError("Official channel identity check incomplete")
        all_channels = set(historical) | official
        candidates = [("slot_%02d" % slot, token)
                      for slot, token in sorted(configured_tokens(env).items())]
        primary = verify_primary_bots(env)
        candidates += [("primary_" + role, token)
                       for role, token in sorted(primary.items())]
        distinct = {}
        for name, token in candidates:
            if token not in distinct:
                distinct[token] = name
        if not distinct:
            raise RuntimeError("No verified reaction bot credentials")
        reports = []
        # Read-only Telegram membership checks with low concurrency; do not
        # count a temporary network failure as confirmed access.
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {
                executor.submit(bot_coverage, name, token, all_channels): name
                for token, name in distinct.items()
            }
            for future in as_completed(future_map):
                try:
                    reports.append(future.result())
                except Exception:
                    reports.append({"label": future_map[future], "id": None,
                                    "admin": set(), "no_webhook": False,
                                    "errors": len(all_channels)})
        # Multiple environment secrets pointing to the same bot count once.
        unique = {}
        for r in reports:
            if r["id"] is not None and r["id"] not in unique:
                unique[r["id"]] = r
        reports = list(unique.values())
        administrated_any = set().union(*(r["admin"] for r in reports)) if reports else set()
        pollable_any = set().union(*(r["admin"] for r in reports if r["no_webhook"])) if reports else set()
        full_official_observer = any(official <= r["admin"] and r["no_webhook"]
                                     for r in reports)
        unknown_checks = sum(r["errors"] for r in reports)
        print("GITHUB_REACTION_AUDIT_BEGIN")
        print("source=encrypted_github_only telegram_api=getMe_getChatMember_getWebhookInfo")
        print("historical_channels=%d historical_posts=%d official_channels=%d historical_outside_official=%d"
              % (len(historical), sum(historical.values()), len(official), len(set(historical)-official)))
        print("verified_unique_bots=%d official_observer_full_admin=%s"
              % (len(reports), str(full_official_observer).lower()))
        print("historical_channels_with_some_bot_admin=%d/%d"
              % (len(administrated_any & set(historical)), len(historical)))
        print("historical_channels_with_any_webhook_free_admin=%d/%d"
              % (len(pollable_any & set(historical)), len(historical)))
        print("membership_checks_temporary_errors=%d" % unknown_checks)
        channel_names = dict(zip(PRIMARY_PUBLIC_CHANNELS, sorted(official)))
        # Alphabetically zipped IDs are NOT reliable kind mapping.
        # Reverify official username through Telegram getChat.
        main_token = env.get("CINE_RADAR_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN") or ""
        for username in PRIMARY_PUBLIC_CHANNELS:
            status, resp = telegram_call(main_token, "getChat", {"chat_id": "@"+username})
            chat = resp.get("result") or {}
            if status != 200 or not resp.get("ok") or str(chat.get("username") or "").casefold() != username.casefold():
                print("official_channel=%s state=unverified" % username)
                continue
            channel_id = str(chat["id"])
            admins = sum(channel_id in r["admin"] for r in reports)
            pollers = sum(channel_id in r["admin"] and r["no_webhook"] for r in reports)
            print("official_channel=%s known_posts=%d admin_reaction_bots=%d independent_admin_observers=%d reaction_policy=%s"
                  % (username, historical.get(channel_id, 0), admins, pollers, policy_for(chat)))
        print("monitored_by_running_engine=%d/%d" % (len(official), len(all_channels)))
        print("all_history_monitored=%s" % str(all_channels <= official).lower())
        print("GITHUB_REACTION_AUDIT_END")
        return 0
    finally:
        db.connection.close()


if __name__ == "__main__":
    try:
        sys.exit(audit(dict(os.environ)))
    except Exception as exc:
        # Only class name to avoid leaking sensitive values into the public repo logs.
        print("REACTION_COVERAGE_GITHUB_AUDIT_ERROR:", type(exc).__name__, file=sys.stderr)
        sys.exit(1)
