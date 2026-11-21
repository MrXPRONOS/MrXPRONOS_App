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
    if message is None:
        return False
    attachment = getattr(message, "media", None)
    # A link-preview generated from the intervening description remains text.
    if attachment is not None and type(attachment).__name__ not in (
        "MessageMediaWebPage", "MessageMediaEmpty"
    ):
        return False
    return bool(
        (getattr(message, "raw_text", "") or "").strip()
        and not getattr(message, "photo", None)
        and not getattr(message, "document", None)
        and not getattr(message, "action", None)
        and not getattr(message, "buttons", None)
    )


def identity_for_pair(video, poster, category: str, text: str = "") -> Identity:
    media = video_identity(video, category)
    cover = poster_identity(poster, category)
    first_line = (text or "").strip().splitlines()
    first_line = first_line[0].casefold().strip() if first_line else ""
    description_only = first_line.startswith((
        "synopsis", "résumé", "resume", "description", "histoire", "genre", "durée", "duree"
    ))
    supplemental = (parse_identity(text, category)
                    if text and not description_only else Identity("", "missing"))
    if media.kind == "conflict":
        return Identity("", "conflict")
    # Contradictory explicit metadata must block even when the title is
    # generic or missing (e.g. "Film Partie 1" vs "Film Partie 2").
    for left, right in ((media, cover), (media, supplemental), (cover, supplemental)):
        if (left.part is not None and right.part is not None
                and left.part != right.part):
            return Identity("", "conflict")
        if (left.episode is not None and right.episode is not None
                and (left.season, left.episode) != (right.season, right.episode)):
            return Identity("", "conflict")
        if (left.year is not None and right.year is not None
                and left.year != right.year):
            return Identity("", "conflict")
    if media.safe and cover.safe and compatible(media, cover) < 0.95:
        return Identity("", "conflict")
    # The intervening text is often a synopsis, not an independent title.
    # Accept that metadata as description unless it explicitly claims to be a
    # different title, episode or part. Never invent numbering from a synopsis.
    cue = (text or "").strip().casefold()
    explicit = cue.startswith(("titre:", "title:")) or (
        supplemental.episode is not None or supplemental.part is not None
    )
    if explicit and media.safe and supplemental.safe and compatible(media, supplemental) < 0.95:
        return Identity("", "conflict")
    if explicit and cover.safe and supplemental.safe and compatible(cover, supplemental) < 0.95:
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
    if ident.kind == "conflict":
        return None
    if not ident.safe:
        # Strong adjacency and matching Telegram media ID, not a guessed
        # movie name, are enough to rescue an unnamed upload. The generated
        # label explicitly says that its real title is unknown.
        ident = Identity(f"contenu sans titre {int(video.id)}", "unknown")
    return NeighborPair(poster=poster, extra_text=extra,
                        identity=ident, mode=mode)
