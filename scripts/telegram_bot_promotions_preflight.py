#!/usr/bin/env python3
"""Read-only production preflight: Telegram publishing bot, two allowed channels, ledger.

Never sends messages. Never logs chat IDs or secrets.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from telegram_promo_channels import promo_channels
from telegram_bot_buttons_daily import validate_templates


class PreflightError(RuntimeError):
    pass


def bot_read(session, token, method, payload):
    try:
        response = session.post(
            "https://api.telegram.org/bot" + token + "/" + method,
            json=payload, timeout=(8, 25))
        data = response.json()
    except (requests.RequestException, ValueError):
        raise PreflightError("Bot API read unavailable (" + method + ")") from None
    if not response.ok or not isinstance(data, dict) or data.get("ok") is not True:
        raise PreflightError("Bot API read rejected (" + method + ")")
    return data.get("result")


def check_ledger(session, url, service_key):
    if not url.startswith("https://") or not service_key:
        raise PreflightError("Supabase ledger credentials absent")
    try:
        res = session.get(url.rstrip("/") + "/rest/v1/telegram_promo_deliveries",
                          params={"select": "campaign", "limit": "1"},
                          headers={"apikey": service_key, "Authorization": "Bearer " + service_key},
                          timeout=(8, 25))
        data = res.json()
    except (requests.RequestException, ValueError):
        raise PreflightError("Supabase ledger unavailable") from None
    if not res.ok or not isinstance(data, list):
        raise PreflightError("Supabase ledger read refused")


def check_channels(session, token, first, second):
    configured = promo_channels(first, second)
    me = bot_read(session, token, "getMe", {})
    if not isinstance(me, dict) or me.get("is_bot") is not True or int(me.get("id") or 0) <= 0:
        raise PreflightError("Invalid publishing bot identity")
    bot_id = me["id"]
    checked = set()
    for _, channel in configured:
        chat = bot_read(session, token, "getChat", {"chat_id":channel})
        if not isinstance(chat,dict) or chat.get("type") != "channel":
            raise PreflightError("Promotional destination is not a channel")
        cid = chat.get("id")
        if not isinstance(cid, int) or cid in checked:
            raise PreflightError("Telegram destinations resolve to the same channel")
        checked.add(cid)
        if str(chat.get("title") or "").strip().casefold() == "cinéx — stock privé":
            raise PreflightError("Private CineX film stock cannot be a promo destination")
        member = bot_read(session, token, "getChatMember",
                          {"chat_id":cid, "user_id":bot_id})
        status = (member or {}).get("status")
        if status != "creator" and not (status == "administrator" and member.get("can_post_messages") is True):
            raise PreflightError("Publisher lacks channel posting rights")
    return len(checked)


def campaign_status():
    from send_day_based_bookmaker_promos import PROMOS, PARTNERS
    from send_daily_bookmaker_bonus_ads import WEEK_ROTATION as BW, BOOKMAKERS
    from send_daily_bookmaker_guide import WEEK_ROTATION as GW, PARTNERS as GP
    weekday = datetime.now(timezone.utc).weekday()
    day = {x.strip().lower() for x in os.getenv("TELEGRAM_APPROVED_DAY_PROMOS","").split(",") if x.strip()}
    bonus = {x.strip().lower() for x in os.getenv("TELEGRAM_APPROVED_BONUS_BOOKMAKERS","").split(",") if x.strip()}
    guide = {x.strip().lower() for x in os.getenv("TELEGRAM_APPROVED_GUIDE_BOOKMAKERS","").split(",") if x.strip()}
    for name, aset in (("weekday",day),("bonus",bonus),("guide",guide)):
        if not aset:
            print("APPROVAL_MISSING", name, "campaign will be skipped")
    todays = [p for p in PROMOS if p.weekday == weekday and p.image.lower() in day
              and PARTNERS.get(p.bookmaker,{}).get("enabled", True)]
    applicable = {"xpvip":True, "weekday":bool(todays),
                  "bonus":BW[weekday] in bonus, "guide":GW[weekday] != "common" and GW[weekday] in guide}
    return applicable


def main():
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    first=os.getenv("TELEGRAM_CHAT_ID","").strip()
    second=os.getenv("TELEGRAM_CHAT_ID_SECONDARY","").strip()
    if not token or not first or not second:
        raise PreflightError("Publishing bot or two channel credentials missing")
    validate_templates()
    with requests.Session() as session:
        count = check_channels(session,token,first,second)
        check_ledger(session,os.getenv("SUPABASE_URL",""),os.getenv("SUPABASE_SERVICE_ROLE_KEY",""))
    campaigns=campaign_status()
    print("BOT_PROMOTION_PREFLIGHT_OK",json.dumps({
        "channels_authorized":count,"ledger_ok":True,"buttons_valid":True,
        "today_approved_campaigns":campaigns,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    try:
        sys.exit(main())
    except (PreflightError, ValueError) as exc:
        print("BOT_PROMOTION_PREFLIGHT_FAILED",str(exc),file=sys.stderr)
        sys.exit(1)
