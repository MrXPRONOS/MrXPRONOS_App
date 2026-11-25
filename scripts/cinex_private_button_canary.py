#!/usr/bin/env python3
"""One-time CineX PRIVATE stock CTA canary: now and ~30m later by GitHub Actions.

No personal Telegram session. Does not consult Cloudflare D1 while its quota is exhausted.
Uses existing explicitly owner-approved CineX stock SHA-256, Telegram bot identity/private
channel checks, and atomic Supabase reservation. Never prints sensitive chat IDs/tokens.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

EXPECTED_STOCK_SHA256 = "57b1f0a97d7db124ab9f72f470f7d63b92960e06b876397795e5780f5c5cc2b8"
STOCK_NAME = "CinéX — Stock privé"
BOT_USERNAME = "cineradarfr_bot"
BUTTON_TEXT = "🎬 Ouvrir Ciné Radar"
BUTTON_URL = "https://t.me/CineRadarFr_Bot"
KEYBOARD = {"inline_keyboard": [[{"text": BUTTON_TEXT, "url": BUTTON_URL}]]}
CAMPAIGN_PREFIX = "cinex-private-canary-20261125"
TEXTS = {
    "now": "🧪 MR XPRONOS — TEST 1/2 : publication immédiate avec bouton. Canal privé CineX. Ne pas relayer.",
    "later": "🧪 MR XPRONOS — TEST 2/2 : publication différée d’environ 30 minutes avec bouton. Canal privé CineX. Ne pas relayer.",
}


class CanaryError(RuntimeError):
    pass


def _api(session, token, endpoint, payload):
    if not token:
        raise CanaryError("CineRadar bot token missing")
    try:
        r = session.post("https://api.telegram.org/bot" + token + "/" + endpoint,
                         json=payload, timeout=(8, 30))
        obj = r.json()
    except (requests.RequestException, ValueError):
        raise CanaryError("Uncertain Telegram response: " + endpoint) from None
    if not r.ok or not isinstance(obj,dict) or obj.get("ok") is not True:
        raise CanaryError("Telegram rejected: " + endpoint)
    return obj.get("result")


def verify_private_destination(session, token, stock_id):
    if not re.fullmatch(r"-100[0-9]{5,}", stock_id or ""):
        raise CanaryError("Approved private stock ID is not configured")
    if hashlib.sha256(stock_id.encode("utf-8")).hexdigest() != EXPECTED_STOCK_SHA256:
        raise CanaryError("Private stock does not match previously approved SHA-256")
    me = _api(session,token,"getMe",{})
    if (not isinstance(me,dict) or not me.get("is_bot")
        or str(me.get("username") or "").casefold() != BOT_USERNAME):
        raise CanaryError("Wrong Telegram bot identity")
    cid = int(stock_id)
    info = _api(session,token,"getChat",{"chat_id":cid})
    if (not isinstance(info,dict) or info.get("id") != cid
        or info.get("type") != "channel" or info.get("username")
        or info.get("title") != STOCK_NAME):
        raise CanaryError("Destination is not verified private CineX film stock")
    admin = _api(session,token,"getChatMember",{"chat_id":cid,"user_id":me["id"]})
    if not isinstance(admin,dict) or not (admin.get("status") == "creator"
         or (admin.get("status") == "administrator" and admin.get("can_post_messages") is True)):
        raise CanaryError("Bot cannot post to private stock")
    return cid


def reserve_once(session, service_url, service_key, chat_id, phase):
    if not service_url.startswith("https://") or not service_key:
        raise CanaryError("Missing secure Supabase idempotency store")
    url = service_url.rstrip("/") + "/rest/v1/telegram_promo_deliveries"
    day = datetime.now(timezone.utc).date().isoformat()
    campaign = CAMPAIGN_PREFIX + "-" + phase
    headers = {
        "apikey": service_key,
        "Authorization": "Bearer " + service_key,
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates,return=representation",
    }
    params={"on_conflict":"campaign,delivery_day,chat_id"}
    try:
        r=session.post(url,params=params,headers=headers,
                       json={"campaign":campaign,"delivery_day":day,"chat_id":str(chat_id)},
                       timeout=(8,25))
        body=r.json()
    except (requests.RequestException, ValueError):
        raise CanaryError("Idempotency reservation uncertain; do not retry") from None
    if not r.ok or not isinstance(body,list):
        raise CanaryError("Supabase idempotency unavailable")
    if not body:
        raise CanaryError("Canary already attempted; no duplicate will be sent")
    return url, day, campaign, headers


def confirm_delivered(session, record, chat_id):
    url,day,campaign,headers=record
    try:
        r=session.patch(url, params={"campaign":"eq."+campaign,
                 "delivery_day":"eq."+day, "chat_id":"eq."+str(chat_id)},
                 headers=headers,json={"status":"sent","sent_at":datetime.now(timezone.utc).isoformat()},
                 timeout=(8,25))
    except requests.RequestException:
        raise CanaryError("Post delivered but ledger update uncertain") from None
    if not r.ok:
        raise CanaryError("Post delivered but ledger update failed")


def run(session, *, phase, stock_id, bot_token, supabase_url, service_key):
    if phase not in TEXTS:
        raise CanaryError("Unknown test phase")
    chat_id = verify_private_destination(session, bot_token, stock_id)
    record = reserve_once(session,supabase_url,service_key,chat_id,phase)
    # Important: do not retry if the HTTP response is lost; reservation remains.
    result=_api(session,bot_token,"sendMessage",{
        "chat_id":chat_id,
        "text":TEXTS[phase],
        "disable_notification":True,
        "protect_content":True,
        "reply_markup":KEYBOARD,
    })
    if not isinstance(result,dict) or int(result.get("message_id") or 0)<=0 or (
            result.get("chat") or {}).get("id")!=chat_id or result.get("text")!=TEXTS[phase]:
        raise CanaryError("Telegram returned unexpected receipt; send remains reserved")
    keyboard=(result.get("reply_markup") or {}).get("inline_keyboard") or []
    if not any(b.get("text")==BUTTON_TEXT and b.get("url")==BUTTON_URL
               for row in keyboard for b in row if isinstance(b,dict)):
        raise CanaryError("Bot message confirmed but CTA button missing")
    confirm_delivered(session,record,chat_id)
    print("CINEX_PRIVATE_CANARY_VERIFIED",phase,
          "button_confirmed",True,
          "message_id",result["message_id"],
          "destination","approved_private_stock",
          "removed",False)
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--phase",choices=("now","later"),required=True)
    args=parser.parse_args()
    if os.getenv("CINEX_PRIVATE_CANARY_ENABLED")!="1":
        raise CanaryError("Canary is disabled")
    with requests.Session() as session:
        run(session,phase=args.phase,
            stock_id=os.getenv("CINEX_UNIFIED_PRIVATE_CHANNEL",""),
            bot_token=os.getenv("CINEX_RADAR_BOT_TOKEN",""),
            supabase_url=os.getenv("SUPABASE_URL",""),
            service_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY",""))
    return 0


if __name__=="__main__":
    try:
        sys.exit(main())
    except CanaryError as exc:
        print("CINEX_PRIVATE_CANARY_FAILED",str(exc),file=sys.stderr)
        sys.exit(1)
