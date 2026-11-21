"""Provision one owner-only private CineX stock channel, without sending media.

Run only under the shared MTProto cooldown + Github Actions concurrency gate.
Re-use an existing channel ONLY when its exact title AND about marker match,
the connected user is the creator, and there are no unknown participants.
No invite links, subscriber joins, tokens or media are exposed in logs.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import requests

TITLE = "CinéX — Stock privé"
MARKER = "CINEX_PRIVATE_STOCK_V1 owner-only source vault"
DATABASE_ID = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"
ACCOUNT_ID = "9c86118191b804d91b5f5b2c89114999"
DDL = (
    """CREATE TABLE IF NOT EXISTS cine_private_stock_config (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        stock_chat_id TEXT NOT NULL CHECK(stock_chat_id GLOB '-100[0-9]*'),
        owner_id INTEGER NOT NULL CHECK(owner_id>0),
        radar_bot_id INTEGER NOT NULL CHECK(radar_bot_id>0),
        publisher_bot_id INTEGER CHECK(publisher_bot_id IS NULL OR publisher_bot_id>0),
        ready INTEGER NOT NULL DEFAULT 0 CHECK(ready IN(0,1)),
        verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
)


def bot_identity(token: str):
    """Read-only Telegram Bot API identity; NEVER log the token or the URL."""
    if not token:
        return None
    try:
        response = requests.post(
            "https://api.telegram.org/bot" + token + "/getMe",
            json={}, timeout=15,
        )
        result = response.json()
    except Exception as exc:
        raise RuntimeError("telegram_bot_identity_unavailable") from exc
    item = result.get("result") or {}
    if not response.ok or not result.get("ok") or item.get("is_bot") is not True:
        raise RuntimeError("telegram_bot_identity_unverified")
    if not isinstance(item.get("id"), int) or not item.get("username"):
        raise RuntimeError("telegram_bot_identity_incomplete")
    return item


def configured_bots(env=None):
    env = os.environ if env is None else env
    radar = None
    for key in ("CINEX_RADAR_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"):
        token = env.get(key) or ""
        if not token:
            continue
        value = bot_identity(token)
        if str(value["username"]).casefold() == "cineradarfr_bot":
            radar = value
            break
    if radar is None:
        raise RuntimeError("cineradar_identity_not_verified")
    results = [radar]
    pub_token = env.get("CINEX_PUBLISH_BOT_TOKEN") or ""
    pub_name = str(env.get("CINEX_PUBLISH_BOT_USERNAME") or "").lstrip("@").casefold()
    if pub_token:
        if not pub_name:
            raise RuntimeError("publisher_username_required_for_bot_validation")
        pub = bot_identity(pub_token)
        if str(pub["username"]).casefold() != pub_name:
            raise RuntimeError("publisher_identity_mismatch")
        if pub["id"] != radar["id"]:
            results.append(pub)
    return results


def d1_query(sql: str, params=None):
    token = os.environ.get("CLOUDFLARE_API_TOKEN") or ""
    if not token:
        raise RuntimeError("d1_api_token_missing")
    try:
        result = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query",
            json={"sql": sql, "params": list(params or [])},
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            timeout=25,
        )
        payload = result.json()
    except Exception as exc:
        raise RuntimeError("private_d1_query_unavailable") from exc
    if not result.ok or not payload.get("success"):
        raise RuntimeError("private_d1_query_failed")
    values = payload.get("result") or []
    if any(x.get("success") is False for x in values):
        raise RuntimeError("private_d1_statement_failed")
    return values[0].get("results", []) if values else []


def registered_stock():
    try:
        rows = d1_query("SELECT stock_chat_id,owner_id,radar_bot_id,ready FROM cine_private_stock_config WHERE singleton=1")
    except RuntimeError:
        return None
    return rows[0] if rows else None


def store_stock(chat_id: str, owner_id: int, radar_id: int, publisher_id=None):
    for ddl in DDL:
        d1_query(ddl)
    prior = registered_stock()
    if prior is not None and (str(prior["stock_chat_id"]) != str(chat_id)
                               or int(prior["owner_id"]) != int(owner_id)):
        raise RuntimeError("d1_stock_already_bound_to_another_channel")
    sql = ("""INSERT INTO cine_private_stock_config(
       singleton,stock_chat_id,owner_id,radar_bot_id,publisher_bot_id,ready)
       VALUES(1,?,?,?,?,1)
       ON CONFLICT(singleton) DO UPDATE SET
       radar_bot_id=excluded.radar_bot_id,
       publisher_bot_id=excluded.publisher_bot_id,
       ready=1,verified_at=CURRENT_TIMESTAMP
       WHERE cine_private_stock_config.stock_chat_id=excluded.stock_chat_id
       AND cine_private_stock_config.owner_id=excluded.owner_id""")
    d1_query(sql, [str(chat_id), int(owner_id), int(radar_id),
                   int(publisher_id) if publisher_id is not None else None])
    verified = registered_stock()
    if not verified or str(verified["stock_chat_id"]) != str(chat_id) or int(verified["ready"]) != 1:
        raise RuntimeError("stock_config_not_confirmed")


async def verify_members(client, channel, owner_id: int, bots):
    allowed = {owner_id} | {int(x["id"]) for x in bots}
    seen_owner = False
    count = 0
    async for participant in client.iter_participants(channel, limit=40):
        count += 1
        if int(participant.id) not in allowed:
            raise RuntimeError("unknown_private_stock_member")
        if participant.id == owner_id:
            seen_owner = True
    if count >= 40 or not seen_owner:
        raise RuntimeError("stock_member_verification_incomplete")
    return count


async def provision(*, apply=False):
    # Validate the official bots using Bot API BEFORE opening the personal user session.
    bots = configured_bots()
    if not apply:
        print("CINEX_PRIVATE_STOCK_PREFLIGHT_OK", "approved_bots", len(bots),
              "personal_session_opened", False)
        return {"created": False, "ready": False}
    api_id = os.getenv("TG_API_ID") or ""
    api_hash = os.getenv("TG_API_HASH") or ""
    session = os.getenv("TG_STRING_SESSION") or ""
    if not api_id.isdecimal() or not api_hash or not session:
        raise RuntimeError("personal_session_not_configured")
    # Verify Cloudflare write access first, so a successful channel can be
    # durably registered without disclosing its private chat ID in GitHub.
    for ddl in DDL:
        d1_query(ddl)
    prior = registered_stock()

    from telethon import TelegramClient, functions, utils
    from telethon.sessions import StringSession
    from telethon.tl.types import ChatAdminRights
    from telethon.tl.functions.channels import GetParticipantRequest
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            flood_sleep_threshold=0, request_retries=1,
                            connection_retries=2)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("personal_session_not_authorized")
        owner = await client.get_me()
        if owner.bot:
            raise RuntimeError("owner_session_must_be_user")
        dialogs = [d.entity async for d in client.iter_dialogs(limit=500)]
        matching = [d for d in dialogs if getattr(d, "broadcast", False)
                    and not getattr(d, "username", None)
                    and getattr(d, "title", "") == TITLE]
        if len(matching) > 1:
            raise RuntimeError("duplicate_private_stock_titles")
        channel = matching[0] if matching else None
        if prior and not channel:
            raise RuntimeError("registered_stock_not_found_in_owner_dialogs")
        if channel:
            about = await client(functions.channels.GetFullChannelRequest(channel))
            if MARKER not in str(getattr(about.full_chat, "about", "") or ""):
                raise RuntimeError("private_stock_title_collision")
            if prior and int(prior["stock_chat_id"]) != utils.get_peer_id(channel):
                raise RuntimeError("private_stock_id_mismatch")
        else:
            result = await client(functions.channels.CreateChannelRequest(
                title=TITLE, about=MARKER, broadcast=True, megagroup=False,
            ))
            channel = next((x for x in result.chats if getattr(x, "broadcast", False)
                            and x.title == TITLE), None)
            if channel is None:
                raise RuntimeError("private_channel_creation_unconfirmed")
            print("CINEX_PRIVATE_STOCK_CHANNEL_CREATED")
        if not getattr(channel, "broadcast", False) or getattr(channel, "username", None):
            raise RuntimeError("channel_must_be_private_broadcast")
        owner_rights = await client.get_permissions(channel, owner)
        if not getattr(owner_rights, "is_creator", False):
            raise RuntimeError("connected_user_is_not_channel_creator")
        await verify_members(client, channel, int(owner.id), bots)
        for bot in bots:
            user = await client.get_entity("@" + str(bot["username"]))
            if int(user.id) != int(bot["id"]) or not getattr(user, "bot", False):
                raise RuntimeError("telegram_bot_entity_mismatch")
            participant_rights = None
            try:
                member = await client(GetParticipantRequest(channel=channel, participant=user))
                participant_rights = getattr(member.participant, "admin_rights", None)
            except Exception:
                pass
            if participant_rights and getattr(participant_rights, "post_messages", False):
                continue
            minimal = ChatAdminRights(
                change_info=False, post_messages=True, edit_messages=False,
                delete_messages=False, ban_users=False, invite_users=False,
                pin_messages=False, add_admins=False, anonymous=False,
                manage_call=False, other=False, manage_topics=False,
                post_stories=False, edit_stories=False, delete_stories=False,
            )
            await client(functions.channels.EditAdminRequest(
                channel=channel, user_id=user, admin_rights=minimal,
                rank="Stock CinéX",
            ))
            receipt = await client(GetParticipantRequest(channel=channel, participant=user))
            rights = getattr(receipt.participant, "admin_rights", None)
            if not rights or not getattr(rights, "post_messages", False):
                raise RuntimeError("bot_admin_post_rights_not_confirmed")
        await verify_members(client, channel, int(owner.id), bots)
        stock_id = utils.get_peer_id(channel)
        if not str(stock_id).startswith("-100"):
            raise RuntimeError("invalid_private_stock_id")
        store_stock(str(stock_id), int(owner.id), int(bots[0]["id"]),
                    int(bots[1]["id"]) if len(bots) > 1 else None)
        print("CINEX_PRIVATE_STOCK_READY", "private", True,
              "owner_only_humans", True, "bot_count", len(bots),
              "registered_in_private_d1", True, "media_copied", 0)
        return {"ready": True, "created": not bool(matching), "bots": len(bots)}
    finally:
        await client.disconnect()


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--apply", action="store_true")
    parsed = args.parse_args()
    from scripts.check_personal_cooldown import seconds_remaining
    if seconds_remaining():
        print("CINEX_PRIVATE_STOCK_BLOCKED_BY_FLOOD_WAIT")
        return 75
    asyncio.run(provision(apply=parsed.apply))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # No Telegram credentials, invite URLs, IDs, or other personal data in logs.
        print("CINEX_PRIVATE_STOCK_ERROR", type(exc).__name__, str(exc)[:95], file=sys.stderr)
        raise SystemExit(1)
