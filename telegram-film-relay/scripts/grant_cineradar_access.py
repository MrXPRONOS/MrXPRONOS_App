"""One-time, owner-approved, least-privilege Cine Radar bot library access.

Only @CineRadarFr_Bot is promoted, only to the two private channel IDs taken
from existing owner GitHub variables. The workflow never posts, copies, edits,
downloads or deletes a Telegram file. No other bot/user is added.
"""
from __future__ import annotations
import argparse
import asyncio
import logging
import os
from film_relay.runner import resolve_peer
from scripts.catalog_stage12 import configured_targets

LOG=logging.getLogger("cinex.radar_bot_access")
BOT_USERNAME="CineRadarFr_Bot"


def needs_update(permission) -> bool:
    return not (getattr(permission,"is_creator",False)
                or getattr(permission,"is_admin",False))


async def configure(*,apply:bool):
    from telethon import TelegramClient,functions,types,utils
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError,PeerFloodError
    targets=configured_targets(os.environ)
    if not all(t["rights_attested"] for t in targets):
        raise RuntimeError("Droits non confirmés pour les deux vidéothèques")
    api_id=os.getenv("TG_API_ID","")
    api_hash=os.getenv("TG_API_HASH","")
    session=os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or os.getenv("TG_STREAM_SESSION")
    if not api_id.isdigit() or not api_hash or not session:
        raise RuntimeError("Secrets utilisateur Telegram absents")
    client=TelegramClient(StringSession(session),int(api_id),api_hash,
                          flood_sleep_threshold=0,request_retries=1,connection_retries=2,
                          receive_updates=False)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram expirée")
        me=await client.get_me()
        bot=await client.get_entity("@"+BOT_USERNAME)
        if not getattr(bot,"bot",False) or str(getattr(bot,"username","")).casefold()!=BOT_USERNAME.casefold():
            raise RuntimeError("Identité Ciné Radar bot non confirmée")
        result={}
        for target in targets:
            category=target["category"]
            channel=await resolve_peer(client,target["private_chat_id"])
            if (utils.get_peer_id(channel)!=int(target["private_chat_id"])
                    or not getattr(channel,"broadcast",False)
                    or getattr(channel,"username",None)
                    or getattr(channel,"noforwards",False)):
                raise RuntimeError(category+": vidéothèque privée introuvable ou protégée")
            own=await client.get_permissions(channel,me)
            if not getattr(own,"is_creator",False):
                # No silent privilege changes in someone else's channel.
                raise RuntimeError(category+": la session n'est pas propriétaire du canal")
            try:
                perm=await client.get_permissions(channel,bot)
            except Exception:
                perm=None
            if perm is not None and not needs_update(perm):
                result[category]="already_admin"
                continue
            if not apply:
                result[category]="needs_admin"
                continue
            # Channel bots can be added only as admins. Grant ability to post,
            # but no delete, edit, invitations or promoting other administrators.
            rights=types.ChatAdminRights(post_messages=True)
            await client(functions.channels.EditAdminRequest(channel=channel,user_id=bot,
                   admin_rights=rights,rank="Ciné Radar"))
            check=await client.get_permissions(channel,bot)
            if needs_update(check):
                raise RuntimeError(category+": administration non confirmée par Telegram")
            result[category]="added"
            await asyncio.sleep(8)
        print("CINERADAR_LIBRARY_BOT_ACCESS:",result)
        return result
    except (FloodWaitError,PeerFloodError):
        LOG.error("Limitation Telegram : aucune relance immédiate")
        raise
    finally:
        await client.disconnect()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    asyncio.run(configure(apply=args.apply))

if __name__=="__main__":
    main()
