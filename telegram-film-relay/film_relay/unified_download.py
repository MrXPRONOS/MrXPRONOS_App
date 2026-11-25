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
        self.cover_index: dict[str, int] = {}
        self.source_index: dict[str, int] = {}
        self.legacy_cover_proofs: dict[int, int] = {}
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
            self.cover_index = {}
            self.source_index = {}
            async for item in self.client.iter_messages(self.peer, limit=self.history):
                if is_video_message(item):
                    doc = video_document_id(item)
                    if doc:
                        self.index.setdefault(int(doc), int(item.id))
                    from .private_media_contract import source_marker_from_message
                    marker = source_marker_from_message(item)
                    if marker:
                        self.source_index.setdefault(marker, int(item.id))
                elif getattr(item, "photo", None):
                    # Preserve receipts for unfinished uploads across restarts:
                    # a cover already sent must never be blindly sent again.
                    for marker in re.findall(r"#CXSTOCK_[a-f0-9]{16}", str(getattr(item, "raw_text", "") or "")):
                        self.cover_index.setdefault(marker, int(item.id))
            LOG.info("CinéX bibliothèque centrale : %s vidéos distinctes indexées", len(self.index))
        return self.peer

    def verified_cover_for(self, document_id: int) -> bool:
        """True only when the canonical marker is on a photo preceding this stored video."""
        doc = int(document_id)
        marker = "#CXSTOCK_" + hashlib.sha256(str(doc).encode()).hexdigest()[:16]
        mid = (self.index or {}).get(doc)
        cover_mid = self.cover_index.get(marker)
        return bool(mid and ((cover_mid and 0 < mid - cover_mid <= 3)
                             or self.legacy_cover_proofs.get(doc) == mid))

    async def verify_legacy_adjacent_cover(self, document_id, video_mid, source_poster):
        """Read-only recovery: exact same Telegram photo immediately before video.

        No title similarity, no new uploads, no edits, no fabricated marker.
        A historic cover which has been recompressed or is missing requires
        owner review. A conflicting stock marker is never accepted.
        """
        photo_id = getattr(getattr(source_poster, "photo", None), "id", None)
        if not photo_id or getattr(source_poster, "noforwards", False) or video_mid <= 1:
            return False
        cover = await self.client.get_messages(self.peer, ids=int(video_mid) - 1)
        if (not cover or int(getattr(cover, "id", 0)) != int(video_mid) - 1
                or getattr(getattr(cover, "photo", None), "id", None) != photo_id):
            return False
        text = str(getattr(cover, "raw_text", "") or "").strip()
        expected = "#CXSTOCK_" + hashlib.sha256(str(document_id).encode()).hexdigest()[:16]
        markers = re.findall(r"#CXSTOCK_[a-f0-9]{16}", text)
        if not text or any(marker != expected for marker in markers):
            return False
        if not re.sub(r"#CXSTOCK_[a-f0-9]{16}", "", text).strip():
            return False
        self.legacy_cover_proofs[int(document_id)] = int(video_mid)
        LOG.info("CinéX stock : affiche historique contiguë authentifiée par identité photo exacte")
        return True

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
        from .text import resolved_media_title, description_with_title, clean_caption
        title = resolved_media_title(poster, source, preferred=title, description=description)
        details = description_with_title(
            title, description,
            clean_caption(getattr(poster, "raw_text", "") or "", getattr(poster, "entities", None)),
            clean_caption(getattr(source, "raw_text", "") or "", getattr(source, "entities", None)))
        await self.prepare(public=public)
        doc_id = int(doc_id)
        from .private_media_contract import (
            marker_for, renamed_receipt_matches, original_filename, filename_for,
            send_named_private_video,
        )
        source_tag = marker_for(source)
        mid = self.source_index.get(source_tag) or self.index.get(doc_id)
        if mid:
            existing = await self.client.get_messages(self.peer, ids=mid)
            if (is_video_message(existing)
                    and (video_document_id(existing) == doc_id or
                         renamed_receipt_matches(source, existing, title=title,
                                                 poster=poster, description=details))):
                # A historical video-only receipt is not evidence of the
                # required PHOTO+description then VIDEO pair. It can remain
                # downloadable via an existing registry link, but new public
                # poster registrations must not misrepresent it as complete.
                if (poster is not None and not self.verified_cover_for(doc_id)
                        and not await self.verify_legacy_adjacent_cover(doc_id, mid, poster)):
                    raise RuntimeError(
                        "Vidéo centrale ancienne sans affiche adjacente vérifiée ; "
                        "restauration manuelle nécessaire, aucun nouvel envoi.")
                if original_filename(existing) != filename_for(
                        source, title=title, poster=poster, description=details):
                    LOG.warning("Stock CineRadar historique : nom réel du fichier ancien "
                                "non conforme, reçu conservé pour ne pas casser les anciens liens")
                self.index[doc_id] = mid
                return registry.register(
                    private_channel=self.target_id, message_id=mid,
                    title=title, public_handle=handle)
            raise RuntimeError("Reçu de vidéothèque centrale incohérent ; aucun nouveau lien publié.")

        # New central copies are forbidden without their real source poster.
        # Existing video receipts above remain reusable without republication.
        if poster is None or not getattr(poster, "photo", None) or getattr(poster, "noforwards", False):
            raise RuntimeError("Affiche du stock central absente ou protégée : aucune vidéo seule envoyée.")
        from .publication import rich_caption
        marker = "#CXSTOCK_" + hashlib.sha256(str(doc_id).encode()).hexdigest()[:16]
        cover_caption = rich_caption(details, private=True) + "\n" + marker
        existing_cover_id = self.cover_index.get(marker)
        if existing_cover_id:
            # Resume *only* if the same marked cover is the last channel post.
            # Otherwise another upload has intervened and adjacent pairing
            # cannot be proven: stop rather than create a duplicate photo/video.
            recent = [m async for m in self.client.iter_messages(self.peer, limit=1)]
            previous = recent[0] if recent else None
            if (previous is None or int(previous.id) != existing_cover_id
                    or not getattr(previous, "photo", None)
                    or marker not in str(getattr(previous, "raw_text", "") or "")):
                raise RuntimeError("Affiche centrale déjà envoyée mais non contiguë : vérification manuelle, aucun doublon.")
            LOG.info("CinéX stock: affiche en attente réutilisée sans doublon")
        else:
            # Some recovered Telegram photo messages expose .photo but their
            # .media wrapper is absent. Use the genuine Photo as a fallback;
            # never pass None to Telethon and never use a WebPage preview.
            photo_file = getattr(poster, "media", None) or getattr(poster, "photo", None)
            if photo_file is None:
                raise RuntimeError("Affiche source Telegram sans média photo exploitable.")
            cover = await self.client.send_file(
                self.peer, photo_file, caption=cover_caption,
                parse_mode="html",
            )
            checked = await self.client.get_messages(self.peer, ids=int(cover.id))
            if (not getattr(checked, "photo", None)
                    or marker not in str(getattr(checked, "raw_text", "") or "")):
                raise RuntimeError("Affiche du stock central non vérifiée ; vidéo non envoyée.")
            self.cover_index[marker] = int(cover.id)
        from .publication import rich_video_title
        private_cover_id = self.cover_index[marker]
        recorded = await send_named_private_video(
            self.client, self.peer, source,
            title=title, caption=rich_video_title(title),
            private_cover_id=private_cover_id,
            poster=poster, description=details,
        )
        mid = int(recorded.id)
        self.index[doc_id] = mid
        self.source_index[source_tag] = mid
        LOG.info("CinéX bibliothèque centrale : vidéo confirmée catégorie=%s message=%s",
                 category, mid)
        return registry.register(
            private_channel=self.target_id, message_id=mid,
            title=title, public_handle=handle)
