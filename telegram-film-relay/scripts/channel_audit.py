"""Read-only CineX channel and Telegram-number verification for GitHub Actions.

Reads Telegram metadata and permissions; NEVER publishes or forwards messages.
The JSON report deliberately excludes private IDs, secrets and invitation links.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from film_relay.bot_http import BotHTTPClient
from film_relay.category_runner import category_config, preflight
from film_relay.runner import config_from
from film_relay.series_catalog import series_config

LOG = logging.getLogger("cinex_channel_audit")


def requested_channels():
    entries = []
    classic = config_from(os.getenv("CHANNELS_CONFIG", "config/channels.json"))
    entries.append(("films", {
        "category": "films",
        "sources": [s["channel"] for s in classic["sources"]
                    if s.get("redistribution_authorized") is True],
        "private": classic["private_channel"],
        "public": classic["public_channel"],
    }, os.getenv("CINEX_FILM_BOT_TOKEN") or os.getenv("CINEX_BOT_TOKEN", "")))
    entries.append(("series", series_config(),
                    os.getenv("CINEX_SERIES_BOT_TOKEN") or os.getenv("CINEX_BOT_TOKEN", "")))
    for name in ("comedie", "anime"):
        entries.append((name, category_config(name),
                        os.getenv("CINEX_CATEGORY_BOT_TOKEN", "")))
    return entries


async def verify():
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or
               os.getenv("TG_STREAM_SESSION") or "").strip()
    aid = os.getenv("TG_API_ID", "").strip()
    ahash = os.getenv("TG_API_HASH", "").strip()
    if not (aid.isdigit() and ahash and session):
        raise RuntimeError("Session ou identifiants d'API Telegram manquants.")
    client = TelegramClient(StringSession(session), int(aid), ahash,
                            request_retries=0, connection_retries=2,
                            flood_sleep_threshold=0, receive_updates=False)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "publish_actions": 0, "channels": {}}
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("La session personnelle Telegram n'est plus autorisée.")
        for name, cfg, token in requested_channels():
            try:
                # Validates actual IDs, distinct destinations, real source handles.
                sources, private, public, _, _, _ = await preflight(client, None, cfg)
                if len(sources) != len(cfg["sources"]):
                    raise RuntimeError(
                        f"Sources accessibles {len(sources)}/{len(cfg['sources'])} ; vérifier les canaux.")
                user = await client.get_me()
                user_permissions = await client.get_permissions(private, user)
                if not (getattr(user_permissions, "is_creator", False) or
                        (getattr(user_permissions, "is_admin", False) and
                         getattr(user_permissions, "post_messages", False))):
                    raise RuntimeError("Le compte utilisateur ne peut pas publier dans la bibliothèque privée.")
                if not token:
                    raise RuntimeError("Bot de publication absent de la configuration.")
                bot = BotHTTPClient(token, client)
                identity = await bot.get_me()
                perm = await bot.get_permissions(public, identity)
                if not (perm.is_creator or (perm.is_admin and perm.post_messages)):
                    raise RuntimeError("Le bot n'a pas le droit de publier dans la destination.")
                # The actual numeric IDs have already been cross-checked in preflight.
                report["channels"][name] = {"status": "ok",
                                            "sources_validated": len(sources),
                                            "private_id_verified": True,
                                            "public_id_verified": True,
                                            "user_can_post_private": True,
                                            "bot_can_post": True}
                LOG.info("Canaux %s : sources=%s, IDs cohérents, droits bot OK",
                         name, len(sources))
            except Exception as exc:
                # No private IDs or bot tokens in the report.
                report["channels"][name] = {"status": "error",
                                            "error_type": type(exc).__name__}
                LOG.error("Canaux %s : vérification refusée (%s)", name, type(exc).__name__)
    finally:
        await client.disconnect()
    report["status"] = ("ok" if report["channels"] and
                        all(s["status"] == "ok" for s in report["channels"].values())
                        else "needs_attention")
    return report


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = asyncio.run(verify())
    folder = Path("state")
    folder.mkdir(exist_ok=True)
    (folder / "channel_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("AUDIT_CANAL : " + json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
