"""Read-only post-repair inventory of the OWNER'S Telegram account.

No CreateChannel, InviteToChannel, EditAdmin or send calls occur here.
Print only category booleans, error class names, and public bot username.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from scripts.telegram_owner_channel_repair import (
    BOT_USERNAME, STAGE_TITLE, STAGE_MARKER, check_bot,
    legacy_handle, valid_stage_id, select_stage,
)


@dataclass
class Inventory:
    session: str = "unchecked"
    stage_reference: str = "unchecked"
    stage_existing: str = "unchecked"
    stage_owner: str = "unchecked"
    stage_bot: str = "unchecked"
    crypto_resolved: str = "unchecked"
    crypto_owner: str = "unchecked"
    crypto_bot: str = "unchecked"


def own_permissions(permissions):
    if getattr(permissions, "is_creator", False):
        return "creator"
    if getattr(permissions, "is_admin", False):
        return ("admin_promote" if getattr(permissions, "add_admins", False)
                else "admin_no_promote")
    return "not_admin"


def bot_permissions(permissions):
    if getattr(permissions, "is_creator", False):
        return "creator"
    if getattr(permissions, "is_admin", False):
        return ("admin_post" if getattr(permissions, "post_messages", False)
                else "admin_no_post")
    return "not_admin"


async def run(env=None):
    from telethon import TelegramClient, functions, utils
    from telethon.sessions import StringSession
    env = os.environ if env is None else env
    result = Inventory()
    configured = (env.get("FORMATION_STAGE_CHAT") or "").strip()
    result.stage_reference = "valid_numeric" if valid_stage_id(configured) else "missing_or_invalid"
    legacy = legacy_handle(env.get("ACTU_CRYPTO_CHAT_ID", ""))
    if not legacy:
        result.crypto_resolved = "missing_config"
    credentials = [str(env.get(k) or "").strip()
                   for k in ("TG_STRING_SESSION", "TG_API_ID", "TG_API_HASH")]
    if not all(credentials):
        raise RuntimeError("personal_session_credentials_missing")
    bot_identity = check_bot(env.get("FORMATION_BOT_TOKEN", ""))
    client = TelegramClient(StringSession(credentials[0]), int(credentials[1]), credentials[2],
                            flood_sleep_threshold=0, request_retries=0,
                            connection_retries=0, timeout=15)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            result.session = "revoked"
            return result
        result.session = "authorized"
        owner = await client.get_me()
        bot = await client.get_entity("@" + BOT_USERNAME)
        if not getattr(bot, "bot", False) or bot.id != bot_identity["id"]:
            raise RuntimeError("bot_identity_mismatch")
        dialogs = [x.entity async for x in client.iter_dialogs(limit=600)]
        title_matches = [d for d in dialogs
                         if getattr(d, "broadcast", False)
                         and not getattr(d, "username", None)
                         and getattr(d, "title", "") == STAGE_TITLE]
        try:
            stage, mode = select_stage(dialogs, configured)
            if stage is None:
                result.stage_existing = "not_found_in_owner_dialogs"
            elif mode == "candidate":
                full = await client(functions.channels.GetFullChannelRequest(stage))
                if STAGE_MARKER not in str(getattr(full.full_chat, "about", "") or ""):
                    result.stage_existing = "title_found_marker_not_verified"
                    stage = None
                else:
                    result.stage_existing = ("marked_candidate_relink_needed"
                                             if str(utils.get_peer_id(stage)) != configured
                                             else "marked_configured")
            else:
                result.stage_existing = "configured_in_owner_dialogs"
            if stage is not None:
                try:
                    result.stage_owner = own_permissions(
                        await client.get_permissions(stage, owner))
                except Exception as exc:
                    result.stage_owner = "error_" + type(exc).__name__
                try:
                    result.stage_bot = bot_permissions(
                        await client.get_permissions(stage, bot))
                except Exception as exc:
                    result.stage_bot = "error_" + type(exc).__name__
        except Exception as exc:
            result.stage_existing = "error_" + type(exc).__name__
        if legacy:
            try:
                old = await client.get_entity(legacy)
                if not getattr(old, "broadcast", False):
                    result.crypto_resolved = "not_broadcast"
                else:
                    result.crypto_resolved = "exists"
                    try:
                        result.crypto_owner = own_permissions(
                            await client.get_permissions(old, owner))
                    except Exception as exc:
                        result.crypto_owner = "error_" + type(exc).__name__
                    try:
                        result.crypto_bot = bot_permissions(
                            await client.get_permissions(old, bot))
                    except Exception as exc:
                        result.crypto_bot = "error_" + type(exc).__name__
            except Exception as exc:
                result.crypto_resolved = "error_" + type(exc).__name__
    finally:
        await client.disconnect()
    return result


def main():
    try:
        r = asyncio.run(run())
        # No private IDs, bot token, invite links or raw exception bodies.
        for key, value in vars(r).items():
            print("TELEGRAM_OWNER_AUDIT", key + "=" + value, flush=True)
        return 0
    except Exception as exc:
        print("TELEGRAM_OWNER_AUDIT_ABORTED", type(exc).__name__, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
