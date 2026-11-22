"""One-time public channel discovery for the Actu Foot RSS V1 router.

Reads the owner's existing Telegram folder, verifies the *publishing bot* can
post to each channel, and prints ONLY public @usernames for configuration.
No personal session, tokens, or private channel IDs are ever printed.
"""
import asyncio
import json
import os

import requests
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from actufoot_admin_bot_setup import find_actufoot_targets, compact, EXPECTED_HANDLES

# Keywords apply to channel titles *only* if user-chosen username differs.
ROLE_SIGNATURES = {
    "flash": ("footflashactufr", "footflash", "flash247", "footflash247"),
    "mercato": ("mercatofootinfosfr", "mercato"),
    "champions": ("ldcactufootfr", "liguedeschampions", "champions"),
    "premier": ("premierleagueactufr", "premierleague"),
    "liga": ("ligafootactufr", "ligafoot", "laliga", "ligaactualit"),
    "ligue1": ("ligue1footactufr", "ligue1"),
    "africa": ("footafriqueinfosfr", "footafrique", "footafrica"),
    "national": ("selectionsfootactu", "equipenational", "selection"),
    "scores": ("scoresfootclassements", "scoresfoot", "scorefoot", "scoreclassement"),
    "debrief": ("debrieffootanalyses", "debrieffoot", "debrief", "analyse"),
}


def role_for_channel(item):
    username = compact(getattr(item, "username", "") or "")
    title = compact(getattr(item, "title", "") or "")
    # Exact usernames take precedence; an innocuous title can change.
    matched = [role for role, candidates in ROLE_SIGNATURES.items()
               if username in candidates]
    if len(matched) == 1:
        return matched[0]
    matched = [role for role, candidates in ROLE_SIGNATURES.items()
               if any(keyword in title for keyword in candidates)]
    if len(matched) != 1:
        raise ValueError("channel_role_missing_or_ambiguous")
    return matched[0]


def bot_call(session, token, method, data=None):
    # Exceptions must never leak Telegram token embedded in request URL.
    try:
        r = session.post("https://api.telegram.org/bot" + token + "/" + method,
                         data=data or {}, timeout=18)
        data = r.json()
        if r.status_code != 200 or data.get("ok") is not True:
            raise ValueError("telegram_bot_api_error")
        return data["result"]
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise RuntimeError("telegram_bot_access_preflight_failed") from None


async def run():
    api_id = os.getenv("TG_API_ID", "")
    api_hash = os.getenv("TG_API_HASH", "")
    token = os.getenv("FOOTBALL_NEWS_BOT_TOKEN", "")
    string = os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION", "")
    if not api_id.isdecimal() or not api_hash or not token or not string:
        raise RuntimeError("actufoot_registry_credentials_missing")
    session = requests.Session()
    me = bot_call(session, token, "getMe")
    if me.get("is_bot") is not True:
        raise RuntimeError("actufoot_publishing_identity_invalid")
    client = TelegramClient(StringSession(string), int(api_id), api_hash,
                            flood_sleep_threshold=0, request_retries=0,
                            connection_retries=1, receive_updates=False)
    async with client:
        if not await client.is_user_authorized():
            raise RuntimeError("actufoot_owner_session_invalid")
        targets = await find_actufoot_targets(client)
        mapping = {}
        for ch in targets:
            role = role_for_channel(ch)
            public = str(getattr(ch, "username", "") or "").strip()
            if not public or not public[0].isalpha():
                raise RuntimeError("private_or_invalid_channel_not_in_public_registry")
            if role in mapping:
                raise RuntimeError("duplicate_actufoot_role")
            member = bot_call(session, token, "getChatMember", {
                "chat_id": "@" + public, "user_id": str(me["id"]),
            })
            if member.get("status") not in ("administrator", "creator"):
                raise RuntimeError("publishing_bot_not_admin_on_every_channel")
            if member.get("status") == "administrator" and member.get("can_post_messages") is not True:
                raise RuntimeError("publishing_bot_cannot_post")
            resolved = bot_call(session, token, "getChat", {"chat_id": "@" + public})
            if int(resolved.get("id") or 0) != int(utils.get_peer_id(ch)):
                raise RuntimeError("telegram_chat_identity_mismatch")
            mapping[role] = "@" + public
        if len(mapping) != len(ROLE_SIGNATURES):
            raise RuntimeError("missing_actufoot_channel_roles")
        if len(set(mapping.values())) != len(mapping):
            raise RuntimeError("duplicate_actufoot_destinations")
        print("ACTUFOOT_PUBLIC_CHANNEL_MAP",json.dumps(mapping,ensure_ascii=False,sort_keys=True))
        print("ACTUFOOT_PUBLIC_CHANNELS_VERIFIED",len(mapping),
              "publishing_bot_can_post",len(mapping))


if __name__ == "__main__":
    asyncio.run(run())
