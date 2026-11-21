"""Bounded reconciliation of legacy CineX Anime download links.

The already owner-approved unified private stock is reused. Existing Anime
private video IDs, original episode receipts, public posts and buttons are
never changed here. Never silently retry a timed-out central-stock send.
"""
from __future__ import annotations

import asyncio

from .public_video_archive import is_video_message


async def repair_existing_download_links(
    client, anime_private_peer, public_peer, unified, catalogue,
    save_catalog, *, limit: int = 2, pause_seconds: float = 36.0,
):
    if not 0 <= limit <= 4:
        raise ValueError("Anime legacy download repair limit must be between 0 and 4.")
    stats = {"checked": 0, "registered": 0, "missing_private": 0,
             "skipped_existing": 0, "stock_unavailable": 0}
    if not limit or unified.target_id is None:
        return stats
    for series_key, entry in sorted((catalogue.get("series") or {}).items()):
        title = str(entry.get("title") or series_key)
        for season_key, season_episodes in sorted(
                (entry.get("episodes") or {}).items(), key=lambda x: int(x[0])):
            for number_key, saved in sorted(
                    season_episodes.items(), key=lambda x: int(x[0])):
                if saved.get("download_url"):
                    stats["skipped_existing"] += 1
                    continue
                if stats["checked"] >= limit:
                    return stats
                stats["checked"] += 1
                old_id = saved.get("message_id")
                if not old_id:
                    stats["missing_private"] += 1
                    continue
                video = await client.get_messages(
                    anime_private_peer, ids=int(old_id))
                if not is_video_message(video):
                    stats["missing_private"] += 1
                    continue
                # No fallback to other source channels. This exact private
                # episode receipt is our only source for backfill.
                deep_link = await unified.store(
                    video, category="anime",
                    title=f"{title} S{int(season_key):02d}E{int(number_key):02d}",
                    public=public_peer,
                )
                if not deep_link:
                    stats["stock_unavailable"] += 1
                    continue
                saved["download_url"] = deep_link
                save_catalog(catalogue)
                stats["registered"] += 1
                if pause_seconds:
                    await asyncio.sleep(pause_seconds)
    return stats
