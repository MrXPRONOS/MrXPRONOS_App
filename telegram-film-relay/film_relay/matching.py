"""Find a movie poster immediately preceding an associated video.

All routines are pure so they can be tested without Telegram credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Sequence
import re

VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v")
TRAILER = re.compile(r"\b(trailer|bande[- ]annonce|teaser|extrait)\b", re.I)


@dataclass(frozen=True)
class Pair:
    poster: Any
    movie: Any
    # The description may be a separate text message posted after the photo.
    description_message: Any | None = None


def document_of(msg: Any) -> Any:
    return getattr(msg, "document", None)


def filename_of(msg: Any) -> str:
    """Read filename from Telethon Message.file OR DocumentAttributeFilename.

    MKV is commonly uploaded as a generic Telegram document, not Video.
    """
    name = getattr(getattr(msg, "file", None), "name", None)
    if name:
        return str(name).lower()
    doc = document_of(msg)
    for attr in getattr(doc, "attributes", []) or []:
        value = getattr(attr, "file_name", None)
        if value:
            return str(value).lower()
    return ""


def is_video(msg: Any) -> bool:
    """A video-file message, not a short clip or a text-only message."""
    if getattr(msg, "photo", None) is not None:
        return False
    doc = document_of(msg)
    if doc is None and getattr(msg, "video", None) is None:
        return False
    mime = str(getattr(doc, "mime_type", "") or "").lower()
    filename = filename_of(msg)
    if not (mime.startswith("video/") or "matroska" in mime or filename.endswith(VIDEO_EXT) or getattr(msg, "video", None)):
        return False
    if TRAILER.search(str(getattr(msg, "raw_text", "") or "")):
        return False
    duration = getattr(getattr(msg, "file", None), "duration", None)
    size = getattr(getattr(msg, "file", None), "size", None) or getattr(doc, "size", None) or 0
    # Exclude tiny teaser clips; duration, when available, has priority.
    if duration and duration < 600:
        return False
    if not duration and size and size < 35 * 1024 * 1024:
        return False
    return True


def is_poster(msg: Any) -> bool:
    """Require an actual photo with a nontrivial film-style caption."""
    if not getattr(msg, "photo", None):
        return False
    text = str(getattr(msg, "raw_text", "") or "").strip()
    # URLs alone, advertisements and empty captions must not count.
    stripped = re.sub(r"(?i)(?:https?://|www\.|t\.me/|telegram\.me/)\S+", "", text).strip()
    return len(stripped) >= 12 and len(stripped.split()) >= 2


def match_pairs(messages: Sequence[Any], *, max_gap: int = 4, max_age_minutes: int = 180) -> list[Pair]:
    """Pair by source ordering, plus reply/media-group signals when available.

    Hard boundary: a second poster prevents an earlier poster from claiming a
    later video. Does not assert the text and video describe the same film.
    """
    ordered = sorted((x for x in messages if getattr(x, "id", None) is not None), key=lambda x: x.id)
    result: list[Pair] = []
    claimed: set[int] = set()
    for idx, poster in enumerate(ordered):
        if not is_poster(poster):
            continue
        choices: list[tuple[int, int, Any]] = []
        for movie in ordered[idx + 1:idx + 1 + max_gap]:
            if is_poster(movie):
                break
            if not is_video(movie) or movie.id in claimed:
                continue
            pd, md = getattr(poster, "date", None), getattr(movie, "date", None)
            if pd and md and (md < pd or md - pd > timedelta(minutes=max_age_minutes)):
                continue
            reply = getattr(getattr(movie, "reply_to", None), "reply_to_msg_id", None) == poster.id
            grouped = bool(getattr(poster, "grouped_id", None)) and (
                getattr(poster, "grouped_id", None) == getattr(movie, "grouped_id", None)
            )
            # Prefer an explicit reply or album match; otherwise proximity.
            score = (100 if reply else 0) + (70 if grouped else 0) - (movie.id - poster.id)
            choices.append((-score, movie.id, movie))
        if choices:
            _, _, chosen = min(choices)
            result.append(Pair(poster, chosen))
            claimed.add(chosen.id)
    return result



# Trusting a particular MKV source never waives Telegram's no-forward protection.
# Identifying a movie from its descriptive text remains a format heuristic.
FILM_CUES = re.compile(
    r"\b(?:films?|titre(?:\s+original)?|dur[ée]e|genre|synopsis|"
    r"r[ée]sum[ée]|r[ée]alisateur|acteurs?|casting|ann[ée]e|sortie|"
    r"production|vostfr|version\s+fran[cç]aise)\b",
    re.IGNORECASE,
)
LINKS = re.compile(r"(?i)(?:https?://|www\.|t\.me/|telegram\.me/)\S+")


def is_film_description(value: str) -> bool:
    """Identify an actual movie listing rather than a caption containing only links."""
    cleaned = LINKS.sub("", str(value or "")).strip()
    return len(cleaned) >= 10 and bool(FILM_CUES.search(cleaned))


def is_mkv_document(msg: Any) -> bool:
    if getattr(msg, "photo", None) or not document_of(msg):
        return False
    mime = str(getattr(document_of(msg), "mime_type", "") or "").lower()
    return filename_of(msg).endswith(".mkv") or "matroska" in mime


def description_of(pair: Pair) -> str:
    msg = pair.description_message if pair.description_message is not None else pair.poster
    return str(getattr(msg, "raw_text", "") or "")


def description_entities_of(pair: Pair):
    msg = pair.description_message if pair.description_message is not None else pair.poster
    return getattr(msg, "entities", None)


def match_authorized_mkv_pairs(messages: Sequence[Any]) -> list[Pair]:
    """For a licensed source only: photo+caption+MKV or photo+text+MKV.

    No file size, duration, time interval or message-id-distance assumptions.
    Messages must be consecutive *in the retrieved list*. Multiple photos,
    unrelated posts or other videos interrupt the association.
    """
    ordered = sorted(
        (x for x in messages if getattr(x, "id", None) is not None),
        key=lambda x: x.id,
    )
    result = []
    used_movies: set[int] = set()
    for i, poster in enumerate(ordered):
        if not getattr(poster, "photo", None) or getattr(poster, "noforwards", False):
            continue
        caption_ok = is_film_description(getattr(poster, "raw_text", "") or "")
        if i + 1 >= len(ordered):
            continue
        nxt = ordered[i + 1]
        description_msg = None
        movie = None
        if is_mkv_document(nxt):
            if caption_ok:
                movie = nxt
        elif (not getattr(nxt, "photo", None)
              and document_of(nxt) is None
              and not getattr(nxt, "noforwards", False)
              and i + 2 < len(ordered)
              and is_film_description(getattr(nxt, "raw_text", "") or "")):
            candidate = ordered[i + 2]
            if is_mkv_document(candidate):
                description_msg = nxt
                movie = candidate
        if movie is None or movie.id in used_movies or getattr(movie, "noforwards", False):
            continue
        result.append(Pair(poster=poster, movie=movie, description_message=description_msg))
        used_movies.add(movie.id)
    return result


def document_key(msg: Any) -> str | None:
    doc = document_of(msg)
    doc_id = getattr(doc, "id", None)
    return f"doc:{doc_id}" if doc_id is not None else None
