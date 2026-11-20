#!/usr/bin/env python3
"""Inspect current Telegram Bot API permissions without modifying any channel.

No Telegram *user* credentials or session, no Telethon, no log of bot secrets,
channel identifiers, invite links, private chat IDs, or raw webhook payloads.
All comparisons and output refer to named logical channel categories only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from audit_series_bots import BotAPI,parse_channel_ids
from publish_individual_series_bot import d1

REPORT = Path("cinex-bot-permissions-report.json")
EXCESS = (
    "can_promote_members",
    "can_change_info",
    "can_restrict_members",
    "can_delete_messages",
    "can_manage_video_chats",
    "can_post_stories",
    "can_edit_stories",
    "can_delete_stories",
)
SENSITIVE_DESTINATIONS = frozenset({"series_main","series_rescue","films_main","films_rescue"})
BOT_TOKENS = (
    ("publisher", "CINEX_PUBLISH_BOT_TOKEN"),
    ("radar", "CINEX_RADAR_BOT_TOKEN"),
    ("secondary", "ALT_TELEGRAM_BOT_TOKEN"),
    ("desir", "ALT_DESIR_BOT_TOKEN"),
    ("action", "ALT_ACTION_BOT_TOKEN"),
    ("anime", "ALT_ANIME_BOT_TOKEN"),
)


def channel_targets():
    sources=parse_channel_ids(os.getenv("CINEX_SERIES_CHANNEL_IDS",""))
    targets=[
        ("series_main", "@seriesvf_cinex"),
        ("series_rescue", "-1003822435811"),
        ("films_main", "@CineXFilms_vf"),
        ("franchise_source", "@fastandfuriousvffr"),
    ]
    # The films' rescue is read from the private canonical D1 config rather
    # than a hardcoded stale ID. No invite URL leaves this process.
    try:
        rows=d1("SELECT rescue_chat_id FROM cine_classic_rescue_config WHERE LOWER(public_handle)=?",
                ["@cinexfilms_vf"])
        if len(rows)==1 and str(rows[0].get("rescue_chat_id","")).startswith("-100"):
            targets.append(("films_rescue",str(rows[0]["rescue_chat_id"])))
    except RuntimeError:
        print("PERMISSIONS_RESCUE_D1_UNAVAILABLE: films rescue omitted; no Telegram actions performed")
    for i,source in enumerate(sources,1):
        targets.append(("series_source_%02d" % i,source))
    return targets


def inspect_permission(member:dict, *, destination:bool):
    status=str(member.get("status") or "unknown")
    if status not in ("administrator","creator"):
        return {"access":status,"can_publish":False,"dangerous":[]}
    # Bot creator status is unusual and grants all rights. Do not suggest
    # automatically revoking it; manual review is needed.
    sensitive=sorted(x for x in EXCESS if member.get(x) is True)
    return {"access":status,"can_publish":status=="creator" or
            bool(member.get("can_post_messages")) if destination else None,
            "dangerous":sensitive}


def audit_permissions(bot_candidates,targets):
    result={"bot_count":0,"channel_categories":len(targets),
            "checks":[],"manual_review_count":0,"unreachable_count":0}
    seen=set()
    for label,token in bot_candidates:
        token=token.strip()
        if not token or token in seen:continue
        seen.add(token)
        bot=BotAPI(token)
        try:
            who=bot.call("getMe",{})
            user_id=int(who["id"])
            if not who.get("is_bot") and who.get("is_bot") is not None:
                raise ValueError("Unexpected bot identity")
        except (RuntimeError,TypeError,ValueError,KeyError):
            result["unreachable_count"]+=1
            result["checks"].append({"bot_label":label,"category":"identity","access":"unavailable"})
            continue
        result["bot_count"]+=1
        for category,chat in targets:
            try:
                rights=bot.call("getChatMember",{"chat_id":chat,"user_id":user_id})
                info=inspect_permission(rights,destination=category in SENSITIVE_DESTINATIONS)
                checked={"bot_label":label,"category":category,**info}
                if info["dangerous"]:
                    result["manual_review_count"]+=1
                if info["can_publish"] is False and category in SENSITIVE_DESTINATIONS:
                    checked["publisher_rights_missing"]=True
                result["checks"].append(checked)
            except (RuntimeError,TypeError,KeyError,ValueError):
                result["unreachable_count"]+=1
                result["checks"].append({"bot_label":label,"category":category,"access":"unavailable"})
    return result


def main():
    candidates=[(label,os.getenv(name,"")) for label,name in BOT_TOKENS]
    targets=channel_targets()
    report=audit_permissions(candidates,targets)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("CINEX_BOT_RIGHTS_SUMMARY",json.dumps(
        {k:v for k,v in report.items() if k!="checks"},ensure_ascii=False))
    for c in report["checks"]:
        print("CINEX_BOT_RIGHTS",c["bot_label"],c["category"],
              c["access"],"excess",",".join(c.get("dangerous",[])) or "-")
    # Extra privileges need the owner to review them inside Telegram;
    # do not alter roles or fail cron jobs based on the observation.
    return 0


if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as error:
        REPORT.write_text(json.dumps({"status":"unavailable","reason":type(error).__name__}),
                          encoding="utf-8")
        print("CINEX_BOT_RIGHTS_AUDIT_UNAVAILABLE",type(error).__name__,file=sys.stderr)
        sys.exit(1)
