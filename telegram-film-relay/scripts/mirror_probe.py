"""Read-only verification of CinéX secondary Telegram channel and duplicate MKVs."""
from __future__ import annotations
import asyncio
import os
from collections import Counter

from telethon import TelegramClient
from telethon.sessions import StringSession


async def execute() -> int:
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    session = os.getenv("TG_STRING_SESSION")
    if not (api_id and api_hash and session):
        print("FAIL : identifiants Telegram non renseignés.")
        return 1
    destination = os.getenv("TG_MIRROR_CHANNEL", "@Torrent9SeriesFilms")
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            connection_retries=1, request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            print("FAIL : session Telegram non autorisée.")
            return 1
        try:
            mirror = await client.get_entity(destination)
        except Exception as exc:
            print(f"FAIL : miroir introuvable ({type(exc).__name__}). "
                  "Vérifier le username ou utiliser son ID numérique -100.")
            return 1
        if not getattr(mirror, "broadcast", False):
            print("FAIL : la destination secondaire n'est pas un canal de diffusion.")
            return 1
        print(f"SECOND CANAL RÉSOLU : @{getattr(mirror, 'username', '')}; "
              f"titre : {getattr(mirror, 'title', '')}")
        me = await client.get_me()
        try:
            perms = await client.get_permissions(mirror, me)
            allowed = bool(getattr(perms, "is_creator", False) or
                           (getattr(perms, "is_admin", False) and
                            getattr(perms, "post_messages", False)))
        except Exception as exc:
            print(f"FAIL : impossible de confirmer le droit de publier ({type(exc).__name__}).")
            return 1
        if not allowed:
            print("FAIL : la session n'a pas le droit de publier dans le second canal.")
            return 1
        print("DROIT DE PUBLICATION DU SECOND CANAL : confirmé")

        public = await client.get_entity(os.getenv("TG_PUBLIC_CHANNEL"))
        protected = bool(getattr(public, "noforwards", False))
        print("TRANSFERT DU CANAL PUBLIC PRINCIPAL : " +
              ("BLOQUÉ (protection activée)" if protected else "AUTORISÉ (protection désactivée)"))

        private = await client.get_entity(int(os.getenv("TG_PRIVATE_CHANNEL")))
        doc_ids = Counter()
        async for post in client.iter_messages(private, limit=250):
            doc = getattr(post, "document", None)
            ident = getattr(doc, "id", None)
            if ident is not None:
                doc_ids[int(ident)] += 1
        duplicates = {ident: count for ident, count in doc_ids.items() if count > 1}
        print(f"AUDIT PRIVÉ : {sum(doc_ids.values())} vidéos/documents récents, "
              f"{len(duplicates)} identifiants de document répétés, "
              f"{sum(n-1 for n in duplicates.values())} copies supplémentaires. "
              "Aucun message supprimé.")
        return 0 if not protected else 1
    finally:
        await client.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(execute()))
