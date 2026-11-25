"""Reconstruct CinéX publication receipts from Telegram itself after GitHub push conflicts.

Only the source document's exact Telegram document ID is used for matching:
a similarly named movie is not sufficient to mark a post as published.
"""
from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

LINK = re.compile(r"https://t\.me/c/(?P<channel>\d+)/(?P<message>\d+)(?:\b|/)")


def movie_document_id(message: Any) -> int | None:
    doc = getattr(message, "document", None)
    value = getattr(doc, "id", None)
    return int(value) if value is not None else None


def referenced_private_messages(message: Any, private_peer_id: int) -> set[int]:
    """Find exact private-video message IDs inside bot buttons or old plain captions."""
    urls = [str(getattr(message, "raw_text", "") or "")]
    markup = getattr(message, "reply_markup", None)
    for row in getattr(markup, "rows", []) or []:
        for button in getattr(row, "buttons", []) or []:
            urls.append(str(getattr(button, "url", "") or ""))
    # Tests/alternative Telethon wrappers expose buttons via .buttons.
    for row in getattr(message, "buttons", []) or []:
        for button in row:
            urls.append(str(getattr(button, "url", "") or ""))
    expected_channel = str(private_peer_id).removeprefix("-100")
    matches = set()
    for value in urls:
        for found in LINK.finditer(value):
            if found.group("channel") == expected_channel:
                matches.add(int(found.group("message")))
    return matches


@dataclass
class TelegramReceiptCache:
    """A bounded snapshot read from Telegram, independent of GitHub's state file."""
    by_document: dict[int, list[int]]
    public_by_video: dict[int, int]
    public_v4_by_video: dict[int, int] = field(default_factory=dict)
    by_source_marker: dict[str, list[int]] = field(default_factory=dict)


async def snapshot_telegram_posts(
    client, private_channel, public_channel, private_peer_id: int,
    *, private_limit: int = 650, public_limit: int = 650,
) -> TelegramReceiptCache:
    private: dict[int, list[int]] = defaultdict(list)
    named: dict[str, list[int]] = defaultdict(list)
    from .private_media_contract import source_marker_from_message
    from .private_stock_audit import filename_descriptive
    async for message in client.iter_messages(private_channel, limit=private_limit):
        doc_id = movie_document_id(message)
        if doc_id is not None:
            private[doc_id].append(int(message.id))
            marker = source_marker_from_message(message)
            if marker and filename_descriptive(
                    getattr(getattr(message, "file", None), "name", "") or ""):
                named[marker].append(int(message.id))
    public: dict[int, int] = {}
    public_messages = []
    async for message in client.iter_messages(public_channel, limit=public_limit):
        public_messages.append(message)
        for video_id in referenced_private_messages(message, private_peer_id):
            public.setdefault(video_id, int(message.id))
    # A poster alone (or a video with no verified keyboard) is not a
    # completed V4 pair. Preserve the legacy map only to prevent reposts.
    v4 = verified_v4_pairs(public_messages, public_channel, private_peer_id, private)
    return TelegramReceiptCache(dict(private), public, v4, dict(named))


def verified_v4_pairs(messages, public_channel, private_peer_id, private_by_document):
    """Read-only proof of a direct V4 poster/video pair with the same document."""
    from .publication import (read_url_button_rows, verify_complete_public_video_poster,
                              verify_complete_public_video_keyboard)
    from .cinex_v4_policy import has_automatic_ttl
    from .public_video_archive import is_video_message
    from .radar_download_registry import is_bot_download_url
    from .text import private_message_link
    photos = {}
    result = {}
    for message in sorted(messages, key=lambda m: int(m.id)):
        rows = read_url_button_rows(message)
        if len(rows) != 4 or any(len(row) != 1 for row in rows):
            continue
        watch_label, watch_url = rows[0][0]
        _, download_url = rows[1][0]
        if not is_bot_download_url(download_url):
            continue
        for private_mid in referenced_private_messages(message, private_peer_id):
            link = private_message_link(private_peer_id, private_mid)
            if watch_url != link:
                continue
            if getattr(message, "photo", None):
                if verify_complete_public_video_poster(message, public_channel,
                        link, download_url, watch_label=watch_label):
                    photos[private_mid] = (int(message.id), rows)
            elif is_video_message(message) and has_automatic_ttl(message):
                doc = movie_document_id(message)
                prior = photos.get(private_mid)
                if (prior and prior[1] == rows
                        and private_mid in private_by_document.get(doc, ())
                        and verify_complete_public_video_keyboard(message, public_channel,
                                link, download_url, watch_label=watch_label)):
                    result[private_mid] = prior[0]
    return result


def recover_from_snapshot(cache: TelegramReceiptCache, state, pair_id: str,
                          media_id: str | None, movie, *, logger=None) -> str:
    """Return complete, staged, or none. Store a checkpoint BEFORE further sends.

    Complete = exact document and verified V4 photo+video+keyboard.
    Incomplete = a legacy public link without full V4 proof (quarantine).
    Staged = matching private video but no public post.
    """
    doc_id = movie_document_id(movie)
    if doc_id is None:
        return "none"
    from .private_media_contract import marker_for
    candidates = (cache.by_document.get(doc_id, []) or
                  cache.by_source_marker.get(marker_for(movie), []))
    if not candidates:
        return "none"
    # Only a fully verified photo + tagged video with matching four-button
    # keyboards proves a V4 publication. An older poster with a private link
    # is NOT enough; preserve its receipt and quarantine it without reupload.
    for private_video_id in candidates:
        verified_poster_id = cache.public_v4_by_video.get(private_video_id)
        if verified_poster_id:
            state.add(pair_id, media_id, private_video_id, verified_poster_id)
            if logger:
                logger.warning(
                    "Paire V4 confirmée, checkpoint réparé : %s privé=%s public=%s",
                    pair_id, private_video_id, verified_poster_id,
                )
            return "complete"
    for private_video_id in candidates:
        if private_video_id in cache.public_by_video:
            state.stage(pair_id, private_video_id)
            if logger:
                logger.error(
                    "Lien public historique sans paire V4 vérifiée : %s ; "
                    "reprise bloquée, aucun doublon.", pair_id,
                )
            return "incomplete"
    # Video was copied but no public message completed. Resume only the public.
    state.stage(pair_id, candidates[0])
    if logger:
        logger.warning(
            "VIDÉO DÉJÀ PRÉSENTE, reprise sans nouveau MKV : %s privé=%s",
            pair_id, candidates[0],
        )
    return "staged"


async def existing_native_forwards(client, mirror_channel, origin_public_peer_id: int,
                                   *, limit: int = 600) -> dict[int, int]:
    """Map original public-post ID to existing forwarded message ID.

    Avoid duplicate forwards after a successful Telegram send whose state
    could not be committed to GitHub.
    """
    origin = str(origin_public_peer_id).removeprefix("-100")
    forwards: dict[int, int] = {}
    async for post in client.iter_messages(mirror_channel, limit=limit):
        forwarded = getattr(post, "fwd_from", None)
        peer = getattr(forwarded, "from_id", None)
        channel_id = getattr(peer, "channel_id", None)
        original_post_id = getattr(forwarded, "channel_post", None)
        if channel_id is not None and str(channel_id) == origin and original_post_id:
            forwards.setdefault(int(original_post_id), int(post.id))
    return forwards
