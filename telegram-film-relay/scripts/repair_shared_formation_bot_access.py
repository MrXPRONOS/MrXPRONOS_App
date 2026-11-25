"""Repair only the owner's existing shared Formation private source bot admin.

Never creates/joins a Telegram channel, copies media, changes destination,
enables redistribution rights, or logs Telegram IDs / API tokens.
"""
from __future__ import annotations
import asyncio
import os
import sys

from scripts.complete_remaining_manual_vaults import (
    d1_query, verified_bot_peers, check_and_grant,
)

def record_safe_status(prefix,token,peer,expected_id):
    import requests
    if not token:
        raise RuntimeError(prefix+"_token_missing")
    try:
        response=requests.post(
            "https://api.telegram.org/bot"+token+"/getMe",timeout=12)
        data=response.json()
    except Exception:
        raise RuntimeError(prefix+"_getme_unavailable") from None
    user=data.get("result") if data.get("ok") else {}
    if user.get("id")!=expected_id or user.get("is_bot") is not True:
        raise RuntimeError(prefix+"_getme_identity_mismatch")
    for method,params in (
        ("getChat",{"chat_id":peer}),
        ("getChatMember",{"chat_id":peer,"user_id":expected_id}),
    ):
        try:
            result=requests.post(
                "https://api.telegram.org/bot"+token+"/"+method,
                json=params,timeout=15).json()
        except Exception:
            raise RuntimeError(prefix+"_"+method+"_network_uncertain") from None
        if result.get("ok") is not True:
            code=result.get("error_code")
            if code not in (400,401,403,429):
                code=0
            raise RuntimeError(prefix+"_"+method+"_failed_"+str(code))
        payload=result.get("result") or {}
        if method=="getChat":
            if payload.get("type")!="channel" or payload.get("username"):
                raise RuntimeError(prefix+"_source_not_private_channel")
            if payload.get("has_protected_content") is True:
                raise RuntimeError(prefix+"_source_protected_copy_not_allowed")
        else:
            if not (payload.get("status") in ("administrator","creator") and
                    (payload.get("status")=="creator" or
                     payload.get("can_post_messages") is True)):
                raise RuntimeError(prefix+"_bot_post_rights_missing")
    return True

async def repair():
    from telethon import TelegramClient,utils
    from telethon.sessions import StringSession
    source=d1_query(
        "SELECT chat_id,owner_approved,bot_access_verified "
        "FROM cine_manual_fallback_sources WHERE category='formation_general'")
    if len(source)!=1 or source[0]["owner_approved"]!=1 or \
       source[0]["bot_access_verified"]!=1:
        raise RuntimeError("verified_shared_source_missing")
    registered=str(source[0]["chat_id"])
    stage=str(os.getenv("FORMATION_STAGE_CHAT") or "").strip()
    if not registered.startswith("-100") or stage!=registered:
        raise RuntimeError("stage_does_not_match_verified_source")
    creds=(os.getenv("TG_API_ID","").strip(),
           os.getenv("TG_API_HASH","").strip(),
           os.getenv("TG_STRING_SESSION","").strip())
    if not creds[0].isdecimal() or not creds[1] or not creds[2]:
        raise RuntimeError("owner_session_credentials_missing")
    client=TelegramClient(StringSession(creds[2]),int(creds[0]),creds[1],
                          request_retries=0,connection_retries=0,
                          flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("owner_session_not_authorized")
        me=await client.get_me()
        if not me or getattr(me,"bot",False):
            raise RuntimeError("owner_identity_invalid")
        dialogs=[d.entity async for d in client.iter_dialogs(limit=500)]
        matches=[d for d in dialogs if
                 str(utils.get_peer_id(d))==registered and
                 getattr(d,"broadcast",False) and
                 not getattr(d,"username",None)]
        if len(matches)!=1:
            raise RuntimeError("verified_private_source_not_found")
        channel=matches[0]
        owner=await client.get_permissions(channel,me)
        if not getattr(owner,"is_creator",False):
            raise RuntimeError("owner_not_channel_creator")
        bots=await verified_bot_peers(client,os.environ)
        publisher=bots.get("FORMATION_BOT_TOKEN")
        radar=bots.get("radar")
        if not publisher or not radar:
            raise RuntimeError("formation_or_radar_bot_not_resolved")
        changes=0
        for label,bot in dict.fromkeys((("formation",publisher),
                                         ("radar",radar))):
            if not await check_and_grant(client,channel,bot,apply=True):
                raise RuntimeError(label+"_bot_admin_not_confirmed")
            # Telethon proves owner admin rights; Bot API must independently
            # prove the currently configured exact secret can access source.
            key="FORMATION_BOT_TOKEN" if label=="formation" else "CINE_RADAR_BOT_TOKEN"
            record_safe_status(label,os.getenv(key,""),registered,int(bot.id))
        print("FORMATION_SHARED_SOURCE_BOT_PERMISSIONS",
              "owner=verified","formation=verified","radar=verified",
              "source_protected=false")
    finally:
        await client.disconnect()

def main():
    from scripts.check_personal_cooldown import seconds_remaining
    if seconds_remaining():
        print("FORMATION_SOURCE_ACCESS_BLOCKED_BY_COOLDOWN")
        return 75
    try:
        asyncio.run(repair())
        return 0
    except Exception as exc:
        if type(exc) is RuntimeError:
            reason=str(exc)
            if not reason.replace("_","").replace("0","").replace("1","").replace("2","").replace("3","").replace("4","").replace("9","").isalnum():
                reason="unknown_safe_error"
        else:
            reason=type(exc).__name__
        print("FORMATION_SOURCE_ACCESS_STOPPED",reason)
        return 1

if __name__=="__main__":
    sys.exit(main())
