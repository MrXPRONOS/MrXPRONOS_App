#!/usr/bin/env python3
"""Fast & Furious: bot-only audit / optional single-poster publication.

A public saga can be resolved by @username via Bot API; this DOES NOT read
its old history. The pinned photo (if accessible) and owner-forwarded movies
are the only source data. No TG_SESSION_STRING, Telethon, or user login.
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

from audit_series_bots import BotAPI, is_admin, identify_radar_bot
from publish_individual_series_bot import d1,request_bot,INVITE,TOKEN

HANDLE="fastandfuriousvffr"
SOURCE="@"+HANDLE
PUBLIC="@CineXFilms_vf"
SLUG="fast-and-furious"
REPORT=Path("cinex-fast-furious-publish-report.json")


def poster_keyboard(token:str,rescue:str):
    if not TOKEN.fullmatch(token) or not INVITE.fullmatch(rescue):
        raise RuntimeError("Saga: bouton invalide")
    return {"inline_keyboard":[
        [{"text":"📥 Télécharger les films disponibles",
          "url":"https://t.me/CineRadarFr_Bot?start=ffs_"+token,"style":"success"}],
        [{"text":"🛟 Canal de secours","url":rescue,"style":"danger"}],
        [{"text":"🎬 Canal Fast and Furious VF","url":"https://t.me/"+HANDLE,"style":"primary"}],
    ]}


def candidates():
    return [
        ("FOOTBALL_NEWS_BOT_TOKEN",os.getenv("CINEX_PUBLISH_BOT_TOKEN","")),
        ("TELEGRAM_BOT_TOKEN",os.getenv("ALT_TELEGRAM_BOT_TOKEN","")),
        ("DESIR_BOT_TOKEN",os.getenv("ALT_DESIR_BOT_TOKEN","")),
        ("ACTION_BOT_TOKEN",os.getenv("ALT_ACTION_BOT_TOKEN","")),
        ("ANIME_BOT_TOKEN",os.getenv("ALT_ANIME_BOT_TOKEN","")),
        ("CINEX_RADAR_BOT_TOKEN",os.getenv("CINEX_RADAR_BOT_TOKEN","")),
    ]


def check_write(bot:BotAPI,chat_id,identity:int):
    chat=bot.call("getChat",{"chat_id":chat_id})
    if chat.get("type")!="channel":raise RuntimeError("Destination non reconnue comme canal")
    member=bot.call("getChatMember",{"chat_id":chat["id"],"user_id":identity})
    if not is_admin(member) or (member.get("status")=="administrator" and not member.get("can_post_messages",False)):
        raise RuntimeError("Le bot n'a pas le droit de publier")
    return chat


def verified_rescue():
    rows=d1("SELECT rescue_chat_id,invite_url FROM cine_classic_rescue_config WHERE LOWER(public_handle)=?",["@cinexfilms_vf"])
    if len(rows)!=1 or not re.fullmatch(r"-100[0-9]{6,}",str(rows[0]["rescue_chat_id"])):
        raise RuntimeError("Canal de secours Films non configuré")
    invite=str(rows[0]["invite_url"])
    if not INVITE.fullmatch(invite):raise RuntimeError("Lien du secours Films invalide")
    return str(rows[0]["rescue_chat_id"]),invite


def resolve_source(bots):
    for label,bot,me in bots:
        try:
            chat=bot.call("getChat",{"chat_id":SOURCE})
            if chat.get("type")=="channel" and str(chat.get("username") or "").lower()==HANDLE:
                return chat
        except RuntimeError:
            continue
    return None


def audit_and_publish(*,publish:bool=False):
    rows=d1("SELECT slug,source_chat_id,poster_source_message_id,public_post_id,rescue_post_id,rights_attested,status,token FROM cine_franchise_catalog WHERE slug=?",[SLUG])
    if len(rows)!=1:raise RuntimeError("Catalogue Fast & Furious non installé")
    catalog=rows[0]
    rescue_id,rescue_invite=verified_rescue()
    bots=[]
    seen=set()
    for name,secret in candidates():
        if not secret or secret in seen:continue
        seen.add(secret)
        try:
            bot=BotAPI(secret)
            me=bot.call("getMe",{})
            bots.append((name,bot,me))
        except (RuntimeError,ValueError):
            continue
    if not bots:raise RuntimeError("Aucun bot GitHub connecté")
    source=resolve_source(bots)
    source_id=str(source["id"]) if source else None
    if source and source_id.startswith("-100"):
        if catalog["source_chat_id"] not in (None,source_id):
            raise RuntimeError("ID du canal public modifié : contrôle manuel requis")
        d1("UPDATE cine_franchise_catalog SET source_chat_id=?,updated_at=CURRENT_TIMESTAMP WHERE slug=? AND (source_chat_id IS NULL OR source_chat_id=?)",
           [source_id,SLUG,source_id])
        if catalog["poster_source_message_id"] is None:
            pin=source.get("pinned_message") or {}
            if pin.get("photo") and int(pin.get("message_id") or 0)>0:
                d1("UPDATE cine_franchise_catalog SET poster_source_message_id=?,poster_caption=?,updated_at=CURRENT_TIMESTAMP WHERE slug=? AND poster_source_message_id IS NULL",
                   [int(pin["message_id"]),str(pin.get("caption") or "")[:1500],SLUG])
                catalog["poster_source_message_id"]=int(pin["message_id"])
    elif catalog["source_chat_id"]:
        source_id=str(catalog["source_chat_id"])
    count=d1("SELECT COUNT(*) AS n FROM cine_franchise_films WHERE slug=?",[SLUG])[0]["n"]
    owner=d1("SELECT COUNT(*) AS n FROM cine_owner_vault v JOIN cine_franchise_films f ON f.source_chat_id=v.source_chat_id AND f.source_message_id=v.source_message_id WHERE f.slug=? AND v.status='stored'",[SLUG])[0]["n"]
    publisher=None
    diagnostics=[]
    try:
        identity=identify_radar_bot(os.getenv("CINEX_RADAR_BOT_TOKEN",""))
    except RuntimeError:
        identity=None
    radar_admin=None
    for name,bot,me in bots:
        main_ok=backup_ok=source_ok=False
        try:check_write(bot,PUBLIC,int(me["id"]));main_ok=True
        except RuntimeError:pass
        try:check_write(bot,rescue_id,int(me["id"]));backup_ok=True
        except RuntimeError:pass
        if source_id:
            try:
                detail=bot.call("getChat",{"chat_id":source_id})
                membership=bot.call("getChatMember",{"chat_id":detail["id"],"user_id":me["id"]})
                source_ok=is_admin(membership)
                if identity is not None and radar_admin is None:
                    radar=bot.call("getChatMember",{"chat_id":detail["id"],"user_id":identity})
                    radar_admin=is_admin(radar)
            except RuntimeError:pass
        diagnostics.append({"bot":str(me.get("username") or name),"main":main_ok,"backup":backup_ok,"source":source_ok})
        if main_ok and backup_ok and source_ok and publisher is None:
            publisher=(name,bot,me)
    state={
        "slug":SLUG,"source_url":"https://t.me/"+HANDLE,"source_found":bool(source_id),
        "source_id":source_id,"main":"https://t.me/CineXFilms_vf",
        "pin_indexed":bool(catalog.get("poster_source_message_id")),
        "indexed_films":int(count),"owner_copies":int(owner),
        "radar_admin":radar_admin,"publisher_ready":publisher is not None,
        "publisher_checks":diagnostics,
        "status":catalog["status"],"mode":"publish" if publish else "audit",
    }
    if not publish:
        print("CINEX_FF_AUDIT",json.dumps({k:v for k,v in state.items() if k!="publisher_checks"},ensure_ascii=False))
        for check in diagnostics:print("CINEX_FF_BOT",json.dumps(check,ensure_ascii=False))
        return state
    if not publisher:raise RuntimeError("Publication bloquée : bot non administrateur dans Films + Secours + Fast & Furious")
    if int(catalog["rights_attested"] or 0)!=1 or not source_id or not catalog.get("poster_source_message_id") or not count:
        raise RuntimeError("Publication bloquée : source, affiche ou films transférés manquants")
    _,pub,me=publisher
    if catalog["status"] not in ("draft","published"):
        raise RuntimeError("Publication en révision manuelle; ne pas créer de doublons")
    token=catalog["token"]
    markup=poster_keyboard(token,rescue_invite)
    if catalog["status"]=="published":
        if not catalog.get("public_post_id") or not catalog.get("rescue_post_id"):
            raise RuntimeError("Reçus de publication manquants")
        for chat_id,msg_id in ((PUBLIC,catalog["public_post_id"]),(rescue_id,catalog["rescue_post_id"])):
            request_bot(pub._token,"editMessageReplyMarkup",{"chat_id":chat_id,"message_id":int(msg_id),"reply_markup":markup})
        state["publication"]="updated_existing"
        return state
    # Mark an irreversible request before copyMessage; any ambiguous response
    # leaves a needs_review state and cannot silently duplicate public posters.
    d1("UPDATE cine_franchise_catalog SET status='needs_review' WHERE slug=? AND status='draft'",[SLUG])
    public=request_bot(pub._token,"copyMessage",{
        "chat_id":PUBLIC,"from_chat_id":source_id,"message_id":int(catalog["poster_source_message_id"]),
        "reply_markup":markup,"disable_notification":True,
    })
    if not int(public.get("message_id") or 0)>0:raise RuntimeError("Affiche principale: reçu Telegram absent")
    d1("UPDATE cine_franchise_catalog SET public_post_id=? WHERE slug=? AND status='needs_review'",
       [int(public["message_id"]),SLUG])
    backup=request_bot(pub._token,"copyMessage",{
        "chat_id":rescue_id,"from_chat_id":source_id,"message_id":int(catalog["poster_source_message_id"]),
        "reply_markup":markup,"disable_notification":True,
    })
    if not int(backup.get("message_id") or 0)>0:raise RuntimeError("Affiche secours: reçu Telegram absent")
    d1("UPDATE cine_franchise_catalog SET rescue_post_id=?,status='published',updated_at=CURRENT_TIMESTAMP WHERE slug=? AND status='needs_review'",
       [int(backup["message_id"]),SLUG])
    state["publication"]="published_both"
    state["public_post_id"]=int(public["message_id"])
    state["rescue_post_id"]=int(backup["message_id"])
    return state


if __name__=="__main__":
    result=None
    try:
        result=audit_and_publish(publish=os.getenv("CINEX_FF_PUBLISH","false").lower()=="true")
        REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    except Exception as error:
        REPORT.write_text(json.dumps({"status":"blocked","reason":str(error)[:220]},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("CINEX_FF_BLOCKED",str(error)[:220],file=sys.stderr)
        sys.exit(1)
