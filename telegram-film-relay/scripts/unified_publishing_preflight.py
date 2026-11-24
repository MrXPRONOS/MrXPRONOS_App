"""Read-only preflight for unified CinéX poster/video publishing.

Checks each known configured public/private pair, the matching publishing bot,
the existing rescue invitation, and the shared folder. NO Telegram send/edit/delete.
"""
from __future__ import annotations

import asyncio
import logging
import os

from film_relay.bot_http import BotHTTPClient
from film_relay.publication import film_folder_url
from film_relay.rescue_channels import rescue_link_for
from film_relay.runner import resolve_peer
from film_relay.ten_video_rotation import category_targets
from film_relay.public_video_retention import validate_retention_targets
from film_relay.unified_download import configured_private_id
from film_relay.radar_download_registry import RadarRegistry

LOG = logging.getLogger("cinex.unified_preflight")


def token_for(category: str):
    common = (os.getenv("FOOTBALL_NEWS_BOT_TOKEN")
              or os.getenv("TELEGRAM_BOT_TOKEN") or "")
    if category == "desir":
        return os.getenv("DESIR_BOT_TOKEN") or common
    if category == "comedie":
        return os.getenv("COMEDIE_BOT_TOKEN") or common
    if category == "anime":
        if os.getenv("CINEX_ANIME_LEGACY_RELAY_DISABLED") == "true":
            # A legacy Désir bot is not proof that dedicated Anime V2 is ready.
            return os.getenv("CINEX_ANIME_SOURCE_BOT_TOKEN") or ""
        # Hybrid Anime reads with the existing user session and publishes
        # with the same principal bot as Films and Series. No new polling.
        return common
    if category == "action":
        return os.getenv("ACTION_BOT_TOKEN") or common
    return common


def verify_cineradar_registry(env=None) -> int:
    """Read-only proof of the owner-approved stock and enabled D1 delivery gate.

    Does not send, copy, delete or register any Telegram media.
    """
    env = os.environ if env is None else env
    approved_id = configured_private_id(env)
    if approved_id is None:
        raise RuntimeError("CineRadar : canal privé central non approuvé")
    registry = RadarRegistry(env=env)
    stock = registry._query(
        "SELECT stock_chat_id,radar_bot_id FROM cine_private_stock_config "
        "WHERE singleton=1 AND ready=1 LIMIT 1"
    ).get("results") or []
    if (len(stock) != 1 or str(stock[0].get("stock_chat_id")) != str(approved_id)
            or int(stock[0].get("radar_bot_id") or 0) <= 0):
        raise RuntimeError("CineRadar : stock central ou bot D1 non confirmé")
    gate = registry._query(
        "SELECT value FROM bot_settings "
        "WHERE setting_key='cine_delivery_enabled' LIMIT 1"
    ).get("results") or []
    if len(gate) != 1 or str(gate[0].get("value")) != "1":
        raise RuntimeError("CineRadar : livraison des téléchargements désactivée")
    return approved_id


async def run():
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession

    ids = (os.getenv("TG_API_ID"), os.getenv("TG_API_HASH"),
           os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
           or os.getenv("TG_STREAM_SESSION"))
    if not all(ids):
        raise RuntimeError("Session Telegram manquante")
    film_folder_url()
    selected = category_targets()
    validate_retention_targets(selected)
    verified_stock_id = verify_cineradar_registry()
    LOG.info("CineRadar D1 : stock central approuvé et livraison activée")
    client = TelegramClient(StringSession(ids[2]), int(ids[0]), ids[1],
                            request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    failed = 0
    checked = 0
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session Telegram non autorisée")
        for category, public_handle, private_id in selected:
            try:
                public = await resolve_peer(client, public_handle)
                private = await resolve_peer(client, str(private_id))
                if utils.get_peer_id(public) == utils.get_peer_id(private):
                    raise RuntimeError("Destination publique = vidéothèque")
                if utils.get_peer_id(private) != private_id:
                    raise RuntimeError("Identité de vidéothèque non conforme")
                if int(private_id) == int(verified_stock_id):
                    raise RuntimeError("La vidéothèque de catégorie ne peut être le stock central")
                if (str(getattr(public, "username", "") or "").casefold()
                        != public_handle[1:].casefold()):
                    raise RuntimeError("Identité du canal principal non conforme")
                bot_token = token_for(category)
                if not bot_token:
                    raise RuntimeError("Secret bot non configuré")
                bot = BotHTTPClient(bot_token, client)
                identity = await bot.get_me()
                for label, peer in (("principal", public), ("videotheque", private)):
                    permission = await bot.get_permissions(peer, identity)
                    if not (getattr(permission, "is_creator", False) or
                            (getattr(permission, "is_admin", False) and
                             getattr(permission, "post_messages", False))):
                        raise RuntimeError(f"Bot non autorisé à publier dans {label}")
                if not rescue_link_for(public):
                    raise RuntimeError("Invitation Secours non vérifiée")
                checked += 1
                LOG.info("%s : OK, destinations et bot autorisés, secours/dossier vérifiés",
                         category)
            except Exception as exc:
                failed += 1
                # Never print tokens or invitation values.
                LOG.error("%s : BLOQUÉ : %s", category, str(exc).splitlines()[0][:170])
        LOG.info("BILAN PREVOL : catégories configurées=%d, prêtes=%d, bloquées=%d",
                 len(selected), checked, failed)
    finally:
        await client.disconnect()
    if failed or checked != 6:
        raise RuntimeError("Prévol Lot 2 incomplet : catégories, bots ou Secours à corriger")
    return checked


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())
