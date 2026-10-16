"""Reconstruct CinéX publication receipts from Telegram itself after GitHub push conflicts.

Only the source document's exact Telegram document ID is used for matching:
a similarly named movie is not sufficient to mark a post as published.
"""
from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass
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


async def snapshot_telegram_posts(
    client, private_channel, public_channel, private_peer_id: int,
    *, private_limit: int = 650, public_limit: int = 650,
) -> TelegramReceiptCache:
    private: dict[int, list[int]] = defaultdict(list)
    async for message in client.iter_messages(private_channel, limit=private_limit):
        doc_id = movie_document_id(message)
        if doc_id is not None:
            private[doc_id].append(int(message.id))
    public: dict[int, int] = {}
    async for message in client.iter_messages(public_channel, limit=public_limit):
        for video_id in referenced_private_messages(message, private_peer_id):
            public.setdefault(video_id, int(message.id))
    return TelegramReceiptCache(dict(private), public)


def recover_from_snapshot(cache: TelegramReceiptCache, state, pair_id: str,
                          media_id: str | None, movie, *, logger=None) -> str:
    """Return complete, staged, or none. Store a checkpoint BEFORE further sends.

    Complete = a matching source document and a public post linking to that
    precise private video. Staged = matching private video but no public post.
    """
    doc_id = movie_document_id(movie)
    if doc_id is None:
        return "none"
    candidates = cache.by_document.get(doc_id, [])
    if not candidates:
        return "none"
    # Prefer a video whose public post exists, including one from an older run.
    for private_video_id in candidates:
        public_post_id = cache.public_by_video.get(private_video_id)
        if public_post_id:
            state.add(pair_id, media_id, private_video_id, public_post_id)
            if logger:
                logger.warning(
                    "PUBLIÉ ANTÉRIEUREMENT, checkpoint réparé : %s privé=%s public=%s",
                    pair_id, private_video_id, public_post_id,
                )
            return "complete"
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
