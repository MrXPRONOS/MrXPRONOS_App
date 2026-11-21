"""Near-neighbour pairing for historic CineX Telegram posts.

A conservative alternate to title matching when videos have generic captions.
Pairs must be strictly consecutive: photo->video or photo->plain-text->video.
Never join across other media, service posts, or conflicting explicit titles.
"""
from __future__ import annotations

from dataclasses import dataclass

from .legacy_media_identity import Identity, compatible, parse_identity, poster_identity, video_identity
from .public_video_archive import is_video_message


@dataclass(frozen=True)
class NeighborPair:
    poster: object
    extra_text: str
    identity: Identity
    mode: str


def is_plain_text(message) -> bool:
    return bool(
        message is not None
        and (getattr(message, "raw_text", "") or "").strip()
        and not getattr(message, "photo", None)
        and not getattr(message, "document", None)
        and not getattr(message, "media", None)
        and not getattr(message, "action", None)
        and not getattr(message, "buttons", None)
    )


def identity_for_pair(video, poster, category: str, text: str = "") -> Identity:
    media = video_identity(video, category)
    cover = poster_identity(poster, category)
    supplemental = parse_identity(text, category) if text else Identity("", "missing")
    if media.kind == "conflict":
        return Identity("", "conflict")
    if media.safe and cover.safe and compatible(media, cover) < 0.95:
        return Identity("", "conflict")
    if media.safe and supplemental.safe and compatible(media, supplemental) < 0.95:
        return Identity("", "conflict")
    if cover.safe and supplemental.safe and compatible(cover, supplemental) < 0.95:
        return Identity("", "conflict")
    # An explicit episode or part on the media takes priority over the
    # general series/movie cover; otherwise prefer an identified cover.
    if media.safe and (media.episode is not None or media.part is not None):
        return media
    for candidate in (cover, supplemental, media):
        if candidate.safe:
            return candidate
    return Identity("", "missing")


def find_neighbor_pair(video, messages, category: str) -> NeighborPair | None:
    """Require exactly the previous messages and no cross-video guess."""
    by_id = {int(m.id): m for m in messages}
    item = by_id.get(video.id - 1)
    poster = None
    extra = ""
    mode = ""
    if item is not None and getattr(item, "photo", None):
        poster, mode = item, "poster_video"
    elif is_plain_text(item):
        previous = by_id.get(video.id - 2)
        if previous is not None and getattr(previous, "photo", None):
            poster, extra, mode = previous, item.raw_text.strip(), "poster_text_video"
    if poster is None or not is_video_message(video):
        return None
    ident = identity_for_pair(video, poster, category, extra)
    if not ident.safe:
        return None
    return NeighborPair(poster=poster, extra_text=extra,
                        identity=ident, mode=mode)
