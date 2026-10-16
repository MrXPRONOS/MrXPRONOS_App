"""Publish 3 rotating cross-channel Telegram promo posters with real link buttons."""
from __future__ import annotations
import asyncio
import logging
import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from film_relay.runner import config_from, resolve_peer
from film_relay.promotions import publish_promotions
from film_relay.state import State


async def execute():
    cfg=config_from(os.getenv("CHANNELS_CONFIG","config/channels.json"))
    token=(os.getenv("CINEX_BOT_TOKEN") or "").strip()
    api_id=os.getenv("TG_API_ID")
    api_hash=os.getenv("TG_API_HASH")
    session=os.getenv("TG_SESSION_STRING") or os.getenv("TG_STRING_SESSION") or os.getenv("TG_STREAM_SESSION")
    if not all((token,api_id,api_hash,session)):
        raise RuntimeError("Jeton bot football ou identifiants Telegram manquants.")
    state=State(os.getenv("STATE_PATH","state/state.json"))
    user=TelegramClient(StringSession(session),int(api_id),api_hash,
                        request_retries=1,connection_retries=1,flood_sleep_threshold=0)
    bot=TelegramClient(StringSession(),int(api_id),api_hash,
                       request_retries=1,connection_retries=1,flood_sleep_threshold=0)
    await user.connect()
    try:
        if not await user.is_user_authorized():
            raise RuntimeError("Session TG_SESSION_STRING non autorisée.")
        await bot.start(bot_token=token)
        private=await resolve_peer(user,cfg["private_channel"])
        primary=await resolve_peer(user,cfg["public_channel"])
        mirror=None
        try:
            if cfg.get("mirror_channel"):
                mirror=await resolve_peer(user,cfg["mirror_channel"])
        except Exception as exc:
            logging.warning("Canal secondaire inaccessible : %s",type(exc).__name__)
        results=await publish_promotions(user,bot,private,primary,mirror,state,
                                         force=os.getenv("PROMO_FORCE_ONCE","false").lower()=="true")
        print("PUBLICITÉS CINÉX : "
              f"privé={results['private']} public={results['public']} "
              f"secondaire={results['mirror']} non_autorisés/différés={results['skipped']}")
        if results["skipped"]:
            print("Vérifier les droits administrateur du bot football dans les canaux concernés.")
        return 0 if any(results[k] for k in ("private","public","mirror")) or not results["skipped"] else 2
    finally:
        await bot.disconnect()
        await user.disconnect()


if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s")
    raise SystemExit(asyncio.run(execute()))
