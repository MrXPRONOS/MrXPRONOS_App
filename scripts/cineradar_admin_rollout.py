#!/usr/bin/env python3
"""Gradual reconciliation of owner's Telegram channel admin bots and reactions.

The owner explicitly requested all applicable channel privileges except the
ability to add administrators. Uses ONLY Telegram personal MTProto, Telegram
Bot API for getMe, and encrypted GitHub file state. No Cloudflare, D1,
Supabase or other database. Never reveals private channel identifiers/tokens.

It never sends messages, posts, reactions, creates channels, joins unfamiliar
channels, removes admins or changes any existing webhook. Every mutation is
idempotent and verified; FloodWait stops without retrying Telegram.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import os
import re
import sys
import time
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from scripts.actu_foot_github_vault import GitHubVault, VaultError, VaultConflict
from scripts.cineradar_owner_channels import OwnerChannelVault, validate as validate_owner
from scripts.cineradar_reaction_core import (
    configured_tokens, telegram_call, APIError, PRIMARY_CANDIDATES,
)

PROGRESS_PATH = "assets/data/private/cineradar/admin_rollout.aes.json"
PROGRESS_CONTEXT = b"MrXPRONOS/CineRadar/BotAdminRollout/GitHubVault/v1"
MAX_BOTS = 40
# Named bot secrets already present in the repository's cinema, editorial and
# reaction workflows. Numbered secrets and optional JSON are handled separately.
ADDITIONAL_SECRET_NAMES = (
    "CINEX_ANIME_SOURCE_BOT_TOKEN", "ALT_FOOTBALL_NEWS_BOT_TOKEN",
    "ALT_TELEGRAM_BOT_TOKEN", "ALT_DESIR_BOT_TOKEN",
    "ALT_ACTION_BOT_TOKEN", "ALT_ANIME_BOT_TOKEN",
    "ALT_SERIES_BOT_TOKEN", "CINERADAR_REACTION_OBSERVER_TOKEN",
)


class AdminRolloutVault(GitHubVault):
    def __init__(self, **kwargs):
        super().__init__(path=PROGRESS_PATH, **kwargs)
        self.key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                        info=PROGRESS_CONTEXT).derive(self.key)


def no_secrets(text):
    # Never surface Telegram error bodies or bot usernames/IDs in job logs.
    return type(text).__name__


def bot_token_candidates(env):
    """Every explicitly configured, relevant GitHub bot secret, deduped by value."""
    values = list(configured_tokens(env).values())
    for keys in PRIMARY_CANDIDATES.values():
        values.extend(str(env.get(key) or "").strip() for key in keys)
    values.extend(str(env.get(key) or "").strip()
                  for key in ADDITIONAL_SECRET_NAMES)
    seen, result = set(), []
    for token in values:
        if token and token not in seen:
            result.append(token)
            seen.add(token)
    return result


def resolve_bot_accounts(env, transport=None):
    from scripts.cineradar_reaction_core import _request_json
    transport = transport or _request_json
    result, used = [], set()
    invalid = 0
    for token in bot_token_candidates(env):
        try:
            status, body = telegram_call(token, "getMe", {}, transport)
        except APIError:
            invalid += 1
            continue
        profile = body.get("result") or {}
        ident = profile.get("id")
        name = str(profile.get("username") or "")
        if (status != 200 or body.get("ok") is not True
            or profile.get("is_bot") is not True
            or type(ident) is not int or ident <= 0
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", name)):
            invalid += 1
            continue
        if ident in used:
            continue
        used.add(ident)
        result.append({"id": ident, "username": name})
        if len(result) > MAX_BOTS:
            raise VaultError("Unexpectedly large Telegram admin bot inventory")
    if not result:
        raise VaultError("No verified Telegram bots")
    print(f"ADMIN_ROLLOUT_BOT_PREFLIGHT unique={len(result)} unavailable={invalid}")
    return result


def full_channel_rights():
    """Full applicable broadcast rights, explicitly NEVER add_admins."""
    from telethon.tl.types import ChatAdminRights
    possible = set(inspect.signature(ChatAdminRights).parameters)
    wanted = (
        "change_info", "post_messages", "edit_messages", "delete_messages",
        "ban_users", "invite_users", "manage_call", "other",
        "post_stories", "edit_stories", "delete_stories",
        "manage_direct_messages", "manage_ranks",
    )
    values = {key: True for key in wanted if key in possible}
    # Group/forum-only rights aren't applicable to broadcast channels.
    for key in ("add_admins","pin_messages","anonymous","manage_topics"):
        if key in possible:
            values[key] = False
    return ChatAdminRights(**values)


def rights_satisfied(actual, desired):
    if actual is None or getattr(actual, "add_admins", False):
        return False
    necessary = (
        "change_info","post_messages","edit_messages","delete_messages",
        "ban_users","invite_users","manage_call",
    )
    return all(
        not getattr(desired,key,False) or getattr(actual,key,False)
        for key in necessary
    )


def is_torrent9(entity):
    from scripts.cineradar_reaction_multichannel import is_torrent9 as check
    return check({"title":getattr(entity,"title",None),
                  "username":getattr(entity,"username",None)})


def inventory():
    vault = OwnerChannelVault(branch="main")
    snapshot = vault.read(allow_new=False)
    ids, excluded = validate_owner(snapshot.data)
    date = datetime.fromisoformat(snapshot.data["verified_at"].replace("Z","+00:00"))
    if date.tzinfo is None or (datetime.now(timezone.utc)-date).total_seconds() > 14*86400:
        raise VaultError("Owner admin inventory is stale")
    return sorted(ids), excluded


def cursor_state(vault, channels):
    ids_digest = hashlib.sha256("|".join(channels).encode()).hexdigest()
    snap = vault.read(allow_new=True)
    doc = snap.data if snap.sha else {
        "version":1,"fingerprint":ids_digest,"cursor":0,"cooldown_until":0,
    }
    if doc.get("version")!=1 or not isinstance(doc.get("cursor"),int):
        raise VaultError("Invalid encrypted rollout progress")
    if doc.get("fingerprint")!=ids_digest:
        doc={"version":1,"fingerprint":ids_digest,"cursor":0,"cooldown_until":0}
    doc["cursor"] %= len(channels)
    return doc,snap.sha


async def real_member_rights(client, channel, bot):
    from telethon import functions, errors
    try:
        result = await client(functions.channels.GetParticipantRequest(
            channel=channel, participant=bot,
        ))
        part=result.participant
        return getattr(part,"admin_rights",None)
    except errors.UserNotParticipantError:
        return None


async def ensure_admin(client,channel,bot,desired,*,dry_run):
    """One verified promotion. Existing webhook routing is never touched."""
    from telethon import functions, errors
    before = await real_member_rights(client,channel,bot)
    if rights_satisfied(before,desired):
        return "already_full"
    if dry_run:
        return "would_promote"
    try:
        await client(functions.channels.EditAdminRequest(
            channel=channel,user_id=bot,admin_rights=desired,rank="CinéRadar",
        ))
    except errors.UserNotParticipantError:
        await client(functions.channels.InviteToChannelRequest(
            channel=channel,users=[bot],
        ))
        await client(functions.channels.EditAdminRequest(
            channel=channel,user_id=bot,admin_rights=desired,rank="CinéRadar",
        ))
    actual=await real_member_rights(client,channel,bot)
    if not rights_satisfied(actual,desired):
        raise RuntimeError("Telegram administration rights were not confirmed")
    if getattr(actual,"add_admins",False):
        raise RuntimeError("Forbidden admin delegation privilege detected")
    return "promoted"


async def ensure_reactions(client, channel, *, dry_run):
    """Enable normal heart/thumbs-up reactions where currently disabled.

    Do not enable paid/star reactions, alter unrelated allowed emoji policies,
    or disable any pre-existing reaction option.
    """
    from telethon import functions, types
    full=await client(functions.channels.GetFullChannelRequest(channel))
    available=getattr(full.full_chat,"available_reactions",None)
    if isinstance(available,types.ChatReactionsAll):
        return "already_allowed"
    if isinstance(available,types.ChatReactionsSome):
        listed={str(getattr(x,"emoticon","")) for x in available.reactions}
        if {"❤️","👍"}.issubset(listed):
            return "already_allowed"
        # Preserve existing allowed emoji, adding only what the reaction bots
        # actually use. Do not inadvertently remove custom emoji reactions.
        new_reactions=list(available.reactions)
        for emoji in ("❤️","👍"):
            if emoji not in listed:
                new_reactions.append(types.ReactionEmoji(emoticon=emoji))
    else:
        new_reactions=[
            types.ReactionEmoji(emoticon="❤️"),
            types.ReactionEmoji(emoticon="👍"),
        ]
    if dry_run:
        return "would_enable"
    await client(functions.messages.SetChatAvailableReactionsRequest(
        peer=channel,
        available_reactions=types.ChatReactionsSome(reactions=new_reactions),
    ))
    # Do not assume Telegram accepted settings solely because no exception.
    updated=await client(functions.channels.GetFullChannelRequest(channel))
    current=getattr(updated.full_chat,"available_reactions",None)
    if isinstance(current,types.ChatReactionsSome):
        present={str(getattr(x,"emoticon","")) for x in current.reactions}
        if {"❤️","👍"}.issubset(present):
            return "enabled"
    if isinstance(current,types.ChatReactionsAll):
        return "enabled"
    raise RuntimeError("Channel reaction policy not confirmed")


async def apply_batch(channels, excluded, bots, cursor, *, apply, max_changes,
                      max_channels, pause, cooldown_until):
    from telethon import TelegramClient, errors, utils
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel
    from scripts.cineradar_reaction_multichannel import is_torrent9 as matching_torrent9

    api_id=str(os.getenv("TG_API_ID") or "").strip()
    api_hash=str(os.getenv("TG_API_HASH") or "").strip()
    session=(os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
             or os.getenv("TG_STREAM_SESSION") or "").strip()
    if not api_id.isdecimal() or not api_hash or not session:
        raise VaultError("Telegram owner session is unavailable")
    if time.time() < cooldown_until:
        print("ADMIN_ROLLOUT_SKIPPED telegram_flood_cooldown_active=true")
        return cursor,{"cooldown":cooldown_until,"skipped":True}
    client=TelegramClient(
        StringSession(session),int(api_id),api_hash,request_retries=0,
        connection_retries=1,flood_sleep_threshold=0,timeout=18,
        receive_updates=False,
    )
    await client.connect()
    counters={"channels_seen":0,"channels_completed":0,"already":0,
              "promoted":0,"reactions_enabled":0,"blocked_rights":0,
              "inaccessible":0,"failed":0,"missing_bots":0}
    try:
        if not await client.is_user_authorized():
            raise VaultError("Telegram owner session no longer authorized")
        owner=await client.get_me()
        if owner is None or getattr(owner,"bot",True):
            raise VaultError("Not an authenticated personal Telegram user")
        # The current user's dialogs supply access hashes for private channels.
        dialogs={}
        async for dialog in client.iter_dialogs():
            channel=dialog.entity
            if isinstance(channel,Channel) and channel.broadcast:
                dialogs[str(utils.get_peer_id(channel))]=channel
        desired=full_channel_rights()
        for step in range(max_channels):
            if counters["channels_completed"]>=max_channels:
                break
            idx=(cursor+step)%len(channels)
            cid=channels[idx]
            counters["channels_seen"]+=1
            entity=dialogs.get(cid)
            if cid in excluded or entity is None:
                counters["inaccessible"]+=1
                counters["channels_completed"]+=1
                continue
            if is_torrent9(entity):
                counters["inaccessible"]+=1
                counters["channels_completed"]+=1
                continue
            permissions=await client.get_permissions(entity,owner)
            can_promote=bool(getattr(permissions,"is_creator",False) or
                (getattr(permissions,"is_admin",False)
                and getattr(permissions,"add_admins",False)))
            # Telegram requires channel admin rights to promote anyone.
            if not can_promote:
                counters["blocked_rights"]+=1
                counters["channels_completed"]+=1
                continue
            if counters["promoted"]>=max_changes:
                break
            # Reactions are a CHANNEL policy, not a per-bot admin right.
            try:
                p=await ensure_reactions(client,entity,dry_run=not apply)
                if p=="enabled":
                    counters["reactions_enabled"]+=1
                    await asyncio.sleep(pause)
            except (errors.FloodWaitError,errors.PeerFloodError):
                raise
            except Exception:
                counters["failed"]+=1
            for botdef in bots:
                if counters["promoted"]>=max_changes:
                    break
                try:
                    bot=await client.get_entity("@"+botdef["username"])
                    if not getattr(bot,"bot",False) or bot.id != botdef["id"]:
                        counters["missing_bots"]+=1
                        continue
                    result=await ensure_admin(
                        client,entity,bot,desired,dry_run=not apply,
                    )
                    if result=="already_full":
                        counters["already"]+=1
                    if result=="promoted":
                        counters["promoted"]+=1
                        await asyncio.sleep(pause)
                    if result=="would_promote":
                        counters["promoted"]+=1
                except (errors.FloodWaitError,errors.PeerFloodError):
                    raise
                except Exception:
                    counters["failed"]+=1
            # Repeat this channel on the next invocation if the current
            # rate-limit budget was exhausted before checking all bots.
            if counters["promoted"]>=max_changes:
                return idx,counters
            counters["channels_completed"]+=1
        return (cursor+counters["channels_completed"])%len(channels),counters
    finally:
        await client.disconnect()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--max-changes",type=int,default=6)
    parser.add_argument("--max-channels",type=int,default=2)
    parser.add_argument("--pause",type=float,default=15)
    args=parser.parse_args()
    if not (1<=args.max_changes<=12 and 1<=args.max_channels<=4
            and 10<=args.pause<=90):
        raise ValueError("Unsafe rollout limits")
    channels,excluded=inventory()
    if not channels:
        raise VaultError("No verified channels to administer")
    bots=resolve_bot_accounts(os.environ)
    vault=AdminRolloutVault(branch="main")
    progress,sha=cursor_state(vault,channels)
    if args.apply and os.getenv("CINERADAR_ADMIN_APPLY_AUTHORIZED")!="true":
        raise VaultError("Explicit rollout authorization missing")
    print(f"ADMIN_ROLLOUT_PLAN verified_owner_channels={len(channels)} "
          f"excluded_torrent9={len(excluded)} distinct_bots={len(bots)} "
          f"max_changes={args.max_changes} max_channels={args.max_channels} "
          f"mode={'apply' if args.apply else 'audit'}")
    from telethon.errors import FloodWaitError,PeerFloodError
    try:
        cursor,summary=asyncio.run(apply_batch(
            channels,excluded,bots,progress["cursor"],
            apply=args.apply,max_changes=args.max_changes,
            max_channels=args.max_channels,pause=args.pause,
            cooldown_until=int(progress.get("cooldown_until") or 0),
        ))
    except FloodWaitError as exc:
        # Telegram's limitation applies to this PERSONAL account; stop,
        # persist the deadline and do not blindly retry or evade it.
        progress["cooldown_until"]=int(time.time())+max(0,int(exc.seconds))+1800
        if args.apply:
            vault.write(progress,expected_sha=sha,
                        message="data(cineradar): Telegram admin rollout cooldown")
        print("ADMIN_ROLLOUT_FLOODWAIT_STOP cooldown_recorded=true")
        return 75
    except PeerFloodError:
        progress["cooldown_until"]=int(time.time())+86400
        if args.apply:
            vault.write(progress,expected_sha=sha,
                        message="data(cineradar): Telegram account protection")
        print("ADMIN_ROLLOUT_PEER_FLOOD_STOP cooldown_recorded=true")
        return 75
    if args.apply and not summary.get("skipped"):
        progress["cursor"]=cursor
        progress["last_run"]=datetime.now(timezone.utc).isoformat()
        vault.write(progress,expected_sha=sha,
                    message="data(cineradar): admin permissions rollout progress")
    print("ADMIN_ROLLOUT_RESULT "+ " ".join(
        str(key)+"="+str(value) for key,value in summary.items()
    ))
    return 0


if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ADMIN_ROLLOUT_FAILED",type(exc).__name__,file=sys.stderr)
        sys.exit(1)
