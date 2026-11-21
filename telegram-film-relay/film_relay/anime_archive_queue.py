"""Durable source-ID queue decoupling legacy history discovery from uploads.

This compatibility module is for the existing MTProto scanner only. New
Bot API subscriptions cannot retrieve older messages without source access.
No media payload or Telegram credentials are persisted in the Git catalogue.
"""
from __future__ import annotations

from datetime import datetime


def enqueue_archive_candidates(catalogue, plans, rows):
    queue = catalogue.setdefault("archive_pending", {})
    archived = {}
    for plan in plans:
        if plan and not plan.get("revisit"):
            archived[str(plan["source_id"])] = set(plan.get("archive_ids", set()))
    added = 0
    for row in rows:
        source_key = str(row.get("source_key") or "")
        if ":" not in source_key:
            continue
        source_id, message_id = source_key.rsplit(":", 1)
        if source_id not in archived or int(message_id) not in archived[source_id]:
            continue
        if source_key in queue:
            continue
        poster = row.get("poster")
        queue[source_key] = {
            "source_key": source_key, "source_id": source_id,
            "message_id": int(message_id),
            "poster_id": int(poster.id) if poster else None,
            "series": str(row["series"]), "title": str(row["title"])[:100],
            "season": int(row["season"]), "episode": int(row["episode"]),
            "document_id": str(getattr(getattr(
                row.get("video"), "document", None), "id", "") or ""),
            "timestamp": float(row.get("timestamp") or 0),
        }
        added += 1
    return added


def prune_receipted_archive(catalogue):
    receipted = set()
    for entry in catalogue.get("series", {}).values():
        receipted.update(entry.get("source_items", {}))
    pending = catalogue.get("archive_pending", {})
    removed = 0
    for source_key in list(pending):
        if source_key in receipted:
            del pending[source_key]
            removed += 1
    return removed


async def recover_archive_queue(client, sources, catalogue, observed,
                                *, limit=80):
    """Retrieve verified, queued old episode IDs in bounded oldest-first order.

    Missing or protected posts stay in queue for manual review rather than
    being replaced with similar-looking files.
    """
    from telethon import utils
    from .desir_matching import is_supported_video
    from .episode_identity import episode_numbers, series_title, canonical_title
    from .matching import filename_of

    peers = {str(utils.get_peer_id(peer)): peer for peer in sources}
    seen = {str(row["source_key"]) for row in observed}
    pending = catalogue.get("archive_pending", {})
    recovered = 0
    for source_key, entry in sorted(
            pending.items(),
            key=lambda item: (float(item[1].get("timestamp") or 0),
                              item[0])):
        if recovered >= limit:
            break
        if source_key in seen:
            continue
        peer = peers.get(str(entry["source_id"]))
        if peer is None:
            continue
        video = await client.get_messages(peer, ids=int(entry["message_id"]))
        if (not video or getattr(video, "noforwards", False)
                or not is_supported_video(video)):
            continue
        found = episode_numbers(
            (getattr(video, "raw_text", "") or "") + " " + filename_of(video))
        if not found or int(found[1]) != int(entry["episode"]):
            catalogue.setdefault("archive_review", {})[source_key] = (
                "source_renamed_or_episode_mismatch")
            continue
        expected_doc = str(entry.get("document_id") or "")
        actual_doc = str(getattr(getattr(video, "document", None), "id", "") or "")
        if expected_doc and actual_doc != expected_doc:
            catalogue.setdefault("archive_review", {})[source_key] = (
                "source_media_changed")
            continue
        poster = None
        if entry.get("poster_id"):
            poster = await client.get_messages(peer, ids=int(entry["poster_id"]))
            if (poster is None or not getattr(poster, "photo", None)
                    or getattr(poster, "noforwards", False)):
                poster = None
        if poster is not None:
            poster_name = canonical_title(series_title(
                getattr(poster, "raw_text", "") or ""))
            expected_name = canonical_title(series_title(entry["title"]))
            if poster_name and expected_name and poster_name != expected_name:
                catalogue.setdefault("archive_review", {})[source_key] = (
                    "source_poster_title_changed")
                continue
        observed.append({
            "source_key": source_key, "series": entry["series"],
            "title": entry["title"], "season": int(entry["season"]),
            "episode": int(entry["episode"]), "video": video,
            "poster": poster, "timestamp": float(entry.get("timestamp") or 0),
        })
        seen.add(source_key)
        recovered += 1
    return recovered
