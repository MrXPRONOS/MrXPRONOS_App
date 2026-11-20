"""CinéX Anime: verify & repair ONLY existing historical Telegram indexes/cards.

No upload, new message, deletion, channel discovery, or other category run.
GitHub Actions owns the single Telegram account session and persists its
local state via the safe merge helper before reporting partial failures.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os

from telethon import TelegramClient, utils
from telethon.sessions import StringSession

from film_relay.anime_catalog import (
    read_catalog, repair_legacy_indexes, save_catalog,
)
from film_relay.bot_http import BotHTTPClient
from film_relay.category_runner import category_config, check_bot_permission
from film_relay.runner import resolve_peer

LOG = logging.getLogger("cinex.anime.repair")
# A one-off reconciliation must never modify an unrelated catalogue entry.
ALLOWED_KEY_PREFIXES = ("mangas-fv-death-parade-", "mangas-fv-tomb-raider-king-")


def pending_keys(catalogue):
    return sorted(
        k for k, row in (catalogue.get("series") or {}).items()
        if row.get("index_repair_pending")
    )


async def run(*, apply=False):
    catalogue = read_catalog()
    pending = pending_keys(catalogue)
    if not pending:
        LOG.info("Anime : aucun index historique à réparer.")
        return 0
    if any(not k.startswith(ALLOWED_KEY_PREFIXES) for k in pending):
        raise RuntimeError("Réparation limitée aux anciens animés identifiés ; aucune modification.")
    if catalogue.get("active_batch"):
        LOG.warning("Lot Anime actif : réparation interrompue pour éviter toute concurrence.")
        return 3
    cfg = category_config("anime")
    api_id = (os.getenv("TG_API_ID") or "").strip()
    api_hash = (os.getenv("TG_API_HASH") or "").strip()
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
               or os.getenv("TG_SESSION_STRING") or "").strip()
    token = (os.getenv("CINEX_CATEGORY_BOT_TOKEN") or "").strip()
    if not (api_id and api_hash and session and token):
        raise RuntimeError("Secrets Telegram absents : aucune opération lancée.")
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            request_retries=0, connection_retries=2,
                            flood_sleep_threshold=0, receive_updates=False)
    bot = BotHTTPClient(token, client)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Session utilisateur Telegram expirée.")
        private = await resolve_peer(client, cfg["private"])
        public = await resolve_peer(client, cfg["public"])
        pid, oid = utils.get_peer_id(private), utils.get_peer_id(public)
        if pid != int(cfg["private"]) or pid == oid:
            raise RuntimeError("Canal privé mal résolu ; annulation.")
        if not (getattr(private, "broadcast", False)
                and getattr(public, "broadcast", False)):
            raise RuntimeError("Destinations non conformes : canaux broadcast requis.")
        if str(getattr(public, "username", "") or "").casefold() != (
                str(cfg["public"]).lstrip("@").casefold()):
            raise RuntimeError("Identifiant du canal public incohérent.")
        bot_public = await bot.get_entity(cfg["public"])
        if utils.get_peer_id(bot_public) != oid:
            raise RuntimeError("Bot et utilisateur : canaux publics différents.")
        me = await bot.get_me()
        perms = await bot.get_permissions(bot_public, me)
        check_bot_permission(perms, cfg["public"])
        LOG.info("Préflight : canaux Telegram et bot vérifiés ; fiches en attente=%d", len(pending))
        if not apply:
            LOG.info("Mode lecture seule : aucun message Telegram modifié.")
            return 0
        fixed = await repair_legacy_indexes(
            client, bot, private, public, bot_public, pid,
            catalogue, max(12.0, float(os.getenv("CINEX_PAUSE_SECONDS", "12"))))
        save_catalog(catalogue)
        remaining = pending_keys(catalogue)
        LOG.info("Bilan réparation Anime : corrigées=%d ; restantes=%d ; "
                 "anciens messages conservés", fixed, len(remaining))
        return 3 if remaining else 0
    finally:
        await bot.disconnect()
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Réparer les index Anime sans republier")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
