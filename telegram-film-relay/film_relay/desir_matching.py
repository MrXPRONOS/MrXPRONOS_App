"""Source-media matching for a separate licensed Telegram film relay.

Supports empty photo captions, MKV documents without duration metadata, and MP4.
The source ordering is used as a heuristic; protected posts are never copied.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from .matching import filename_of

@dataclass(frozen=True)
class Item:
    poster: Any | None
    video: Any

def is_supported_video(message: Any) -> bool:
    if getattr(message, "noforwards", False) or getattr(message, "photo", None):
        return False
    doc = getattr(message, "document", None)
    if doc is None:
        return False
    name = filename_of(message)
    mime = str(getattr(doc, "mime_type", "") or "").lower()
    return (name.endswith((".mkv", ".mp4")) or mime in
            ("video/mp4", "video/x-matroska", "application/x-matroska"))
    # No duration or size checks, including for MKV without metadata.

def is_poster(message: Any) -> bool:
    return bool(getattr(message, "photo", None)) and not getattr(message, "noforwards", False)

def pair_items(messages: Sequence[Any], max_gap: int = 4) -> list[Item]:
    ordered = sorted((m for m in messages if getattr(m, "id", None) is not None),
                     key=lambda m: int(m.id))
    claimed = set()
    result = []
    for index, photo in enumerate(ordered):
        if not is_poster(photo):
            continue
        for later in ordered[index + 1:index + max_gap + 1]:
            if is_poster(later):
                break
            if is_supported_video(later):
                if later.id not in claimed:
                    claimed.add(later.id)
                    result.append(Item(photo, later))
                break
            if getattr(later, "document", None) is not None:
                break
    for msg in ordered:
        if is_supported_video(msg) and msg.id not in claimed:
            result.append(Item(None, msg))
    return sorted(result, key=lambda item: item.video.id)

def film_title(item: Item) -> str:
    for obj in (item.poster, item.video):
        if obj is not None:
            caption = str(getattr(obj, "raw_text", "") or "").strip()
            if caption:
                return caption[:650]
    name = filename_of(item.video)
    return Path(name).stem.replace("_", " ").replace(".", " ")[:120] if name else "Film CinéX Désir"

def item_key(source_peer_id: int, item: Item) -> str:
    return f"{source_peer_id}:{item.video.id}"
