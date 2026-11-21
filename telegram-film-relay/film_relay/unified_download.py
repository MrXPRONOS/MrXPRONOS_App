"""Opt-in central Telegram download library for every CineX category.

The category libraries and existing public links remain valid. If the owner
configures CINEX_UNIFIED_PRIVATE_CHANNEL, each newly shared source video is
verified in one central PRIVATE channel before its public download link appears.
No automatic creation, invitations, downloads to disk, or deletions.
"""
from __future__ import annotations

from html import escape
import hashlib
import logging
import os
import re

from .public_video_archive import is_video_message, video_document_id
from .radar_download_registry import RadarRegistry

LOG = logging.getLogger("cinex.unified_download")
VARIABLE = "CINEX_UNIFIED_PRIVATE_CHANNEL"
_ALLOWED = {"films", "series", "anime", "action", "comedie", "desir"}


def configured_private_id(env=None) -> int | None:
    """Opt in only to the owner-confirmed private channel (SHA-256 receipt).

    If GitHub's variable has not yet been configured, use only the *already
    verified* CineRadar stock ID from D1, provided that its SHA-256 equals
    the explicit owner-approved digest from the workflow. Do not discover
    arbitrary Telegram channels or silently accept a different ID.
    """
    env = env if env is not None else os.environ
    value = str(env.get(VARIABLE, "") or "").strip()
    approved = str(env.get("CINEX_UNIFIED_STOCK_APPROVED_SHA256", "") or "").strip().lower()
    if not value and not approved:
        return None
    if approved and not re.fullmatch(r"[a-f0-9]{64}", approved):
        raise RuntimeError("Empreinte du canal central invalide.")
    if not value:
        registry = RadarRegistry(env=env)
        rows = registry._query(
            "SELECT stock_chat_id FROM cine_private_stock_config "
            "WHERE singleton=1 AND ready=1 AND radar_bot_id>0 LIMIT 1"
        ).get("results") or []
        if len(rows) != 1:
            raise RuntimeError("Stock prive CineRadar non valide : aucune destination active.")
        value = str(rows[0].get("stock_chat_id") or "")
    if not re.fullmatch(r"-100[0-9]{5,}", value):
        raise RuntimeError(
            VARIABLE + " doit être l'identifiant numérique exact -100... "
            "du nouveau canal privé (aucune déduction depuis son nom)."
        )
    if approved and hashlib.sha256(value.encode("utf-8")).hexdigest() != approved:
        raise RuntimeError("Le canal privé ne correspond pas à celui confirmé par le propriétaire.")
    return int(value)


class UnifiedLibrary:
    """One per Telegram-client run, with document-ID deduplication."""

    def __init__(self, client, *, env=None, history: int = 4000, registry=None):
        self.client = client
        self.env = env if env is not None else os.environ
        self.target_id = configured_private_id(self.env)
        self.history = history
        self.peer = None
        self.index: dict[int, int] | None = None
        self.registry = registry

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

    async def store(self, source, *, category: str, title: str, public=None, poster=None, description: str = ""):
        """Return a verified CineRadar bot deep link or None when not enabled.

        Never return a URL for a failed send. Re-read an existing receipt or a
        newly sent message to verify that the document is identical.
        """
        if self.target_id is None:
            return None
        if category not in _ALLOWED:
            raise ValueError("Catégorie centrale inconnue.")
        # CineRadar is the download client, NOT a direct private-channel link.
        handle = getattr(public, "username", None)
        if not isinstance(handle, str) or not handle:
            raise RuntimeError("Téléchargement CineRadar : canal public sans @username fiable.")
        handle = "@" + handle.lstrip("@")
        registry = self.registry or RadarRegistry(env=self.env if hasattr(self, "env") else None)
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
                return registry.register(
                    private_channel=self.target_id, message_id=mid,
                    title=title, public_handle=handle)
            raise RuntimeError("Reçu de vidéothèque centrale incohérent ; aucun nouveau lien publié.")

        # For NEW uploads with a source poster, the verified central archive
        # must contain the original PHOTO + readable description followed by
        # its VIDEO. The marker permits safe resumption if the photo succeeded
        # but a later step failed. Existing video receipts are never duplicated.
        if poster is not None:
            if not getattr(poster, "photo", None) or getattr(poster, "noforwards", False):
                raise RuntimeError("Affiche du stock central absente ou protégée.")
            from .publication import rich_caption
            marker = "#CXSTOCK_" + hashlib.sha256(str(doc_id).encode()).hexdigest()[:16]
            details = str(description or getattr(poster, "raw_text", "") or title).strip()[:650]
            cover_caption = rich_caption(details, private=True) + "\n" + marker
            recent = [m async for m in self.client.iter_messages(self.peer, limit=1)]
            previous = recent[0] if recent else None
            if (previous and getattr(previous, "photo", None)
                    and marker in str(getattr(previous, "raw_text", "") or "")):
                LOG.info("CinéX stock: affiche en attente réutilisée sans doublon")
            else:
                cover = await self.client.send_file(
                    self.peer, poster.media, caption=cover_caption,
                    parse_mode="html",
                )
                checked = await self.client.get_messages(self.peer, ids=int(cover.id))
                if (not getattr(checked, "photo", None)
                        or marker not in str(getattr(checked, "raw_text", "") or "")):
                    raise RuntimeError("Affiche du stock central non vérifiée ; vidéo non envoyée.")
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
        return registry.register(
            private_channel=self.target_id, message_id=mid,
            title=title, public_handle=handle)
