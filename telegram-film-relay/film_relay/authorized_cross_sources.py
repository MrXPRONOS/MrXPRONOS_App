"""Conservative cross-channel media matching for explicitly authorized sources.

Never click an unapproved destination or join a channel; Telegram's owner
account must already be a member. Never bypass forwarding restrictions or
infer a title from an untrusted invitation link. Only reconcile known public
@usernames from external GitHub source/media allowlists.
"""
from __future__ import annotations

import re
from dataclasses import replace

from .desir_matching import Item, is_supported_video
from .episode_identity import episode_numbers, consistent_title
from .matching import filename_of
from .title_guard import title_assessment, tokens
from .source_channels import source_list

PUBLIC_POST = re.compile(r"^https?://t\.me/([A-Za-z0-9_]{5,32})/(\d+)(?:\?.*)?$", re.I)
MAX_FOLLOWED = 20


def linked_posts(message, allowed_handles):
    """Read inline URLs from an already authorized source without joining."""
    allowed = {x.casefold() for x in allowed_handles}
    found = []
    for row in getattr(message, "buttons", None) or ():
        for b in row:
            url = getattr(b, "url", None) or getattr(
                getattr(b, "button", None), "url", None)
            match = PUBLIC_POST.fullmatch(str(url or ""))
            if match:
                handle = "@" + match.group(1)
                if handle.casefold() in allowed:
                    found.append((handle, int(match.group(2))))
    return list(dict.fromkeys(found))[:MAX_FOLLOWED]


async def authorized_peers(client, handles, *, banned_ids=frozenset()):
    """Resolve existing members only; never send JoinChannelRequest."""
    from telethon import utils
    peers = []
    for handle in source_list(*handles):
        peer = await client.get_entity(handle)
        if (not getattr(peer, "broadcast", False)
                or getattr(peer, "noforwards", False)
                or str(getattr(peer, "username", "") or "").casefold()
                    != handle[1:].casefold()
                or utils.get_peer_id(peer) in banned_ids):
            raise RuntimeError("Canal média absent, protégé ou incorrect : " + handle)
        peers.append((handle, peer))
    return peers


def _title_compatible(poster, media, channel_name=""):
    """Both title tokens must convincingly agree (no adjacency-only match)."""
    text = getattr(poster, "raw_text", "") or ""
    video_caption = getattr(media, "raw_text", "") or ""
    filename = filename_of(media)
    if title_assessment(poster, media) == "verified":
        return True
    a = tokens(text.splitlines()[0] if text else "")
    b = tokens(video_caption) | tokens(filename) | tokens(channel_name)
    if len(a) < 1 or len(b) < 1:
        return False
    common = a & b
    return len(common) >= min(2, len(a)) and len(common) >= min(2, len(b))


def cross_channel_movie_pairs(posters, media_messages):
    """Pair only uniquely compatible titles across separate authorized feeds."""
    matched = []
    for poster in posters:
        if not getattr(poster, "photo", None) or getattr(poster, "noforwards", False):
            continue
        possibilities = [
            media for media, channel_title in media_messages
            if is_supported_video(media) and _title_compatible(
                poster, media, channel_title)
        ]
        if len(possibilities) == 1:
            matched.append(Item(poster, possibilities[0]))
    return matched


def _episode_key(message):
    caption = getattr(message, "raw_text", "") or ""
    return episode_numbers(caption) or episode_numbers(filename_of(message))


def _show_match(poster, media, media_peer):
    """Match named series explicitly, including dedicated episode channels."""
    title = consistent_title(
        getattr(poster, "raw_text", "") or "",
        getattr(media, "raw_text", "") or "",
        filename_of(media),
    )
    if title:
        return title
    # Dedicated series channels can contain videos named EP01.mkv, but the
    # channel title still must agree with the original poster.
    channel_title = getattr(media_peer, "title", "") or ""
    a = tokens((getattr(poster, "raw_text", "") or "").splitlines()[0])
    b = tokens(channel_title)
    if not a or not b or len(a & b) < min(2, len(a)):
        return None
    # Verify no contradictory named title in video caption or filename.
    video_words = tokens(getattr(media, "raw_text", "") or "") | tokens(filename_of(media))
    if video_words and len(video_words) >= 2 and not a.intersection(video_words):
        return None
    return (getattr(poster, "raw_text", "") or "").splitlines()[0]


def cross_channel_series_rows(posters, media_messages):
    """Associate dedicated-channel numbered episodes with exactly one cover.

    Ambiguous source posters, missing explicit episode indexes, and
    contradictory series names are quarantined, never guessed.
    """
    from .series_catalog import slug
    rows = []
    for media, peer in media_messages:
        if not is_supported_video(media):
            continue
        numbers = _episode_key(media)
        if not numbers:
            continue
        matches = []
        for poster in posters:
            if getattr(poster, "noforwards", False):
                continue
            title = _show_match(poster, media, peer)
            if title:
                matches.append((poster, title))
        unique = {(slug(t), id(p)): (p, t) for p, t in matches}
        titles = {slug(title) for _, title in unique.values()}
        if len(titles) != 1:
            continue
        # Multiple covers of same exact series are allowed only when they
        # share an identical normalized title; choose newest validated one.
        poster, title = max(unique.values(), key=lambda x: int(x[0].id))
        from telethon import utils
        rows.append({
            "source_key": f"{utils.get_peer_id(peer)}:{int(media.id)}",
            "series": slug(title), "title": title,
            "season": int(numbers[0]), "episode": int(numbers[1]),
            "video": media, "poster": poster,
            "timestamp": getattr(getattr(media, "date", None), "timestamp", lambda: 0)(),
        })
    return rows


async def follow_authorized_button_posts(client, messages, media_peers):
    """Follow ONLY direct post URLs from allowed channels already accessible."""
    allowed = {handle.casefold(): peer for handle, peer in media_peers}
    seen = {}
    for message in messages:
        for handle, msg_id in linked_posts(message, allowed):
            peer = allowed[handle.casefold()]
            try:
                found = await client.get_messages(peer, ids=int(msg_id))
            except Exception:
                continue
            if found is not None and not getattr(found, "noforwards", False):
                seen[(handle.casefold(), msg_id)] = (found, peer)
            if len(seen) >= MAX_FOLLOWED:
                return list(seen.values())
    return list(seen.values())
