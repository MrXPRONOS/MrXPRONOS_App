"""Réparation ciblée et idempotente de No Longer Rangers S02 (6 épisodes).

Ne publie aucun nouveau film, épisode ou publicité.
Modifie uniquement les légendes/index existants, après contrôle des IDs
et des marqueurs émis par CinéX. Ne supprime aucun transfert Torrent9.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
import re
from html import escape

from telethon import TelegramClient, utils
from telethon.errors import FloodWaitError, MessageNotModifiedError
from telethon.sessions import StringSession

from film_relay.anime_catalog import (
    CATALOG, main_index_text, public_buttons, read_catalog,
    save_catalog, season_text,
)
from film_relay.bot_http import BotHTTPClient, TelegramBotHTTPError
from film_relay.category_runner import category_config
from film_relay.runner import resolve_peer
from film_relay.text import private_message_link

LEGACY_KEY = "mangas-fv-no-longer-rangers-s02-mp4"
FIXED_NAME = "No Longer Rangers"
EXPECTED_PUBLIC_ID = 17
EXPECTED_PRIVATE_INDEX = 11
EXPECTED_SEASON_INDEX = 12
EXPECTED_EPISODES = {str(i): 12+i for i in range(1,7)}
EXPECTED_SOURCE_PREFIX = "-1001595907308:"
MIRROR_ID = 2428

async def edit_text(client, channel, message_id, content):
    current = await client.get_messages(channel, ids=int(message_id))
    if not current:
        raise RuntimeError("Message privé introuvable : " + str(message_id))
    if (current.raw_text or "").strip() == re.sub(r"<[^>]+>", "", content).strip():
        return
    try:
        await client.edit_message(channel, int(message_id), content,
                                  parse_mode="html", link_preview=False)
    except MessageNotModifiedError:
        pass

async def run(dry_run: bool):
    data = read_catalog()
    entry = data.get("series", {}).get(LEGACY_KEY)
    if not entry:
        raise RuntimeError("Fiche historique No Longer Rangers introuvable : aucune modification.")
    episodes = entry.get("episodes", {})
    if "2" in episodes and "1" not in episodes:
        print("CORRECTION_DEJA_ENREGISTREE")
        return
    if (set(episodes) != {"1"} or
        {k:int(v["message_id"]) for k,v in episodes["1"].items()} != EXPECTED_EPISODES or
        entry.get("public_id") != EXPECTED_PUBLIC_ID or
        entry.get("main_index_id") != EXPECTED_PRIVATE_INDEX or
        entry.get("season_indices", {}) != {"1":EXPECTED_SEASON_INDEX} or
        len(entry.get("source_items", {})) != 6 or
        not all(k.startswith(EXPECTED_SOURCE_PREFIX) for k in entry["source_items"])):
        raise RuntimeError("Les reçus diffèrent du cas S02 étudié : arrêt sans modification.")
    if "S02" not in entry.get("title",""):
        raise RuntimeError("Absence du marqueur S02 dans le titre d'origine.")

    cfg=category_config("anime")
    api_id=os.getenv("TG_API_ID")
    api_hash=os.getenv("TG_API_HASH")
    session=(os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or
             os.getenv("TG_STREAM_SESSION"))
    token=os.getenv("CINEX_CATEGORY_BOT_TOKEN")
    if not all((api_id,api_hash,session,token)):
        raise RuntimeError("Secrets Telegram indispensables manquants.")

    client=TelegramClient(StringSession(session),int(api_id),api_hash,
                          request_retries=0,connection_retries=2,
                          flood_sleep_threshold=0,receive_updates=False)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session utilisateur non autorisée.")
        private=await resolve_peer(client,cfg["private"])
        public=await resolve_peer(client,cfg["public"])
        mirror=await resolve_peer(client,cfg["mirror"])
        private_id=utils.get_peer_id(private)
        bot=BotHTTPClient(token,client)
        bot_identity=await bot.get_me()
        rights=await bot.get_permissions(public,bot_identity)
        if not (rights.is_creator or (rights.is_admin and rights.post_messages)):
            raise RuntimeError("Le bot ne peut pas corriger la fiche publique.")

        marker="#CXANIME_"+hashlib.sha256(LEGACY_KEY.encode()).hexdigest()[:15]
        pub=await client.get_messages(public,ids=EXPECTED_PUBLIC_ID)
        idx=await client.get_messages(private,ids=EXPECTED_PRIVATE_INDEX)
        seasonidx=await client.get_messages(private,ids=EXPECTED_SEASON_INDEX)
        if not (pub and pub.photo and marker in (pub.raw_text or "")):
            raise RuntimeError("La fiche publique n°17 n'est pas celle du catalogue.")
        if not (idx and marker in (idx.raw_text or "")):
            raise RuntimeError("L'index principal n°11 ne correspond pas au catalogue.")
        if not (seasonidx and marker+"_S1" in (seasonidx.raw_text or "")):
            raise RuntimeError("L'index saison n°12 ne correspond pas à S1.")
        videos={}
        for ep,id_value in EXPECTED_EPISODES.items():
            obj=await client.get_messages(private,ids=id_value)
            if not obj or not obj.document or "#CXEP_" not in (obj.raw_text or ""):
                raise RuntimeError(f"Épisode {ep} : document ou marqueur manquant.")
            ep_mark=re.search(r"#CXEP_[0-9a-f]{18}",obj.raw_text or "")
            if not ep_mark:
                raise RuntimeError("Marqueur d'épisode illisible.")
            videos[ep]=(obj,ep_mark.group(0))
        mirror_msg=await client.get_messages(mirror,ids=MIRROR_ID)
        mirror_check=bool(mirror_msg and getattr(mirror_msg,"fwd_from",None))
        print("REPARATION_CIBLE",LEGACY_KEY,"saison actuelle 1 -> saison 2")
        print("VIDEOS_VERIFIEES",sorted(EXPECTED_EPISODES.values()))
        print("INDEX_PRIVATE",EXPECTED_PRIVATE_INDEX,EXPECTED_SEASON_INDEX,
              "CARTE_PUBLIQUE",EXPECTED_PUBLIC_ID,
              "MIRROR_PRESENT",mirror_check)
        if dry_run:
            print("MODE_SIMULATION : aucune modification Telegram ni GitHub.")
            return

        # Éditer d'abord les vidéos, sans les retransférer ni changer leurs IDs.
        for ep,(msg,ep_mark) in sorted(videos.items(),key=lambda x:int(x[0])):
            new_caption=(f"🌸 <b>{escape(FIXED_NAME)}</b> — "
                         f"S02E{int(ep):02d}\n{ep_mark}")
            await edit_text(client,private,msg.id,new_caption)
            await asyncio.sleep(7)

        new_episodes=dict(episodes["1"])
        idx_text=season_text(FIXED_NAME,2,new_episodes)+"\n"+marker+"_S2"
        await edit_text(client,private,EXPECTED_SEASON_INDEX,idx_text)
        await asyncio.sleep(7)
        seasons={"2":EXPECTED_SEASON_INDEX}
        main_text=main_index_text(FIXED_NAME,private_id,seasons)+"\n"+marker
        await edit_text(client,private,EXPECTED_PRIVATE_INDEX,main_text)
        await asyncio.sleep(7)

        # La publication est du bot : modifier simultanément titre ET boutons.
        preview={
            **entry,"title":FIXED_NAME,
            "season_indices":seasons,
            "episodes":{"2":new_episodes},
        }
        button_rows=public_buttons(private_id,preview)
        new_cap=(f"🌸 <b>{escape(FIXED_NAME)}</b>\n"
                 f"📺 <b>Saison 2 — 6 épisodes</b>\n\n"
                 "<i>Saisons et épisodes dans la bibliothèque CinéX.</i>\n"
                 f'📚 <a href="{private_message_link(private_id,EXPECTED_PRIVATE_INDEX)}">'
                 "VOIR TOUS LES ÉPISODES</a>\n"+marker)
        await bot._call("editMessageCaption",{
            "chat_id":str(utils.get_peer_id(public)),
            "message_id":str(EXPECTED_PUBLIC_ID),
            "caption":new_cap,
            "parse_mode":"HTML",
            "reply_markup":json.dumps(bot._keyboard(button_rows),
                                      ensure_ascii=False),
        })
        entry["title"]=FIXED_NAME
        entry["episodes"]={"2":new_episodes}
        entry["season_indices"]=seasons
        data["series"][LEGACY_KEY]=entry
        save_catalog(data)
        print("CORRECTION_TELEGRAM_ET_HISTORIQUE_REUSSIE")
        # Le transfert natif est une copie ancienne. Ne pas le supprimer
        # ni le dupliquer sans autorisation de l'utilisateur.
        if mirror_check:
            print("ATTENTION_MIROIR_2428 : boutons transférés anciens possibles ;")
            print("aucun transfert supplémentaire ni suppression effectuée.")
    except FloodWaitError as err:
        raise RuntimeError(f"Telegram impose {err.seconds}s d'attente : arrêt.") from err
    finally:
        await client.disconnect()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    opt=parser.parse_args()
    asyncio.run(run(not opt.apply))

if __name__=="__main__":
    main()
