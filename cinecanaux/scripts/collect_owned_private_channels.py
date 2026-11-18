#!/usr/bin/env python3
"""Ciné Radar: discover owned private film/series/anime channels, store invite links safely.
Only existing personal Telegram dialogs that are also verified bot-administered in the private
Supabase registry qualify. Never print channel identities or invitations. No media transfers.
"""
import asyncio
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

import requests
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl.types import Channel
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest

MAX_SCAN = 1000
TARGET = "cine_radar_owned_invites"
INVITE = re.compile(r"^https://t[.]me/(?:[+][A-Za-z0-9_-]{12,}|joinchat/[A-Za-z0-9_-]{12,})$")
def plain(value):
    return "".join(ch for ch in unicodedata.normalize("NFD", str(value or "").casefold()) if not unicodedata.combining(ch))
def compact(value):
    return re.sub(r"[^a-z0-9]+", "", plain(value))
def classify(name):
    n = plain(name); key = compact(name)
    if "torrent9" in key or "livecorner" in key or "actucine" in key: return None
    if any(x in key for x in ("blackclover","animezone","cinexanime","jojosbizarre","jujutsukaisen","onepiece","bleach","manga")):
        return ("animes", None, False)
    if any(x in key for x in ("kdramazone","blackdoves","series","serie","lupin")) and "africacine" not in key:
        return ("series", None, False)
    if "africacine" in key: return ("films", "series", False)
    if "cinexdesir" in key: return ("films", "romance", True)
    if any(x in key for x in ("cinexcomedie","cinexvideotheque","hollywood","films","film","cinema")):
        return ("films", "comedie" if "comedie" in key else None, False)
    return None

def session():
    url = os.getenv("SUPABASE_URL","").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
    if not url.startswith("https://") or not url.endswith(".supabase.co") or not key:
        raise RuntimeError("private_registry_credentials_invalid")
    s = requests.Session()
    s.headers.update({"apikey":key,"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    return url+"/rest/v1",s

def registry(api,s):
    r=s.get(api+"/telegram_channel_registry",params={
        "select":"channel_id,title,is_private,bot_status",
        "is_private":"eq.true","limit":"1000"
    },timeout=(8,25))
    if r.status_code!=200:raise RuntimeError("registry_read_failed")
    return {int(x["channel_id"]):x for x in r.json()
            if x.get("bot_status") in ("administrator","creator") and x.get("channel_id") is not None}

def previous(api,s):
    r=s.get(api+"/"+TARGET,params={"select":"telegram_channel_id,invite_url","limit":"1000"},timeout=(8,25))
    if r.status_code!=200:raise RuntimeError("invite_lookup_failed")
    return {int(x["telegram_channel_id"]):x.get("invite_url") for x in r.json()}


def bot_api(method, payload):
    token=(os.getenv("MRXPRONOS_CANAL_BOT_TOKEN") or "").strip()
    if not token:return None
    try:
        response=requests.post("https://api.telegram.org/bot"+token+"/"+method,json=payload,timeout=(8,18))
        if response.status_code!=200:return None
        body=response.json()
        return body.get("result") if isinstance(body,dict) and body.get("ok") is True else None
    except (requests.RequestException,ValueError):
        return None

def bot_invite(cid):
    """Use existing invites or admin-granted invite creation, never bypass privileges."""
    info=bot_api("getMe",{})
    if not isinstance(info,dict) or str(info.get("username","")).casefold()!="mrxpronos_canal_bot":
        return None,"bot_unverified"
    bot_id=info.get("id")
    if not isinstance(bot_id,int):return None,"bot_unverified"
    member=bot_api("getChatMember",{"chat_id":cid,"user_id":bot_id})
    if not isinstance(member,dict) or member.get("status") not in ("creator","administrator"):
        return None,"bot_not_admin"
    chat=bot_api("getChat",{"chat_id":cid})
    existing=(chat or {}).get("invite_link") if isinstance(chat,dict) else None
    if existing and INVITE.fullmatch(existing):return existing,"bot_existing"
    if member.get("status")=="creator" or member.get("can_invite_users") is True:
        created=bot_api("createChatInviteLink",{"chat_id":cid,"name":"CineRadarDirectory"})
        invite=created.get("invite_link") if isinstance(created,dict) else None
        if invite and INVITE.fullmatch(invite):return invite,"bot_created"
        return None,"bot_create_failed"
    return None,"bot_no_invite_permission"

async def run():
    tg_id=os.getenv("TG_API_ID","")
    tg_hash=os.getenv("TG_API_HASH","")
    tg_session=os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or os.getenv("TG_STREAM_SESSION")
    if not tg_id.isdigit() or not tg_hash or not tg_session:
        raise RuntimeError("personal_session_missing")
    api,s=session()
    rows=registry(api,s); prior=previous(api,s)
    client=TelegramClient(StringSession(tg_session),int(tg_id),tg_hash,
        request_retries=0,connection_retries=2,flood_sleep_threshold=0,receive_updates=False)
    seen=0; confirmed=0; stored=0; unavailable=0; skipped_sensitive=0; reasons={}
    await client.connect()
    try:
        if not await client.is_user_authorized(): raise RuntimeError("personal_session_not_authorized")
        me=await client.get_me()
        async for d in client.iter_dialogs():
            entity=d.entity
            if not isinstance(entity,Channel) or not getattr(entity,"broadcast",False):
                continue
            seen+=1
            if seen>MAX_SCAN:break
            cid=utils.get_peer_id(entity)
            registered=rows.get(cid)
            if not registered or entity.username:continue
            target=classify(registered["title"])
            if not target:continue
            kind,secondary,sensitive=target
            if sensitive:
                skipped_sensitive+=1
                # Retain this channel in the secure registry, but do not feature it
                # publicly until an age-restricted presentation is available.
            try:
                permissions=await client.get_permissions(entity,me)
                is_admin=bool(getattr(entity,"creator",False) or getattr(entity,"admin_rights",None)
                    or getattr(permissions,"is_creator",False) or getattr(permissions,"is_admin",False))
                if not is_admin:continue
                confirmed+=1
                existing=prior.get(cid)
                if existing and INVITE.fullmatch(existing):
                    invite=existing
                else:
                    full=await client(GetFullChannelRequest(entity))
                    export=getattr(full.full_chat,"exported_invite",None)
                    invite=getattr(export,"link",None)
                    if not invite or not INVITE.fullmatch(invite):
                        rights=getattr(entity,"admin_rights",None)
                        can_invite=bool(getattr(entity,"creator",False) or getattr(rights,"invite_users",False))
                        if can_invite:
                            invite=(await client(ExportChatInviteRequest(entity))).link
                        else:
                            invite,reason=bot_invite(cid)
                            if not invite:
                                reasons[reason]=reasons.get(reason,0)+1
                                unavailable+=1
                                continue
                if not invite or not INVITE.fullmatch(invite):
                    reasons["invalid_invite"]=reasons.get("invalid_invite",0)+1
                    unavailable+=1
                    continue
                payload={
                  "telegram_channel_id":cid,"title":str(entity.title or registered["title"])[:160],
                  "category":kind,"secondary_category":secondary,"invite_url":invite,
                  "public_username":None,"is_sensitive":bool(sensitive),
                  "personal_admin_confirmed":True,"bot_admin_confirmed":True,
                  "verified_at":datetime.now(timezone.utc).isoformat()
                }
                post=s.post(api+"/"+TARGET,params={"on_conflict":"telegram_channel_id"},
                    headers={"Prefer":"resolution=merge-duplicates,return=minimal"},
                    json=payload,timeout=(8,25))
                if post.status_code not in (200,201,204):
                    reasons["supabase_save_failed"]=reasons.get("supabase_save_failed",0)+1
                    unavailable+=1
                    continue
                stored+=1
            except Exception as exc:
                # Never print private IDs, titles, links, session, or Telegram response strings.
                unavailable+=1
                reasons[type(exc).__name__]=reasons.get(type(exc).__name__,0)+1
    finally:
        await client.disconnect()
        s.close()
    print("OWNED_PRIVATE_DISCOVERY",{"broadcast_seen":seen,"qualified_admin":confirmed,
        "stored":stored,"unavailable":unavailable,"sensitive_deferred":skipped_sensitive,"reasons":reasons})

if __name__=="__main__":
    try:asyncio.run(run())
    except Exception as e:
        print("::error::OWNED_PRIVATE_DISCOVERY_FAILED",type(e).__name__)
        sys.exit(1)
