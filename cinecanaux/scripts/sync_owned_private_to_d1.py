#!/usr/bin/env python3
"""Push verified Cine Radar owned-channel invites from private Supabase storage into Cloudflare D1.
Never print invitation links or private Telegram IDs. Only non-sensitive channels are published.
Requires a scoped Cloudflare API token with D1 write permission.
"""
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone, timedelta
import requests

ACCOUNT="9c86118191b804d91b5f5b2c89114999"
DATABASE="fa8b5009-bc1a-4a6e-b143-7a487c7297a5"
INVITE=re.compile(r"^https://t[.]me/(?:[+][A-Za-z0-9_-]{12,}|joinchat/[A-Za-z0-9_-]{12,})$")
def compact(t):
    return "".join(x for x in unicodedata.normalize('NFD',str(t or '').casefold())
        if x.isalnum() and not unicodedata.combining(x))
def run():
    token=(os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN") or "").strip()
    if not token:
        print("PRIVATE_SYNC_PENDING_CLOUDFLARE_TOKEN")
        return 0
    base=(os.getenv("SUPABASE_URL") or "").rstrip("/")
    key=(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not base.startswith("https://") or not base.endswith(".supabase.co") or not key:
        raise RuntimeError("supabase_credentials_missing")
    s=requests.Session()
    s.headers.update({"apikey":key,"Authorization":"Bearer "+key})
    response=s.get(base+"/rest/v1/cine_radar_owned_invites",params={
      "select":"telegram_channel_id,title,category,secondary_category,invite_url,is_sensitive,personal_admin_confirmed,bot_admin_confirmed,verified_at",
      "personal_admin_confirmed":"eq.true","bot_admin_confirmed":"eq.true","limit":"1000"
    },timeout=(8,25))
    if response.status_code!=200:raise RuntimeError("invite_registry_read_failed")
    entries=response.json()
    cloud=requests.Session()
    cloud.headers.update({"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    endpoint=f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/d1/database/{DATABASE}/query"
    inserted=0;skipped=0
    for row in entries:
        title=str(row.get("title") or "").strip()[:160]
        url=str(row.get("invite_url") or "").strip()
        category=str(row.get("category") or "")
        try: verified=datetime.fromisoformat(str(row.get("verified_at") or "").replace("Z","+00:00"))
        except ValueError: skipped+=1;continue
        if verified.tzinfo is None or verified<datetime.now(timezone.utc)-timedelta(days=31):
            skipped+=1;continue
        if not INVITE.fullmatch(url) or category not in {"films","series","animes"} or not title:
            skipped+=1;continue
        if "torrent9" in compact(title) or row.get("is_sensitive") is True:
            skipped+=1;continue
        chatid=str(row["telegram_channel_id"])
        calls=[
          ("INSERT INTO channels(title,link,description,content_type,genre,status,rights_confirmed,language) VALUES(?,?,?,?,'general','approved',0,'unknown') ON CONFLICT(link) DO UPDATE SET title=excluded.title,content_type=excluded.content_type,updated_at=CURRENT_TIMESTAMP",
            [title,url,"Canal Telegram privé — invitation administrée",category]),
          ("INSERT OR IGNORE INTO channel_index_meta(channel_id,listing_status,link_status,telegram_chat_id) SELECT id,'listed','private',? FROM channels WHERE link=?",
            [chatid,url]),
          ("INSERT INTO owned_channel_features(channel_id,source,verification,priority,primary_category,private_channel,telegram_chat_id,enabled,last_verified_at) SELECT id,'telegram_admin_registry','both_admins',4,?,1,?,1,CURRENT_TIMESTAMP FROM channels WHERE link=? ON CONFLICT(channel_id) DO UPDATE SET verification='both_admins',priority=excluded.priority,primary_category=excluded.primary_category,private_channel=1,telegram_chat_id=excluded.telegram_chat_id,last_verified_at=CURRENT_TIMESTAMP",
            [category,chatid,url]),
          ("INSERT OR IGNORE INTO channel_categories(channel_id,category) SELECT id,? FROM channels WHERE link=?",
            [category,url])
        ]
        if row.get("secondary_category"):
            calls.append(("INSERT OR IGNORE INTO channel_categories(channel_id,category) SELECT id,? FROM channels WHERE link=?",
               [str(row["secondary_category"])[:35],url]))
        for sql,params in calls:
            out=cloud.post(endpoint,json={"sql":sql,"params":params},timeout=(8,30))
            if out.status_code!=200 or out.json().get("success") is not True:
                raise RuntimeError("cloudflare_d1_write_failed")
        inserted+=1
    print("PRIVATE_SYNC_COMPLETE",{"listed":inserted,"skipped":skipped})
    s.close();cloud.close()
    return 0
if __name__=="__main__":
    try:sys.exit(run())
    except Exception as e:
        print("::error::PRIVATE_SYNC_FAILED",type(e).__name__)
        sys.exit(1)
