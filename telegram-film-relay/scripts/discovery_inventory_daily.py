#!/usr/bin/env python3
"""CinéX quotidien : une session Telegram personnelle pour deux tâches.

1. Vérifier les canaux où le compte ET @mrxpronos_canal_bot sont admins,
   conserver les canaux privés chiffrés dans Supabase Vault.
2. Chercher les canaux cinéma publics, envoyer le digest en Messages enregistrés.

Seule une liste d'identifiants PUBLICS vérifiés est exportée vers RUNNER_TEMP
pour le processus de promotion Bot API, qui n'ouvre pas de session personnelle.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PeerFloodError
from telethon.sessions import StringSession

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from inventory_mrxpronos_shared_admin_channels import scan as inventory_scan  # noqa: E402
from discovery_daily import run as daily_discovery  # noqa: E402

LOG = logging.getLogger("telegram_daily_coordinator")


async def run() -> int:
    api_id = (os.getenv("TG_API_ID") or "").strip()
    api_hash = (os.getenv("TG_API_HASH") or "").strip()
    session = (
        os.getenv("TG_SESSION_STRING")
        or os.getenv("TG_STRING_SESSION")
        or os.getenv("TG_STREAM_SESSION")
        or ""
    ).strip()
    if not api_id.isdecimal() or not api_hash or not session:
        LOG.error("Configuration Telegram personnelle indisponible.")
        return 1

    public_output = os.getenv("CINERADAR_PUBLIC_INVENTORY_FILE", "").strip()
    if not public_output:
        LOG.error("Le chemin temporaire de l'inventaire PUBLIC est obligatoire.")
        return 1

    client = TelegramClient(
        StringSession(session), int(api_id), api_hash,
        request_retries=0, connection_retries=2,
        flood_sleep_threshold=0, receive_updates=False,
    )
    try:
        await client.connect()
        if not await client.is_user_authorized():
            LOG.error("La session Telegram personnelle n'est plus autorisée.")
            return 1

        LOG.info("Étape 1/2 : actualisation de l'inventaire admin et du coffre chiffré.")
        code = await inventory_scan(client=client, public_export_path=public_output)
        if code != 0:
            return code or 1

        LOG.info("Étape 2/2 : recherche publique quotidienne avec la MÊME session.")
        code = await daily_discovery(client=client)
        if code != 0:
            return code or 1
        LOG.info("Inventaire sécurisé et découverte achevés via une seule connexion MTProto.")
        return 0
    except (FloodWaitError, PeerFloodError):
        LOG.error("Limitation Telegram : arrêt immédiat, aucune nouvelle tentative.")
        return 2
    except Exception as exc:
        # Never log arbitrary error messages; Telegram/HTTP errors may contain secrets or private IDs.
        LOG.error("Coordination interrompue (%s), sans nouvelle connexion.", type(exc).__name__)
        return 1
    finally:
        await client.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level="INFO", format="%(asctime)s | %(levelname)s | %(message)s")
    raise SystemExit(asyncio.run(run()))
