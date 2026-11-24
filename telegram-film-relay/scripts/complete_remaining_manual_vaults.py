"""Safely complete the nine owner-owned private source vaults (opt-in).

Reuses proven existing sources; creates only missing category-specific ones.
Binds both CineRadar intake and the actual category publisher with minimal
post-only permissions, registers verified sources in PRIVATE D1.

A new source remains disabled until an independent rights attestation is
configured. This script never publishes, forwards or imports media.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass

from scripts.audit_remaining_manual_vaults import (
    REMAINING, CHANNEL_TITLE, PUBLISHER_SECRET, configured_id,
    find_private,
)
from scripts.provision_manual_vault import verify_bot_token

CHANNEL = re.compile(r"^-100[0-9]{6,}$")
MARKER = "MRX_MANUAL_SOURCE_V1:"
ACCOUNT = "9c86118191b804d91b5f5b2c89114999"
DATABASE = "fa8b5009-bc1a-4a6e-b143-7a487c7297a5"
RIGHTS_ENV = {
    cat: "CINEX_MANUAL_RIGHTS_"+cat.upper()+"_ATTESTED"
    for cat in REMAINING
}


def authorized_for_activation(category, env=None):
    """Explicit manual-source redistribution rights (NOT normal publishing rights)."""
    env = os.environ if env is None else env
    return str(env.get(RIGHTS_ENV[category], "false")).strip().lower() == "true"


def d1_query(sql, params=(), env=None):
    import requests
    env = os.environ if env is None else env
    token = str(env.get("CLOUDFLARE_API_TOKEN") or env.get("CF_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("private_d1_credentials_missing")
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        + str(env.get("CLOUDFLARE_ACCOUNT_ID") or ACCOUNT)
        + "/d1/database/" + str(env.get("CINERADAR_D1_DATABASE_ID") or DATABASE)
        + "/query"
    )
    try:
        response = requests.post(
            url, headers={"Authorization": "Bearer " + token},
            json={"sql":sql,"params":list(params)}, timeout=18,
        )
        body = response.json()
        if not response.ok or body.get("success") is not True:
            raise RuntimeError("private_d1_write_failed")
        result = body.get("result") or []
        if len(result) != 1 or result[0].get("success") is not True:
            raise RuntimeError("private_d1_receipt_missing")
        return result[0].get("results") or []
    except (ValueError, requests.RequestException) as exc:
        raise RuntimeError("private_d1_network_unavailable") from exc


def register_source(chat_id, category, *, bot_verified, explicit_rights):
    """Idempotent and immutable category mapping. No rights inferred from ownership."""
    if category not in REMAINING or not CHANNEL.fullmatch(str(chat_id)):
        raise ValueError("invalid_owner_source")
    if not bot_verified:
        raise RuntimeError("required_bots_not_verified")
    old = d1_query(
        "SELECT category,rights_attested FROM cine_manual_fallback_sources "
        "WHERE chat_id=? LIMIT 2", [str(chat_id)]
    )
    if old and (len(old) != 1 or old[0]["category"] != category):
        raise RuntimeError("source_belongs_to_another_category")
    rights = 1 if explicit_rights or (
        old and int(old[0].get("rights_attested") or 0) == 1) else 0
    enabled = rights
    d1_query(
        "INSERT INTO cine_manual_fallback_sources"
        "(chat_id,category,rights_attested,bot_access_verified,owner_approved,"
        "enabled,verified_at) VALUES(?,?,?,1,1,?,CURRENT_TIMESTAMP) "
        "ON CONFLICT(chat_id) DO UPDATE SET "
        "bot_access_verified=1,owner_approved=1,"
        "rights_attested=excluded.rights_attested,enabled=excluded.enabled,"
        "verified_at=CURRENT_TIMESTAMP "
        "WHERE cine_manual_fallback_sources.category=excluded.category",
        [str(chat_id),category,rights,enabled]
    )
    after = d1_query(
        "SELECT category,enabled,owner_approved,rights_attested,"
        "bot_access_verified FROM cine_manual_fallback_sources "
        "WHERE chat_id=? LIMIT 2", [str(chat_id)]
    )
    if (len(after) != 1 or after[0]["category"] != category or
            int(after[0]["owner_approved"]) != 1 or
            int(after[0]["bot_access_verified"]) != 1 or
            int(after[0]["rights_attested"]) != rights or
            int(after[0]["enabled"]) != enabled):
        raise RuntimeError("private_d1_source_not_confirmed")
    return bool(enabled)


def category_bot_tokens(env):
    radar = str(env.get("CINE_RADAR_BOT_TOKEN") or "").strip()
    if not radar:
        raise RuntimeError("radar_bot_secret_missing")
    mapping = {"radar": radar}
    for key in sorted(set(PUBLISHER_SECRET.values())):
        token = str(env.get(key) or "").strip()
        if token:
            mapping[key] = token
    return mapping


async def verified_bot_peers(client, env):
    result = {}
    for label, token in category_bot_tokens(env).items():
        info = verify_bot_token(token)
        if not info or info.get("is_bot") is not True:
            continue
        if label == "radar" and str(info.get("username", "")).lower() != "cineradarfr_bot":
            raise RuntimeError("radar_identity_mismatch")
        try:
            peer = await client.get_entity("@" + str(info["username"]))
            if not getattr(peer, "bot", False) or peer.id != info["id"]:
                continue
            result[label] = peer
        except Exception:
            continue
    if "radar" not in result:
        raise RuntimeError("radar_bot_not_verified")
    return result


def minimal_rights():
    from telethon.tl.types import ChatAdminRights
    return ChatAdminRights(
        change_info=False, post_messages=True,
        edit_messages=False, delete_messages=False,
        ban_users=False, invite_users=False, pin_messages=False,
        add_admins=False, anonymous=False, manage_call=False,
        other=False, manage_topics=False, post_stories=False,
        edit_stories=False, delete_stories=False,
    )


async def check_and_grant(client, source, bot, *, apply):
    from telethon import functions
    from telethon.errors import UserNotParticipantError
    if bot is None:
        return False
    try:
        perms = await client.get_permissions(source, bot)
        if getattr(perms, "is_creator", False) or (
            getattr(perms, "is_admin", False) and
            getattr(perms, "post_messages", False)
        ):
            return True
    except UserNotParticipantError:
        pass
    except Exception:
        # Do not guess what a Telegram error means.
        raise
    if not apply:
        return False
    await client(functions.channels.EditAdminRequest(
        channel=source, user_id=bot,
        admin_rights=minimal_rights(), rank="CineX Stock"
    ))
    await asyncio.sleep(15)
    receipt = await client.get_permissions(source, bot)
    return bool(getattr(receipt, "is_creator", False) or (
        getattr(receipt, "is_admin", False) and
        getattr(receipt, "post_messages", False)
    ))


@dataclass
class Result:
    category: str
    existing: bool = False
    created: bool = False
    bots_ready: bool = False
    registered: bool = False
    ingestion_enabled: bool = False
    issue: str = ""


async def finish_nine(*, apply=False, max_created=4, pause=180):
    """Single authorized client; fail-stop on Telegram limits, never evade."""
    from telethon import TelegramClient, functions, utils
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, PeerFloodError

    if max_created < 0 or max_created > 4 or pause < 120:
        raise ValueError("unsafe_provisioning_limits")
    env = os.environ
    session = str(env.get("TG_STRING_SESSION") or "").strip()
    api_id = str(env.get("TG_API_ID") or "").strip()
    api_hash = str(env.get("TG_API_HASH") or "").strip()
    if not session or not api_id.isdecimal() or not api_hash:
        raise RuntimeError("personal_session_missing")
    # Private D1 must be available before any Telegram channel creation.
    d1_query("SELECT category FROM cine_manual_fallback_sources LIMIT 1")
    client = TelegramClient(StringSession(session),int(api_id),api_hash,
                            request_retries=0,connection_retries=0,
                            flood_sleep_threshold=0)
    await client.connect()
    created = 0
    outputs = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("personal_session_revoked")
        me = await client.get_me()
        if me is None or getattr(me,"bot",False):
            raise RuntimeError("account_not_personal")
        bots = await verified_bot_peers(client,env)
        dialogs = [d.entity async for d in client.iter_dialogs(limit=500)]
        for category in REMAINING:
            row = Result(category)
            try:
                specified = configured_id(category,env)
                status, source = find_private(
                    dialogs,category,specified,utils.get_peer_id
                )
                if status not in ("missing","found"):
                    row.issue = status
                    outputs.append(row)
                    continue
                if source is None:
                    if not apply:
                        row.issue = "private_source_not_created_in_dry_run"
                        outputs.append(row)
                        continue
                    if created >= max_created:
                        row.issue = "new_channel_creation_cap"
                        outputs.append(row)
                        continue
                    reply = await client(functions.channels.CreateChannelRequest(
                        title=CHANNEL_TITLE[category],
                        about=MARKER+category,
                        broadcast=True,megagroup=False,
                    ))
                    matches = [x for x in reply.chats
                               if getattr(x,"broadcast",False) and
                               x.title==CHANNEL_TITLE[category] and
                               not getattr(x,"username",None)]
                    if len(matches)!=1:
                        raise RuntimeError("new_private_channel_not_confirmed")
                    source=matches[0]
                    dialogs.append(source)
                    row.created=True
                    created+=1
                    await asyncio.sleep(pause)
                else:
                    row.existing=True
                if getattr(source,"username",None) or not getattr(source,"broadcast",False):
                    raise RuntimeError("source_must_be_private_broadcast")
                actual_id = str(utils.get_peer_id(source))
                if not CHANNEL.fullmatch(actual_id):
                    raise RuntimeError("invalid_private_peer")
                if specified and specified!=actual_id:
                    raise RuntimeError("configured_private_peer_mismatch")
                owner = await client.get_permissions(source,me)
                if not getattr(owner,"is_creator",False):
                    raise RuntimeError("source_creator_mismatch")
                if not specified:
                    from telethon.tl.functions.channels import GetFullChannelRequest
                    full=await client(GetFullChannelRequest(source))
                    if MARKER+category not in str(full.full_chat.about or ""):
                        raise RuntimeError("unmarked_private_vault_conflict")
                radar = bots.get("radar")
                publisher = bots.get(PUBLISHER_SECRET[category])
                # Never approve a vault that is inaccessible to either bot.
                if publisher is None:
                    row.issue="publisher_bot_secret_missing"
                    outputs.append(row);continue
                verified = True
                for bot in {radar.id:radar,publisher.id:publisher}.values():
                    if not await check_and_grant(client,source,bot,apply=apply):
                        verified=False
                row.bots_ready=verified
                if apply and verified:
                    row.ingestion_enabled=register_source(
                        actual_id,category,bot_verified=True,
                        explicit_rights=authorized_for_activation(category,env))
                    row.registered=True
                if not verified:
                    row.issue="telegram_bot_admin_missing"
                elif not row.ingestion_enabled:
                    row.issue="awaiting_explicit_manual_media_rights"
                outputs.append(row)
            except (FloodWaitError,PeerFloodError):
                # Never attempt another channel, account or session on rate-limit.
                raise
            except Exception as exc:
                row.issue=type(exc).__name__
                outputs.append(row)
        return outputs
    finally:
        await client.disconnect()


def main():
    import argparse
    from scripts.check_personal_cooldown import seconds_remaining
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--max-created",type=int,default=4)
    parser.add_argument("--pause",type=int,default=180)
    a=parser.parse_args()
    if seconds_remaining():
        print("CINEX_NINE_SOURCE_BLOCKED_BY_FLOODWAIT")
        return 75
    try:
        rows=asyncio.run(finish_nine(
            apply=a.apply,max_created=a.max_created,pause=a.pause))
    except Exception as exc:
        print("CINEX_NINE_SOURCE_HALTED",type(exc).__name__)
        return 1
    safe=[x.__dict__ for x in rows]
    print("CINEX_NINE_SOURCE_RESULT "+json.dumps(safe,sort_keys=True))
    n=sum(x.registered for x in rows)
    created=sum(x.created for x in rows)
    live=sum(x.ingestion_enabled for x in rows)
    print("CINEX_NINE_SOURCE_SUMMARY",json.dumps({
        "total":len(rows),"registered":n,"created":created,
        "enabled_with_rights":live,"requires_followup":sum(not x.ingestion_enabled for x in rows)
    },sort_keys=True))
    return 0 if len(rows)==len(REMAINING) and n==len(REMAINING) else 2

if __name__=="__main__":
    sys.exit(main())
