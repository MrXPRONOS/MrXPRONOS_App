#!/usr/bin/env python3
"""Cache real profile photos of verified private Telegram channels already listed in Cine Radar.
Never log, persist or publish private invite URLs or Telegram numeric chat IDs.
Only small channel-avatar JPEG thumbnails are made public, as the channels are in the directory.
"""
import asyncio
import io
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone

import requests
from PIL import Image, ImageOps
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl.types import Channel

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"assets"/"avatars"
DIRECTORY="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/api/search"

def directory():
    result=[]
    for offset in range(0,400,80):
        req=Request(DIRECTORY+f"?limit=80&offset={offset}",headers={"Accept":"application/json","User-Agent":"CineRadarAvatarRefresh/2.0"})
        with urlopen(req,timeout=20) as response:
            payload=json.load(io.TextIOWrapper(response,encoding="utf8"))
        items=payload.get("channels",[])
        if not isinstance(items,list):raise RuntimeError("invalid_directory")
        result.extend(x for x in items if isinstance(x,dict) and x.get("private_channel") is True)
        if offset+80>=int(payload.get("total",len(items))) or not items:break
    return result

def private_map():
    url=(os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key=(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url.startswith("https://") or not url.endswith(".supabase.co") or not key:
        raise RuntimeError("private_registry_credentials_missing")
    response=requests.get(url+"/rest/v1/cine_radar_owned_invites",params={
       "select":"telegram_channel_id,invite_url,personal_admin_confirmed,bot_admin_confirmed,is_sensitive",
       "personal_admin_confirmed":"eq.true","bot_admin_confirmed":"eq.true","is_sensitive":"eq.false","limit":1000
    },headers={"apikey":key,"Authorization":"Bearer "+key},timeout=(8,25))
    if response.status_code!=200:raise RuntimeError("private_registry_query_failed")
    return {str(r["invite_url"]):int(r["telegram_channel_id"]) for r in response.json()}

async def run():
    key=os.getenv("TG_API_ID","").strip()
    ahash=os.getenv("TG_API_HASH","").strip()
    session=(os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or os.getenv("TG_STREAM_SESSION") or "").strip()
    if not key.isdigit() or not ahash or not session:raise RuntimeError("telegram_credentials_missing")
    own=private_map()
    channels=directory()
    jobs={}
    for c in channels:
        link=str(c.get("link") or "")
        rowid=c.get("id")
        if link not in own:continue
        if not isinstance(rowid,int) or rowid<1:continue
        jobs[own[link]]=rowid
    if not jobs:
        print("PRIVATE_AVATAR_REFRESH_EMPTY",{"directory":len(channels),"registered":len(own)})
        return
    OUT.mkdir(parents=True,exist_ok=True)
    refreshed=0;no_photo=0;errors=0;seen=set()
    client=TelegramClient(StringSession(session),int(key),ahash,request_retries=0,connection_retries=2,flood_sleep_threshold=0,receive_updates=False)
    await client.connect()
    try:
        if not await client.is_user_authorized():raise RuntimeError("telegram_session_not_authorized")
        async for dialog in client.iter_dialogs():
            entity=dialog.entity
            if not isinstance(entity,Channel) or not entity.broadcast:continue
            cid=utils.get_peer_id(entity)
            if cid not in jobs:continue
            idx=jobs[cid];seen.add(cid)
            if not getattr(entity,"photo",None):
                no_photo+=1
                continue
            try:
                path=await client.download_profile_photo(entity,file=bytes)
                if not path or len(path)>6_000_000:
                    no_photo+=1
                    continue
                with Image.open(io.BytesIO(path)) as img:
                    thumb=ImageOps.fit(img.convert("RGB"),(256,256),method=Image.Resampling.LANCZOS)
                    thumb.save(OUT/("d1_"+str(idx)+".jpg"),"JPEG",quality=84,optimize=True,progressive=True)
                refreshed+=1
            except Exception as e:
                errors+=1
                print("PRIVATE_AVATAR_UNAVAILABLE",type(e).__name__)
            await asyncio.sleep(1)
    finally:
        await client.disconnect()
    print("PRIVATE_AVATAR_REFRESH",{"matched":len(jobs),"accessed":len(seen),"refreshed":refreshed,"without_photo":no_photo,"errors":errors})
if __name__=="__main__":asyncio.run(run())
