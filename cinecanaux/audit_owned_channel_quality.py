#!/usr/bin/env python3
"""Read-only Telegram metadata audit for featured Cine Radar channels.
Audit only IDs/categories already publicly listed. Never download posts or messages,
and never print/write private invite URLs, Telegram account keys or raw message text.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl.types import Channel
from telethon.errors import FloodWaitError

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/"assets"/"owned_channel_quality.json"
BASE="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev"
HANDLE=re.compile(r"^https://t\.me/([A-Za-z][A-Za-z0-9_]{4,31})/?$",re.I)
LIMIT=200

def catalog():
    all_rows=[]
    with requests.Session() as http:
        for offset in range(0,480,80):
            r=http.get(BASE+"/api/search",params={"sort":"relevant","limit":80,"offset":offset},
                timeout=(8,30),headers={"Accept":"application/json","User-Agent":"CineRadarQualityAudit/1.0"})
            r.raise_for_status()
            body=r.json()
            rows=body.get("channels",[])
            if not isinstance(rows,list):raise RuntimeError("invalid_public_directory")
            all_rows.extend(x for x in rows if isinstance(x,dict) and x.get("featured") is True)
            if not rows or offset+80>=int(body.get("total",len(rows))):break
    return list({int(x["id"]):x for x in all_rows if isinstance(x.get("id"),int)}.values())

def private_chats():
    root=str(os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key=str(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not root.startswith("https://") or not root.endswith(".supabase.co") or not key:
        raise RuntimeError("private_registry_credentials_missing")
    r=requests.get(root+"/rest/v1/cine_radar_owned_invites",
       params={"select":"telegram_channel_id,invite_url,is_sensitive,personal_admin_confirmed,bot_admin_confirmed",
         "personal_admin_confirmed":"eq.true","bot_admin_confirmed":"eq.true","is_sensitive":"eq.false","limit":1000},
       headers={"apikey":key,"Authorization":"Bearer "+key},timeout=(8,25))
    r.raise_for_status()
    # Map in memory only; no private links go into the report.
    return {str(x.get("invite_url")):int(x["telegram_channel_id"]) for x in r.json()}

def verify_avatar(row):
    id=int(row["id"])
    try:
        r=requests.get(BASE+"/assets/channel-avatar/"+str(id)+".jpg",
            timeout=(8,20),headers={"Accept":"image/*","User-Agent":"CineRadarQualityAudit/1.0"},
            params={"v":"audit-20261118"})
        mime=str(r.headers.get("content-type") or "").lower()
        source=str(r.headers.get("x-cineradar-avatar") or "")
        if r.status_code==200 and source=="telegram" and mime.startswith("image/") and len(r.content)>200:
            return "real"
        if r.status_code==200 and (source=="fallback" or "svg" in mime):
            return "fallback"
    except requests.RequestException:
        pass
    return "unknown"

async def run():
    rows=catalog()
    invite_map=private_chats()
    api_id=str(os.getenv("TG_API_ID") or "")
    api_hash=str(os.getenv("TG_API_HASH") or "")
    session=str(os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or os.getenv("TG_STREAM_SESSION") or "")
    if not api_id.isdigit() or not api_hash or not session:raise RuntimeError("telegram_credentials_missing")
    now=datetime.now(timezone.utc)
    metrics={}
    private_targets={}
    public_targets={}
    for row in rows:
        id=int(row["id"])
        metrics[id]={"channel_id":id,"avatar_status":verify_avatar(row),"audit_status":"unknown",
            "total_posts":None,"sampled_posts":0,"posts_7d":None,"posts_30d":None,
            "media_30d":None,"last_post_at":None,"observed_at":now.isoformat()}
        if row.get("private_channel") is True:
            if row.get("link") in invite_map:private_targets[invite_map[row["link"]]]=id
        else:
            name=HANDLE.fullmatch(str(row.get("link") or ""))
            if name:public_targets[name.group(1).lower()]=id

    client=TelegramClient(StringSession(session),int(api_id),api_hash,request_retries=0,
        connection_retries=2,flood_sleep_threshold=0,receive_updates=False)
    await client.connect()
    seen=set()
    try:
        if not await client.is_user_authorized():raise RuntimeError("session_not_authorized")
        async def inspect(entity,id):
            try:
                # A maximum of 200 message metadata records; no bodies/images/videos downloaded.
                sample=await client.get_messages(entity,limit=LIMIT)
                total=int(sample.total) if isinstance(getattr(sample,"total",None),int) else None
                posts=[m for m in sample if getattr(m,"date",None) is not None and not getattr(m,"action",None)]
                last=max((m.date for m in posts),default=None)
                recent7=sum(m.date>=now-timedelta(days=7) for m in posts)
                recent30=sum(m.date>=now-timedelta(days=30) for m in posts)
                media30=sum(m.date>=now-timedelta(days=30) and
                    (getattr(m,"photo",None) is not None or getattr(m,"document",None) is not None)
                    for m in posts)
                metrics[id].update(audit_status="verified",total_posts=total,sampled_posts=len(posts),
                    posts_7d=recent7,posts_30d=recent30,media_30d=media30,
                    last_post_at=last.isoformat() if last else None)
            except FloodWaitError:
                metrics[id]["audit_status"]="unavailable"
                raise
            except Exception:
                metrics[id]["audit_status"]="unavailable"
            finally:
                await asyncio.sleep(0.8)

        async for dialog in client.iter_dialogs():
            entity=dialog.entity
            if not isinstance(entity,Channel) or not getattr(entity,"broadcast",False):continue
            full_id=utils.get_peer_id(entity)
            username=str(getattr(entity,"username","") or "").lower()
            id=private_targets.get(full_id) or public_targets.get(username)
            if not id or id in seen:continue
            seen.add(id)
            try:await inspect(entity,id)
            except FloodWaitError:break

        for username,id in public_targets.items():
            if id in seen:continue
            try:
                entity=await client.get_entity("@"+username)
                if not isinstance(entity,Channel) or not entity.broadcast:continue
                seen.add(id)
                await inspect(entity,id)
            except FloodWaitError:break
            except Exception:
                metrics[id]["audit_status"]="unavailable"
    finally:
        await client.disconnect()
    records=sorted(metrics.values(),key=lambda x:x["channel_id"])
    payload={"version":1,"source":"Telegram authorized account (metadata-only)",
      "sample_limit":LIMIT,"observed_at":now.isoformat(),"channels":records}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("QUALITY_AUDIT_SUMMARY",{"featured":len(records),
      "verified":sum(x["audit_status"]=="verified" for x in records),
      "real_avatars":sum(x["avatar_status"]=="real" for x in records),
      "fallback_avatars":sum(x["avatar_status"]=="fallback" for x in records)})
    for x in records:
        print("CHANNEL_QUALITY",{"id":x["channel_id"],"avatar":x["avatar_status"],
            "activity":x["audit_status"],"total":x["total_posts"],
            "recent7":x["posts_7d"],"recent30":x["posts_30d"]})
if __name__=="__main__":
    asyncio.run(run())
