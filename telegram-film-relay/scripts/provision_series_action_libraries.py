"""One-time private CineX Séries / Action library provisioning.

The owner user session creates the two private broadcast channels, with the
current public channel profile photo and description. No auto-join, source
authorization, bot-admin permission change, GitHub variable mutation, or
invitation export. Idempotent by exact private title.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os

from film_relay.channel_profiles import sync_rescue_profile

LOG = logging.getLogger("cinex.provision_libraries")
TARGETS = (
    ("SERIES", "@seriesvf_cinex", "Ciné X Séries Vidéothèque"),
    ("ACTION", "@filmsaction2026vf", "Ciné X Action Vidéothèque"),
)


async def provision(*, apply: bool = False, pause: int = 45):
    from telethon import TelegramClient, functions, utils
    from telethon.errors import FloodWaitError, PeerFloodError
    from telethon.sessions import StringSession

    api_id = os.getenv("TG_API_ID", "").strip()
    api_hash = os.getenv("TG_API_HASH", "").strip()
    session = (os.getenv("TG_STRING_SESSION") or
               os.getenv("TG_SESSION_STRING") or
               os.getenv("TG_STREAM_SESSION") or "").strip()
    if not api_id or not api_hash or not session:
        raise RuntimeError("Secrets Telegram de la session utilisateur absents.")
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            flood_sleep_threshold=0, request_retries=1,
                            connection_retries=2)
    await client.connect()
    results = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session personnelle Telegram non autorisée.")
        account = await client.get_me()
        dialogs = [d.entity async for d in client.iter_dialogs(limit=500)]
        for prefix, public_handle, library_title in TARGETS:
            try:
                public = await client.get_entity(public_handle)
                if (not getattr(public, "broadcast", False) or
                    str(getattr(public, "username", "") or "").casefold()
                        != public_handle[1:].casefold()):
                    raise RuntimeError("Canal public de référence incorrect.")

                existing = [entity for entity in dialogs
                            if getattr(entity, "broadcast", False)
                            and not getattr(entity, "username", None)
                            and getattr(entity, "title", "") == library_title]
                if len(existing) > 1:
                    raise RuntimeError("Plusieurs canaux privés homonymes ; création refusée.")
                private = existing[0] if existing else None
                created = False
                if not private and apply:
                    response = await client(functions.channels.CreateChannelRequest(
                        title=library_title, about="", broadcast=True, megagroup=False))
                    private = next((entity for entity in response.chats
                                    if getattr(entity, "broadcast", False)
                                    and getattr(entity, "title", "") == library_title), None)
                    if not private or getattr(private, "username", None):
                        raise RuntimeError("Telegram n'a pas confirmé un canal privé.")
                    dialogs.append(private)
                    created = True
                    await asyncio.sleep(pause)
                if not private:
                    LOG.info("[SIMULATION] %s : canal privé à créer depuis %s",
                             prefix, public_handle)
                    results.append((prefix, public_handle, "SIMULATION", ""))
                    continue
                if utils.get_peer_id(private) == utils.get_peer_id(public):
                    raise RuntimeError("Canal source et vidéothèque identiques.")
                permissions = await client.get_permissions(private, account)
                if not getattr(permissions, "is_creator", False):
                    raise RuntimeError("Ce compte n'est pas propriétaire de la vidéothèque.")
                if apply:
                    record = {}
                    await sync_rescue_profile(client, public, private, record, pause=pause)
                numeric_id = utils.get_peer_id(private)
                if not str(numeric_id).startswith("-100"):
                    raise RuntimeError("Identifiant de canal privé invalide.")
                LOG.info("%s : vidéothèque %s (id=%s), création=%s",
                         prefix, library_title, numeric_id, created)
                results.append((prefix, public_handle, "CRÉÉ" if created else "EXISTANT",
                                str(numeric_id)))
            except (FloodWaitError, PeerFloodError):
                raise
            except Exception:
                LOG.exception("%s : provisioning interrompu", prefix)
                raise
        if apply:
            summary = os.getenv("GITHUB_STEP_SUMMARY", "")
            output = os.getenv("GITHUB_OUTPUT", "")
            lines = [
                "## CinéX — nouvelles vidéothèques privées",
                "| Catégorie | Canal principal | État | GitHub Variable | ID privé |",
                "|---|---|---|---|---|",
            ] + [
                f"| {prefix} | {handle} | {status} | "
                f"{prefix}_PRIVATE_CHANNEL | {ident} |"
                for prefix, handle, status, ident in results
            ]
            if summary:
                with open(summary, "a", encoding="utf-8") as stream:
                    stream.write("\n".join(lines) + "\n")
            if output:
                with open(output, "a", encoding="utf-8") as stream:
                    for prefix, _, _, ident in results:
                        stream.write(f"{prefix.lower()}_private_id={ident}\n")
        return results
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pause", type=int, default=45)
    args = parser.parse_args()
    if args.pause < 12:
        parser.error("Pause minimale : 12 secondes.")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(provision(apply=args.apply, pause=args.pause))


if __name__ == "__main__":
    main()
