"""Safe and throttled Telegram channel profile synchronization for Ciné X.

The actual channel photo/description is read from Telegram's owner session.
Source photo bytes are only held in memory, never committed to GitHub.
The verified source photo ID and description digest are checkpointed.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
from html import unescape

LOG = logging.getLogger("cinex.channel_profile")
DEFAULT_PAUSE = 45
MAX_ABOUT = 255


def digest(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def about_text(text: str) -> str:
    """Telegram descriptions are short; never push markup or HTML entities."""
    from re import sub
    clean = sub(r"<[^>]*>", " ", unescape(str(text or "")))
    clean = sub(r"[\x00-\x08\x0b-\x1f]", "", clean)
    clean = sub(r"\s+", " ", clean).strip()
    if len(clean) <= MAX_ABOUT:
        return clean
    return clean[: MAX_ABOUT - 1].rstrip(" ,.;:-") + "…"


def trend_description(item: dict, candidate: dict | None = None) -> str:
    """Use actual Cine Radar synopsis, with clear fallback from the film's card."""
    import re
    summary = (item.get("summary") or "").strip()
    if not summary and candidate:
        caption = str(candidate.get("poster_caption") or "")
        # Never use the first title line as a fabricated synopsis.
        chunks = [line.strip() for line in caption.splitlines()[1:] if line.strip()]
        summary = next((re.sub(r"^(?:synopsis|résumé|description)\s*:\s*", "", line,
                               flags=re.IGNORECASE)
                        for line in chunks if re.match(r"^(?:synopsis|résumé|description)\s*:", line,
                                                      flags=re.IGNORECASE)), "")
    if not summary:
        # Do not invent a film plot.
        summary = f"Fiche de {item.get('title', 'ce titre')} sur Ciné X. Saison(s) et contenu(s) disponibles dans ce canal."
    return about_text(summary)


async def get_channel_about(client, channel) -> str:
    from telethon import functions
    result = await client(functions.channels.GetFullChannelRequest(channel=channel))
    return str(getattr(getattr(result, "full_chat", None), "about", "") or "")


async def sync_description(client, target, desired: str, record: dict, *,
                           key: str = "description_digest", pause: int = DEFAULT_PAUSE,
                           preserve_format: bool = False) -> bool:
    """Always verify the actual Telegram about even if a previous receipt exists."""
    from telethon import functions
    desired = str(desired) if preserve_format else about_text(desired)
    if len(desired) > MAX_ABOUT:
        raise ValueError("Description trop longue pour Telegram : ne pas tronquer une copie exacte")
    if not desired:
        LOG.warning("Description source vide ; ancienne description conservée")
        return False
    original = await get_channel_about(client, target)
    if original == desired:
        record[key] = digest(desired)
        return False
    await client(functions.channels.EditAboutRequest(channel=target, about=desired))
    confirmed = await get_channel_about(client, target)
    if confirmed != desired:
        raise RuntimeError("Description Telegram non confirmée ; checkpoint refusé")
    record[key] = digest(desired)
    await asyncio.sleep(pause)
    return True


async def sync_photo(client, target, source_photo, record: dict, *,
                     key: str = "profile_photo_source_id",
                     pause: int = DEFAULT_PAUSE) -> bool:
    """Photo must be a verified Telegram photo, not an untrusted external URL."""
    from telethon import functions, types
    source = source_photo
    source_id = int(getattr(source, "id", 0) or getattr(source, "photo_id", 0) or 0)
    if not source_id:
        LOG.warning("Aucune photo Telegram vérifiable : profil non modifié")
        return False
    if record.get(key) == source_id and getattr(target, "photo", None):
        return False
    photo_bytes = await client.download_media(source, file=bytes)
    if not photo_bytes:
        raise RuntimeError("Photo de profil Telegram inaccessible")
    if not 128 <= len(photo_bytes) <= 10_000_000:
        raise RuntimeError("Photo hors limites autorisées")
    # Photo sizes can be smaller than a channel avatar; convert to JPEG square.
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(photo_bytes)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        # Crop to square so that Telegram's round profile thumbnail remains legible.
        side = min(img.size)
        left, top = (img.width - side) // 2, (img.height - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img.thumbnail((768, 768), Image.Resampling.LANCZOS)
        stream = io.BytesIO()
        img.save(stream, format="JPEG", quality=90, optimize=True)
    stream.seek(0)
    stream.name = "cinex_profile.jpg"
    uploaded = await client.upload_file(stream)
    await client(functions.channels.EditPhotoRequest(
        channel=target, photo=types.InputChatUploadedPhoto(file=uploaded)))
    # Confirm target has an avatar; Telegram assigns a new photo_id on upload.
    refreshed = await client.get_entity(target)
    if not getattr(refreshed, "photo", None):
        raise RuntimeError("Photo de profil Telegram non confirmée")
    record[key] = source_id
    await asyncio.sleep(pause)
    return True


async def sync_rescue_profile(client, public, rescue, record: dict, *, pause: int = DEFAULT_PAUSE):
    """Mirror Telegram avatar and *exact* description of the public channel."""
    from telethon import functions
    original = await get_channel_about(client, public)
    # Original description may be empty; do not use a synthetic replacement.
    description_changed = False
    if original:
        description_changed = await sync_description(
            client, rescue, original, record,
            key="description_digest", pause=pause, preserve_format=True)
    # ChannelPhoto is not sufficient for download_media in all Telegram versions.
    # download_profile_photo reads the real current profile avatar via Telethon.
    source_photo_id = int(getattr(getattr(public, "photo", None), "photo_id", 0) or 0)
    photo_changed = False
    if source_photo_id and (record.get("profile_photo_source_id") != source_photo_id
                            or not getattr(rescue, "photo", None)):
        image = await client.download_profile_photo(public, file=bytes)
        if not image:
            raise RuntimeError("Impossible de télécharger l'avatar du canal source")
        photo_changed = await sync_photo_bytes(
            client, rescue, image, source_photo_id, record, pause=pause)
    return description_changed, photo_changed


async def sync_photo_bytes(client, target, content: bytes, source_id: int, record: dict,
                           *, key="profile_photo_source_id", pause=DEFAULT_PAUSE) -> bool:
    from telethon import functions, types
    from PIL import Image, ImageOps
    if source_id <= 0 or not content or len(content) > 10_000_000:
        raise ValueError("Photo Telegram source absente ou invalide")
    if record.get(key) == source_id and getattr(target, "photo", None):
        return False
    with Image.open(io.BytesIO(content)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        side = min(img.size)
        if side < 16:
            raise ValueError("Avatar source trop petit")
        left, top = (img.width-side)//2, (img.height-side)//2
        img = img.crop((left,top,left+side,top+side))
        img.thumbnail((768,768),Image.Resampling.LANCZOS)
        stream=io.BytesIO()
        img.save(stream,format="JPEG",quality=90,optimize=True)
    stream.name="cinex_profile.jpg"
    stream.seek(0)
    uploaded=await client.upload_file(stream)
    await client(functions.channels.EditPhotoRequest(
        channel=target,photo=types.InputChatUploadedPhoto(file=uploaded)))
    target_photo = await client.get_entity(target)
    if not getattr(target_photo, "photo", None):
        raise RuntimeError("Nouvel avatar Telegram absent après envoi")
    record[key]=source_id
    await asyncio.sleep(pause)
    return True


async def sync_trend_profile(client, channel, item: dict, poster, record: dict,
                             *, pause: int = DEFAULT_PAUSE):
    """Poster photo from verified Cine X publication, synopsis from Cine Radar."""
    summary = trend_description(item, {"poster_caption":getattr(poster, "raw_text", "")})
    changed_desc = await sync_description(
        client,channel,summary,record,key="description_digest",pause=pause)
    photo = getattr(poster,"photo",None)
    if photo is None:
        LOG.warning("Affiche absente pour %s",item.get("title"))
        return changed_desc,False
    photo_id=int(getattr(photo,"id",0) or 0)
    if photo_id and record.get("profile_photo_source_id")==photo_id and getattr(channel,"photo",None):
        return changed_desc,False
    content=await client.download_media(poster.media,file=bytes)
    if not content:
        raise RuntimeError("Affiche du contenu tendance introuvable")
    changed_photo=await sync_photo_bytes(client,channel,content,photo_id,record,pause=pause)
    return changed_desc,changed_photo
