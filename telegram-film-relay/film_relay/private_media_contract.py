"""Actual Telegram document filenames for owner-session CineX private libraries.

A caption or a server-side copy NEVER changes DocumentAttributeFilename.
Only a new upload from correctly named bytes can do that; see Telegram API.
This module fails closed (no wrong-named receipt) if a safe reupload is unavailable.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from pathlib import Path, PurePath
import re
import shutil
import tempfile
import unicodedata

from .public_video_archive import is_video_message, video_document_id
from .text import resolved_media_title

LOG = logging.getLogger("cinex.private_media_contract")
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
GENERIC = re.compile(r"(?i)^(?:film|video|movie|fichier|document|upload|unknown|sans titre)[\W_0-9]*$")
CONTROL = re.compile(r"[\x00-\x1f\x7f/\\:*?\"<>|]+")
SOURCE_MARKER = re.compile(r"#CXFILE_([a-f0-9]{20})")


def original_filename(media) -> str:
    name = getattr(getattr(media, "file", None), "name", "") or ""
    if name:
        return PurePath(str(name).replace("\\", "/")).name
    for attr in getattr(getattr(media, "document", None), "attributes", ()) or ():
        if type(attr).__name__ == "DocumentAttributeFilename":
            return PurePath(str(attr.file_name).replace("\\", "/")).name
    return ""


def filename_for(media, *, title: str, poster=None, description: str = "") -> str:
    """Keep an explicit season / episode / part number, never fabricate it."""
    from .title_guard import filename_title
    name = original_filename(media)
    suffix = PurePath(name).suffix.lower()
    if suffix not in VIDEO_EXTS:
        mime = str(getattr(getattr(media, "document", None), "mime_type", "") or "")
        suffix = { "video/mp4": ".mp4", "video/x-matroska": ".mkv",
                   "video/quicktime": ".mov", "video/webm": ".webm"}.get(mime, "")
    if suffix not in VIDEO_EXTS:
        raise RuntimeError("Source sans extension vidéo vérifiable")
    # Use the prevalidated publication title, then the original poster and
    # filename, but never a generic catch-all or a made-up movie name.
    chosen = resolved_media_title(poster, media, preferred=title, description=description)
    if chosen.casefold().startswith("titre non identifi"):
        candidate = filename_title(name) if name else ""
        chosen = candidate or ""
    chosen = unicodedata.normalize("NFKC", chosen).strip()
    chosen = CONTROL.sub(" ", chosen)
    chosen = re.sub(r"\s+", " ", chosen).strip(" ._-")
    if len(chosen) < 3 or GENERIC.fullmatch(chosen):
        raise RuntimeError("Nom descriptif absent : vidéo non stockée")
    return chosen[:135].rstrip(" ._-") + suffix


def marker_for(source) -> str:
    doc = video_document_id(source)
    if not doc:
        raise RuntimeError("Identité du document source absente")
    return "#CXFILE_" + hashlib.sha256(str(int(doc)).encode()).hexdigest()[:20]



def bot_copy_source_filename_valid(filename: str, title: str, episode_code: str) -> bool:
    """Bot API copyMessage cannot rename: allow only verifiably named sources."""
    from .private_stock_audit import filename_descriptive
    if not filename_descriptive(filename):
        return False
    if not re.fullmatch(r"S\d{2}E\d{2,3}", episode_code):
        return False
    def tokens(value):
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        normalized = normalized.encode("ascii", "ignore").decode().lower()
        return re.findall(r"[a-z0-9]+", normalized)
    stem = " ".join(tokens(PurePath(filename).stem))
    required = tokens(title)
    if not required or not all(token in stem.split() for token in required):
        return False
    return episode_code.lower() in stem.replace(" ", "").lower()


def source_marker_from_message(message) -> str | None:
    match = SOURCE_MARKER.search(str(getattr(message, "raw_text", "") or ""))
    return "#CXFILE_" + match.group(1) if match else None


def renamed_receipt_matches(source, receipt, *, title: str, poster=None,
                            description: str = "") -> bool:
    """Exact resulting filename and byte count, with source-provenance marker."""
    if not is_video_message(receipt):
        return False
    try:
        required = filename_for(source, title=title, poster=poster,
                                description=description)
    except RuntimeError:
        return False
    if original_filename(receipt) != required:
        return False
    a = getattr(getattr(source, "document", None), "size", None)
    b = getattr(getattr(receipt, "document", None), "size", None)
    if a and b and int(a) != int(b):
        return False
    if (video_document_id(receipt) != video_document_id(source)
            and source_marker_from_message(receipt) != marker_for(source)):
        return False
    return True


async def private_cover_verified(client, destination, poster_id) -> bool:
    if not poster_id:
        return False
    cover = await client.get_messages(destination, ids=int(poster_id))
    return bool(getattr(cover, "photo", None)
                and (getattr(cover, "raw_text", "") or "").strip())


async def send_named_private_video(
    client, destination, source, *, title: str, caption: str,
    private_cover_id: int, poster=None, description: str = "",
):
    """Send only after confirmed cover, then verify true filename and contents.

    If original name already equals target, fast server-side copy keeps document
    identity. Otherwise download into a temporary isolated directory and
    reupload under the desired name. No silent fallback to an unchanged name.
    """
    if not is_video_message(source) or getattr(source, "noforwards", False):
        raise RuntimeError("Vidéo source absente ou protégée")
    if not await private_cover_verified(client, destination, private_cover_id):
        raise RuntimeError("Affiche privée et description absentes avant vidéo")
    name = filename_for(source, title=title, poster=poster, description=description)
    tag = marker_for(source)
    text = caption.strip()
    if tag not in text:
        text += "\n" + tag
    if original_filename(source) == name:
        sent = await client.send_file(destination, source.media,
                                      caption=text, parse_mode="html")
    else:
        size = getattr(getattr(source, "document", None), "size", None)
        if not size or int(size) <= 0:
            raise RuntimeError("Taille du fichier source inconnue ; renommage suspendu")
        required = int(size) + 512 * 1024 * 1024
        if shutil.disk_usage(tempfile.gettempdir()).free < required:
            raise RuntimeError("Espace temporaire insuffisant pour renommer sans perdre la vidéo")
        # Disk quota is per runner; never keep source bytes after uploading.
        with tempfile.TemporaryDirectory(prefix="cinex-rename-") as directory:
            path = Path(directory) / name
            downloaded = await client.download_media(source, file=str(path))
            if not downloaded:
                raise RuntimeError("Téléchargement temporaire source échoué")
            actual = Path(str(downloaded))
            if not actual.is_file() or actual.stat().st_size != int(size):
                raise RuntimeError("Taille des données téléchargées différente de la source")
            LOG.info("Réimportation d'une vidéo sous un nom descriptif vérifiable")
            sent = await client.send_file(
                destination, str(actual), caption=text, parse_mode="html",
                force_document=True,
            )
    confirmed = await client.get_messages(destination, ids=int(sent.id))
    if not renamed_receipt_matches(source, confirmed, title=title,
                                   poster=poster, description=description):
        raise RuntimeError(
            "Vidéo envoyée mais nom, taille ou origine incorrects : "
            "publication bloquée et contrôle manuel requis")
    if int(confirmed.id) <= int(private_cover_id):
        raise RuntimeError("Vidéo privée avant affiche : reçu incohérent")
    return confirmed
