"""Read-only inventory of older CineX poster links (aggregate counts only)."""
import argparse
import asyncio
import json
import os
from collections import Counter
from .legacy_media_identity import find_legacy_poster
from .legacy_neighbor_matching import find_neighbor_pair, identity_for_pair
from .public_video_archive import has_verified_button
from .radar_download_registry import is_bot_download_url
from .ten_video_rotation import split_recent_and_old, movie_button_target, category_targets


def urls(poster):
    for row in getattr(poster, "buttons", None) or ():
        for entry in row:
            inner = getattr(entry, "button", entry)
            url = getattr(entry, "url", None) or getattr(inner, "url", None)
            label = getattr(entry, "text", None) or getattr(inner, "text", None)
            if isinstance(url, str) and isinstance(label, str):
                yield label, url


def analyze(messages, category, private_id, folder):
    recent, old = split_recent_and_old(messages, category)
    posters = [m for m in messages if getattr(m, "photo", None)]
    counts = Counter()
    counts["older"] = len(old)
    counts["protected"] = len(recent)
    pairs = []
    for video in old:
        poster = find_legacy_poster(video, posters, category)
        extra = ""
        if poster is None:
            adjacent = find_neighbor_pair(video, messages, category)
            if adjacent:
                poster, extra = adjacent.poster, adjacent.extra_text
        if not poster:
            counts["missing_poster"] += 1
        elif not identity_for_pair(video, poster, category, extra).safe:
            counts["uncertain_identity"] += 1
        else:
            pairs.append((video, poster))
    claimed = Counter(p.id for _, p in pairs)
    for _, poster in pairs:
        if claimed[poster.id] != 1:
            counts["ambiguous_poster"] += 1
            continue
        counts["unique_pairs"] += 1
        items = list(urls(poster))
        has_bot = any(is_bot_download_url(url) for _, url in items)
        has_watch = movie_button_target(poster, private_id) is not None
        if not has_bot:
            counts["missing_bot_download"] += 1
        if not has_watch:
            counts["missing_private_watch"] += 1
        if folder and not has_verified_button(poster, folder):
            counts["missing_folder"] += 1
        if not any("secours" in label.lower() for label, _ in items):
            counts["missing_rescue"] += 1
        if any("télécharger" in label.lower() and "/c/" in url for label,url in items):
            counts["direct_private_download"] += 1
        if has_bot and has_watch:
            counts["both_buttons"] += 1
    keys = ("older", "protected", "missing_poster", "uncertain_identity",
            "ambiguous_poster", "unique_pairs", "missing_bot_download",
            "missing_private_watch", "missing_folder", "missing_rescue",
            "direct_private_download", "both_buttons")
    return {k:int(counts[k]) for k in keys}


async def execute(history=1200):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from .runner import resolve_peer
    from .publication import film_folder_url
    if not 100 <= history <= 4000:
        raise ValueError("history must be between 100 and 4000")
    session = os.getenv("TG_STRING_SESSION") or os.getenv("TG_SESSION_STRING") or os.getenv("TG_STREAM_SESSION")
    api_id, api_hash = os.getenv("TG_API_ID"), os.getenv("TG_API_HASH")
    if not all((session, api_id, api_hash)):
        raise RuntimeError("Telegram credentials missing")
    client = TelegramClient(StringSession(session), int(api_id), api_hash, flood_sleep_threshold=0)
    await client.connect()
    reports = []
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram session unauthorized")
        for category, public, private_id in category_targets():
            try:
                peer = await resolve_peer(client, public)
                messages = [m async for m in client.iter_messages(peer, limit=history)]
                row = analyze(messages, category, private_id, film_folder_url())
                row["category"], row["scanned"] = category, len(messages)
            except Exception as error:
                if type(error).__name__ in ("FloodWaitError", "PeerFloodError"):
                    raise
                row = {"category":category,"status":"unavailable","reason":type(error).__name__}
            reports.append(row)
            print("CINEX_PUBLIC_SUMMARY " + json.dumps(row))
            await asyncio.sleep(2)
    finally:
        await client.disconnect()
    if any(r.get("status")=="unavailable" for r in reports):
        raise RuntimeError("Incomplete channel inventory")
    return reports


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=int, default=1200)
    args = parser.parse_args()
    asyncio.run(execute(args.history))
