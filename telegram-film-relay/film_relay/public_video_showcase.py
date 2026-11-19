"""After the existing film relay, show up to two recent completed films directly.

No reupload of movies already present on public Telegram (matched by document ID).
No publication from a missing or unverified private video / bot poster.
"""
from __future__ import annotations

import asyncio
import logging
import os

from .publication import rich_video_title
from .public_video_archive import is_video_message, video_document_id
from .state import State
from .text import first_title

LOG = logging.getLogger("cinex.public_showcase")


def select_recent_completed(records: dict, public_ids: set[int], count: int = 2):
    """Only already published posters currently present in the recent public page."""
    candidates = [
        entry for entry in records.values()
        if isinstance(entry, dict)
        and entry.get("public_message_id") in public_ids
        and entry.get("private_message_id")
    ]
    return sorted(candidates, key=lambda x: x["public_message_id"], reverse=True)[:count]


async def run() -> int:
    from telethon import TelegramClient, utils
    from telethon.sessions import StringSession
    from telethon.errors import FloodWaitError, PeerFloodError

    api_id = os.getenv("TG_API_ID", "")
    api_hash = os.getenv("TG_API_HASH", "")
    session = (os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING")
               or os.getenv("TG_STREAM_SESSION") or "")
    private_name = os.getenv("TG_PRIVATE_CHANNEL", "")
    public_name = os.getenv("TG_PUBLIC_CHANNEL", "")
    if not (api_id and api_hash and session and private_name and public_name):
        raise RuntimeError("Identifiants Telegram manquants")
    if public_name.lower() != "@cinexfilms_vf":
        raise RuntimeError("Canal public incorrect : publication interdite hors @CineXFilms_vf")

    state = State("state/state.json")
    client = TelegramClient(StringSession(session), int(api_id), api_hash,
                            request_retries=1, flood_sleep_threshold=0)
    await client.connect()
    published = 0
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Session personnelle expirée")
        public = await client.get_entity(public_name)
        private = await client.get_entity(int(private_name)
                                          if private_name.lstrip("-").isdigit() else private_name)
        if utils.get_peer_id(public) == utils.get_peer_id(private):
            raise RuntimeError("Canaux identiques")
        recent_messages = [m async for m in client.iter_messages(public, limit=80)]
        recent_ids = {m.id for m in recent_messages}
        recent_by_id = {m.id: m for m in recent_messages}
        existing_docs = {video_document_id(m) for m in recent_messages if is_video_message(m)}
        for entry in select_recent_completed(state.data["processed"], recent_ids):
            poster_id, private_id = entry["public_message_id"], entry["private_message_id"]
            poster = recent_by_id.get(poster_id)
            if not poster or not getattr(poster, "photo", None):
                LOG.warning("Affiche #%s manquante : pas de vidéo publique", poster_id)
                continue
            source = await client.get_messages(private, ids=private_id)
            if not source or not is_video_message(source):
                LOG.warning("Vidéothèque #%s indisponible : publication interdite", private_id)
                continue
            doc_id = video_document_id(source)
            if doc_id in existing_docs:
                LOG.info("Film déjà en vitrine, document %s : ignoré", doc_id)
                continue
            title = first_title(poster.raw_text or source.raw_text or "Film")
            LOG.info("Film à montrer directement : %s (doc %s)", title, doc_id)
            if os.getenv("CINEX_SHOWCASE_ENABLED", "").lower() != "true":
                continue
            try:
                sent = await client.send_file(public, source.media,
                                              caption=rich_video_title(title),
                                              parse_mode="html")
                check = await client.get_messages(public, ids=sent.id)
                if not check or video_document_id(check) != doc_id:
                    raise RuntimeError("Vidéopost non confirmé")
                existing_docs.add(doc_id)
                published += 1
                LOG.info("Vidéo publique #%s postée, affiche #%s", sent.id, poster_id)
                await asyncio.sleep(15)
            except (FloodWaitError, PeerFloodError):
                raise
            except Exception:
                LOG.exception("Échec vitrine doc %s ; nouveau cycle peut réessayer", doc_id)
                raise
        LOG.info("Films avec vidéo dans la vitrine publiés dans ce cycle : %d", published)
        return published
    finally:
        await client.disconnect()


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
