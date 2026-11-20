#!/usr/bin/env python3
"""Bot-only CinéX Séries: publish existing season posters to main and rescue.

Unlike the full-delivery workflow, posters may be shown while a season is ongoing.
The Radar deep link says 'availability', not 'download all seasons', until the
catalogue completeness gate is true. Bot delivery still enforces that gate.
No user Telegram session, no history scraping, no auto-filled episode totals.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import time
from pathlib import Path

from audit_series_bots import BotAPI, identify_radar_bot, parse_channel_ids
from publish_individual_series_bot import (
    PUBLIC, RESCUE, HANDLE, INVITE, FOLDER, TOKEN, d1,
    request_bot, check_publisher, rescue_link, catalogue_complete,
)

REPORT=Path("cinex-series-showcase-publish-report.json")
CHAT=re.compile(r"^-100[0-9]{6,}$")


def downloadable_index(chat_id: str):
    """An available episode is downloadable even if the season is ongoing.

    Require contiguous 1..N episode references in each *indexed* season. Do
    not invent the final episode count, missing prior seasons, or future media.
    """
    rows=d1("SELECT season,episode,source_message_id FROM cine_series_episodes WHERE chat_id=? ORDER BY season,episode",[chat_id])
    if not rows or len(rows)>300:
        return {"ready":False,"count":0,"seasons":[],"reason":"no_indexed_episodes"}
    previous_season=0
    previous_episode=0
    groups=[]
    for row in rows:
        try:
            season=int(row["season"])
            episode=int(row["episode"])
            message=int(row["source_message_id"])
        except (KeyError,TypeError,ValueError):
            return {"ready":False,"count":0,"seasons":[],"reason":"invalid_media_reference"}
        if not (1<=season<=50 and 1<=episode<=100 and message>0):
            return {"ready":False,"count":0,"seasons":[],"reason":"invalid_media_reference"}
        if season != previous_season:
            if episode!=1:
                return {"ready":False,"count":0,"seasons":[],"reason":"season_index_does_not_start_at_one"}
            groups.append({"season":season,"episodes":1})
            previous_season,previous_episode=season,episode
        else:
            if episode!=previous_episode+1:
                return {"ready":False,"count":0,"seasons":[],"reason":"episode_gap"}
            groups[-1]["episodes"]+=1
            previous_episode=episode
    return {"ready":True,"count":len(rows),"seasons":groups,"reason":None}


def markup(token: str, rescue_url: str, folder_url: str, *, ready: bool):
    if not TOKEN.fullmatch(token) or not INVITE.fullmatch(rescue_url):
        raise ValueError("Boutons série: token ou secours non valide")
    rows=[
        [{"text": "📥 Télécharger" if ready else "🎬 Disponibilité sur Ciné Radar",
          "url": "https://t.me/CineRadarFr_Bot?start=sr_"+token,
          "style": "success" if ready else "primary"}],
        [{"text":"🛟 Canal de secours", "url":rescue_url,"style":"danger"}],
    ]
    if folder_url and FOLDER.fullmatch(folder_url):
        rows.append([{"text":"📂 Rejoindre le dossier Séries","url":folder_url,"style":"primary"}])
    return {"inline_keyboard":rows}


def plan_one(chat_id: str):
    source=d1("SELECT chat_id,title,publisher_access,radar_access,rights_attested,enabled FROM cine_series_channels WHERE chat_id=?", [chat_id])
    if not source:return {"chat_id":chat_id,"status":"NOT_INDEXED"}
    src=source[0]
    if src["publisher_access"]!="verified" or src["radar_access"]!="verified" or int(src["rights_attested"] or 0)!=1 or int(src["enabled"] or 0)!=1:
        return {"chat_id":chat_id,"status":"NOT_AUTHORIZED"}
    posters=d1("SELECT season,source_message_id FROM cine_series_posters WHERE chat_id=? ORDER BY season LIMIT 1",[chat_id])
    if not posters:return {"chat_id":chat_id,"status":"NO_POSTER"}
    season=int(posters[0]["season"])
    poster=int(posters[0]["source_message_id"])
    if not (1<=season<=50 and poster>0):return {"chat_id":chat_id,"status":"INVALID_POSTER"}
    current=d1("SELECT token,state,public_post_id,rescue_post_id FROM cine_series_publications WHERE chat_id=?",[chat_id])
    ready=downloadable_index(chat_id)["ready"]
    return {"chat_id":chat_id,"title":src["title"],"season":season,"poster":poster,
            "ready":ready,"status":"ALREADY_PUBLISHED" if current and current[0]["state"]=="published"
                     else "REQUIRES_MANUAL_REVIEW" if current else "READY_TO_POST",
            "existing":current[0] if current else None}


def publish_one(bot_token: str,entry: dict,rescue_url: str,folder_url: str):
    chat=entry["chat_id"]
    previous=entry["existing"]
    if previous:
        if entry["status"]!="ALREADY_PUBLISHED":
            return {"chat_id":chat,"status":"REQUIRES_MANUAL_REVIEW"}
        token=previous["token"]
        if not TOKEN.fullmatch(token) or not previous["public_post_id"] or not previous["rescue_post_id"]:
            return {"chat_id":chat,"status":"INVALID_EXISTING_RECEIPTS"}
        keyboard=markup(token,rescue_url,folder_url,ready=entry["ready"])
        for cid,mid in ((PUBLIC,previous["public_post_id"]),(RESCUE,previous["rescue_post_id"])):
            request_bot(bot_token,"editMessageReplyMarkup",{"chat_id":cid,"message_id":int(mid),"reply_markup":keyboard})
        return {"chat_id":chat,"status":"UPDATED_EXISTING","download_ready":entry["ready"]}

    if entry["status"]!="READY_TO_POST":return {"chat_id":chat,"status":entry["status"]}
    token=secrets.token_urlsafe(18)
    if not TOKEN.fullmatch(token):raise RuntimeError("Invalid random series token")
    keyboard=markup(token,rescue_url,folder_url,ready=entry["ready"])
    # Reserve unique record before any Telegram POST so an uncertain timeout
    # cannot produce duplicate public posters on rerun.
    d1("INSERT INTO cine_series_publications(token,chat_id,state) VALUES(?,?,'pending')",[token,chat])
    public=request_bot(bot_token,"copyMessage",{
        "chat_id":PUBLIC,"from_chat_id":chat,"message_id":entry["poster"],
        "reply_markup":keyboard,"disable_notification":True,
    })
    public_id=int(public["message_id"])
    if public_id<=0:raise RuntimeError("Missing public copy receipt")
    d1("UPDATE cine_series_publications SET public_post_id=?,updated_at=CURRENT_TIMESTAMP WHERE token=? AND state='pending'",
       [public_id,token])
    time.sleep(1.2)
    rescue=request_bot(bot_token,"copyMessage",{
        "chat_id":RESCUE,"from_chat_id":chat,"message_id":entry["poster"],
        "reply_markup":keyboard,"disable_notification":True,
    })
    rescue_id=int(rescue["message_id"])
    if rescue_id<=0:raise RuntimeError("Missing rescue copy receipt")
    d1("UPDATE cine_series_publications SET rescue_post_id=?,state='published',updated_at=CURRENT_TIMESTAMP WHERE token=? AND state='pending'",
       [rescue_id,token])
    return {"chat_id":chat,"status":"PUBLISHED","season_poster":entry["season"],
            "download_ready":entry["ready"],"public_message_id":public_id,
            "rescue_message_id":rescue_id}


def find_authorized_publisher(ids: list[str]):
    """Pick only a bot known to be admin in *both destinations and all sources*."""
    candidates=[
        ("FOOTBALL_NEWS_BOT_TOKEN",os.getenv("CINEX_PUBLISH_BOT_TOKEN","")),
        ("CINEX_RADAR_BOT_TOKEN",os.getenv("CINEX_RADAR_BOT_TOKEN","")),
        ("TELEGRAM_BOT_TOKEN",os.getenv("ALT_TELEGRAM_BOT_TOKEN","")),
        ("DESIR_BOT_TOKEN",os.getenv("ALT_DESIR_BOT_TOKEN","")),
        ("ACTION_BOT_TOKEN",os.getenv("ALT_ACTION_BOT_TOKEN","")),
        ("ANIME_BOT_TOKEN",os.getenv("ALT_ANIME_BOT_TOKEN","")),
        ("SERIES_BOT_TOKEN",os.getenv("ALT_SERIES_BOT_TOKEN","")),
    ]
    seen=set()
    failures=[]
    for label,token in candidates:
        token=token.strip()
        if not token or token in seen:continue
        seen.add(token)
        bot=BotAPI(token)
        user=""
        try:
            me=bot.call("getMe",{})
            user=str(me.get("username") or "")[:50]
            check_publisher(bot,PUBLIC,me["id"])
        except Exception:
            print("CINEX_SHOWCASE_ACCESS",label,"@"+(user or "unknown"),"principal=NOT_ADMIN_OR_INACCESSIBLE")
            failures.append(label+": principal")
            continue
        try:
            check_publisher(bot,RESCUE,me["id"])
        except Exception:
            print("CINEX_SHOWCASE_ACCESS",label,"@"+user,"principal=OK secours=NOT_ADMIN_OR_INACCESSIBLE")
            failures.append(label+": secours")
            continue
        bad=[]
        for cid in ids:
            try:
                bot.call("getChat",{"chat_id":cid})
                role=bot.call("getChatMember",{"chat_id":cid,"user_id":me["id"]})
                if role.get("status") not in ("administrator","creator"):bad.append(cid)
            except Exception:bad.append(cid)
        if bad:
            print("CINEX_SHOWCASE_ACCESS",label,"@"+user,"principal=OK secours=OK private_sources_not_admin="+str(len(bad)))
            failures.append(label+": sources="+str(len(bad)))
            continue
        print("CINEX_SHOWCASE_PUBLISHER_SELECTED",label,"@"+user,"sources="+str(len(ids)))
        return bot,token,me
    raise RuntimeError("Aucun bot autorisé pour principal + secours + 11 sources. Diagnostics: "+"; ".join(failures)[:320])


def execute(*,publish:bool=False):
    ids=parse_channel_ids(os.getenv("CINEX_SERIES_CHANNEL_IDS",""))
    if not ids:raise RuntimeError("Variable CINEX_SERIES_CHANNEL_IDS vide")
    if os.getenv("CINEX_SERIES_RIGHTS_ATTESTED","").lower()!="true":
        raise RuntimeError("Les droits de diffusion ne sont pas attestés")
    actual_id=identify_radar_bot(os.getenv("CINEX_RADAR_BOT_TOKEN","").strip())
    if not isinstance(actual_id,int) or actual_id<=0:raise RuntimeError("Cine Radar identity not verified")
    # Never substitute an unrelated bot for the source/destination bot.
    bot,token,me=find_authorized_publisher(ids)
    # Verified Telegram access to every source and BOTH destinations.
    main=check_publisher(bot,PUBLIC,me["id"])
    if str(main.get("username") or "").lower()!=HANDLE:raise RuntimeError("Mauvais canal principal")
    backup=check_publisher(bot,RESCUE,me["id"])
    if str(backup.get("id"))!=RESCUE:raise RuntimeError("Mauvais canal de secours")
    link=rescue_link(bot,me["id"])
    folder=os.getenv("CINEX_SERIES_FOLDER_URL","").strip()
    if folder and not FOLDER.fullmatch(folder):raise RuntimeError("Lien dossier non valide")
    gate=d1("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'")
    if not gate or gate[0]["value"]!="1":raise RuntimeError("Interrupteur de livraison arrêté")
    plans=[]
    for cid in ids:
        plans.append(plan_one(cid))
    report={"mode":"showcase_publish" if publish else "preview",
            "source_count":len(ids),"folder_button_present":bool(folder),
            "backup_link_verified":True,
            "download_ready_count":sum(bool(p.get("ready")) for p in plans),
            "channels":[{k:v for k,v in p.items() if k!="existing"} for p in plans]}
    # Rerun is safe: posts with a 'pending' receipt remain blocked for review.
    if publish:
        for item in plans:
            if item["status"] not in ("READY_TO_POST","ALREADY_PUBLISHED"):continue
            try:
                result=publish_one(token,item,link,folder)
                report["channels"][plans.index(item)]={"title":item.get("title"),**result}
                print("CINEX_SHOWCASE",item["chat_id"],result["status"])
                if result["status"]=="PUBLISHED":time.sleep(1.25)
            except Exception as error:
                report["channels"][plans.index(item)]={"chat_id":item["chat_id"],
                    "status":"MANUAL_REVIEW_REQUIRED","error":str(error)[:130]}
                # Stop: an uncertain Telegram result or rate limit must not create
                # a cascade of partial posts.
                break
    else:
        for p in plans:print("CINEX_SHOWCASE_PREVIEW",p["chat_id"],p["status"],"download_ready",p.get("ready",False))
    return report


if __name__=="__main__":
    try:
        publishing=os.getenv("CINEX_SHOWCASE_PUBLISH","false").lower()=="true"
        result=execute(publish=publishing)
        REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        problems=[x for x in result["channels"] if x["status"] in
          ("MANUAL_REVIEW_REQUIRED","INVALID_EXISTING_RECEIPTS","NOT_AUTHORIZED","NO_POSTER","INVALID_POSTER","NOT_INDEXED")]
        print("CINEX_SHOWCASE_SUMMARY",json.dumps({"mode":result["mode"],"count":len(result["channels"]),
             "problems":len(problems),"download_ready":result["download_ready_count"]}))
        sys.exit(1 if problems else 0)
    except Exception as exc:
        REPORT.write_text(json.dumps({"mode":"preflight_failed","status":"BLOCKED",
          "error":str(exc)[:250]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("CINEX_SHOWCASE_BLOCKED",type(exc).__name__,str(exc)[:180],file=sys.stderr)
        sys.exit(1)
