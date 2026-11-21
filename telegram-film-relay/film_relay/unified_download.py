"""Opt-in central Telegram download library for every CineX category.

The category libraries and existing public links remain valid. If the owner
configures CINEX_UNIFIED_PRIVATE_CHANNEL, each newly shared source video is
verified in one central PRIVATE channel before its public download link appears.
No automatic creation, invitations, downloads to disk, or deletions.
"""
from __future__ import annotations

from html import escape
import logging
import os
import re

from .public_video_archive import is_video_message, video_document_id
from .text import private_message_link

LOG = logging.getLogger("cinex.unified_download")
VARIABLE = "CINEX_UNIFIED_PRIVATE_CHANNEL"
_ALLOWED = {"films", "series", "anime", "action", "comedie", "desir"}


def configured_private_id(env=None) -> int | None:
    env = env if env is not None else os.environ
    value = str(env.get(VARIABLE, "") or "").strip()
    if not value:
        return None
    if not re.fullmatch(r"-100[0-9]{5,}", value):
        raise RuntimeError(
            VARIABLE + " doit être l'identifiant numérique exact -100... "
            "du nouveau canal privé (aucune déduction depuis son nom)."
        )
    return int(value)


class UnifiedLibrary:
    """One per Telegram-client run, with document-ID deduplication."""

    def __init__(self, client, *, env=None, history: int = 4000):
        self.client = client
        self.target_id = configured_private_id(env)
        self.history = history
        self.peer = None
        self.index: dict[int, int] | None = None

    async def prepare(self, *, public=None):
        if self.target_id is None:
            return None
        from telethon import utils
        from .runner import resolve_peer
        if self.peer is None:
            peer = await resolve_peer(self.client, str(self.target_id))
            actual_id = utils.get_peer_id(peer)
            if actual_id != self.target_id:
                raise RuntimeError("Le canal privé central résolu ne correspond pas à l'ID configuré.")
            if not getattr(peer, "broadcast", False):
                raise RuntimeError("La vidéothèque centrale doit être un canal Telegram, pas un groupe.")
            if getattr(peer, "username", None):
                raise RuntimeError("La vidéothèque centrale doit rester privée (sans @username public).")
            me = await self.client.get_me()
            permission = await self.client.get_permissions(peer, me)
            if not (getattr(permission, "is_creator", False) or (
                getattr(permission, "is_admin", False)
                and getattr(permission, "post_messages", False)
            )):
                raise RuntimeError("Le compte de publication doit pouvoir envoyer dans la vidéothèque centrale.")
            self.peer = peer
        if public is not None and utils.get_peer_id(public) == self.target_id:
            raise RuntimeError("La destination centrale ne peut pas être le canal public.")
        if self.index is None:
            self.index = {}
            async for item in self.client.iter_messages(self.peer, limit=self.history):
                if is_video_message(item):
                    doc = video_document_id(item)
                    if doc:
                        self.index.setdefault(int(doc), int(item.id))
            LOG.info("CinéX bibliothèque centrale : %s vidéos distinctes indexées", len(self.index))
        return self.peer

    async def store(self, source, *, category: str, title: str, public=None):
        """Return a real https://t.me/c/... URL or None when not enabled.

        Never return a URL for a failed send. Re-read an existing receipt or a
        newly sent message to verify that the document is identical.
        """
        if self.target_id is None:
            return None
        if category not in _ALLOWED:
            raise ValueError("Catégorie centrale inconnue.")
        if not is_video_message(source) or getattr(source, "noforwards", False):
            raise RuntimeError("Média privé central : vidéo source inaccessible ou protégée.")
        doc_id = video_document_id(source)
        if not doc_id:
            raise RuntimeError("Média privé central : identifiant du document absent.")
        await self.prepare(public=public)
        doc_id = int(doc_id)
        if doc_id in self.index:
            mid = self.index[doc_id]
            existing = await self.client.get_messages(self.peer, ids=mid)
            if (is_video_message(existing)
                    and video_document_id(existing) == doc_id):
                return private_message_link(self.target_id, mid)
            raise RuntimeError("Reçu de vidéothèque centrale incohérent ; aucun nouveau lien publié.")

        description = escape((title or "Vidéo CinéX").strip()[:700])
        label = category.title()
        caption = f"🎞️ <b>{description}</b>\n📚 CinéX · {label}"
        sent = await self.client.send_file(
            self.peer, source.media, caption=caption, parse_mode="html",
        )
        mid = int(sent.id)
        recorded = await self.client.get_messages(self.peer, ids=mid)
        if (not is_video_message(recorded)
                or video_document_id(recorded) != doc_id):
            raise RuntimeError("Vidéo centrale envoyée mais non vérifiée ; aucun lien public créé.")
        self.index[doc_id] = mid
        LOG.info("CinéX bibliothèque centrale : vidéo confirmée catégorie=%s message=%s",
                 category, mid)
        return private_message_link(self.target_id, mid)
