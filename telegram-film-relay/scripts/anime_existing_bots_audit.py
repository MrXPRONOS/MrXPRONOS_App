"""Read-only inventory of EXISTING CineX bots and Anime-source permissions.

This is a diagnostic, NOT a bot creation, admin grant, media transfer, webhook
replacement, update consumer or source invitation. It respects the already
owner-confirmed private stock. Output never contains bot tokens, channel IDs,
usernames, source names, download links or message contents.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys

from film_relay.anime_bot_transport import AnimeBotTransport

EXISTING_TOKENS = {
    "anime": "ANIME_BOT_TOKEN",
    "publisher": "CINEX_PUBLISH_BOT_TOKEN",
    "radar": "CINEX_RADAR_BOT_TOKEN",
    "desir": "DESIR_BOT_TOKEN",
    "legacy": "FOOTBALL_NEWS_BOT_TOKEN",
    "telegram": "TELEGRAM_BOT_TOKEN",
    "series": "SERIES_BOT_TOKEN",
    "action": "ACTION_BOT_TOKEN",
    "comedie": "COMEDIE_BOT_TOKEN",
}
OWNER_STOCK_ID = "-1004353068771"
OWNER_STOCK_SHA = "57b1f0a97d7db124ab9f72f470f7d63b92960e06b876397795e5780f5c5cc2b8"


def _sources(env):
    from film_relay.source_channels import source_list
    source_raw = (
        env.get("ANIME_SOURCE_CHANNEL", "") or env.get("ANIME_SOURCE_CHANNELS", "")
    )
    if not source_raw.strip():
        return []
    return source_list(source_raw, max_sources=12)


def stock_id(env):
    """Do not substitute a different private stock from account discovery."""
    if hashlib.sha256(OWNER_STOCK_ID.encode()).hexdigest() != OWNER_STOCK_SHA:
        raise RuntimeError("Owner-confirmed CineRadar private-stock digest invalid.")
    configured = str(env.get("CINEX_UNIFIED_PRIVATE_CHANNEL", "") or "").strip()
    if configured and configured != OWNER_STOCK_ID:
        raise RuntimeError("Configured stock is not the owner-confirmed CineRadar stock.")
    return OWNER_STOCK_ID


async def _member(bot, identity, chat, *, destination):
    if not chat:
        return False
    try:
        info = await bot.call("getChatMember", {
            "chat_id": str(chat), "user_id": str(identity.id),
        })
    except Exception:
        return False
    role = info.get("status")
    if role not in ("administrator", "creator"):
        return False
    return not destination or role == "creator" or (
        info.get("can_post_messages") is True
    )


async def audit_bot_candidates(env=None, *, transport_factory=AnimeBotTransport):
    env = os.environ if env is None else env
    source_channels = _sources(env)
    private = env.get("ANIME_PRIVATE_CHANNEL", "")
    public = env.get("ANIME_PUBLIC_CHANNEL", "") or "@CineXAnimeFR"
    central = stock_id(env)
    configured_tokens = []
    seen = set()
    for label, key in EXISTING_TOKENS.items():
        token = str(env.get(key, "") or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        configured_tokens.append((label, token))

    report = {
        "audit_only": True,
        "actions_taken": 0,
        "stock_protected_from_deletion": True,
        "source_channels_configured": len(source_channels),
        "existing_bot_tokens_checked": len(configured_tokens),
        "bots": [],
        "source_capable_bot_count": 0,
        "bot_only_polling_candidates": 0,
        "publication_ready": False,
        "blockers": [],
    }
    if not source_channels:
        report["blockers"].append("anime_sources_not_configured")
    if not private or not str(private).startswith("-100"):
        report["blockers"].append("anime_private_channel_missing")
    if not configured_tokens:
        report["blockers"].append("existing_bot_tokens_unavailable")
    for label, token in configured_tokens:
        row = {
            "label": label, "identity_valid": False,
            "source_admin_count": 0, "all_sources_verified": False,
            "anime_private_publish": False,
            "anime_public_publish": False,
            "central_stock_publish": False,
            "webhook_active": None,
            "usable_for_getupdates": False,
        }
        try:
            bot = transport_factory(token)
            who = await bot.identity()
            row["identity_valid"] = who.id > 0
            webhook_info = await bot.call("getWebhookInfo")
            row["webhook_active"] = bool(webhook_info.get("url"))
            for chat in source_channels:
                if await _member(bot, who, chat, destination=False):
                    row["source_admin_count"] += 1
            row["all_sources_verified"] = bool(source_channels) and (
                row["source_admin_count"] == len(source_channels))
            row["anime_private_publish"] = await _member(
                bot, who, private, destination=True)
            row["anime_public_publish"] = await _member(
                bot, who, public, destination=True)
            row["central_stock_publish"] = await _member(
                bot, who, central, destination=True)
            if row["all_sources_verified"]:
                report["source_capable_bot_count"] += 1
            row["usable_for_getupdates"] = bool(
                row["all_sources_verified"]
                and row["anime_private_publish"]
                and row["anime_public_publish"]
                and row["central_stock_publish"]
                and row["webhook_active"] is False)
            if row["usable_for_getupdates"]:
                report["bot_only_polling_candidates"] += 1
        except Exception:
            row["failure"] = "bot_api_read_only_check_failed"
        report["bots"].append(row)
    if report["bot_only_polling_candidates"] == 0:
        report["blockers"].append("no_existing_bot_with_source_and_destination_access")
    if any(x["webhook_active"] for x in report["bots"]):
        report["blockers"].append("webhook_active_on_some_bots_do_not_poll_those_tokens")
    report["publication_ready"] = False  # Never infer state/dedup/rights from admin access.
    return report


def main():
    try:
        report = asyncio.run(audit_bot_candidates())
        print("CINEX_ANIME_BOT_EXISTING_ACCESS",
              json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print("CINEX_ANIME_BOT_AUDIT_UNAVAILABLE", type(exc).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
